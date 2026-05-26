"""
Utility electricity data ingestion parser.

Format: Billing Summary CSV (Green Button-compatible / utility portal export).
This is the format exported from utility portals (PG&E, ComEd, Eversource,
Duke Energy, etc.) via their web portal "Download My Data" feature.

Design decisions documented in DECISIONS.md:
- We chose billing summary CSV over Green Button ESPI XML because:
  (a) it is the simplest format any facilities team can export without IT involvement,
  (b) the ESPI XML format, while more precise (15-min interval data), requires
      parsing Unix timestamps and ESPI UoM codes — significant complexity for a
      prototype with no added analytical value at monthly reporting granularity.
- Billing period proration: we store raw billing periods AND compute calendar-month
  allocations. Proration is simple (proportional days). A real deployment would
  prefer 15-min AMI interval data to avoid proration altogether.

Scope: Scope 2, location-based method.
Emission factor: EPA eGRID2022 by US state → subregion.
"""

import io
import logging
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from core.models import IngestionBatch, RawRecord, EmissionRecord
from .emission_factors import get_egrid_factor

logger = logging.getLogger(__name__)


COLUMN_ALIASES = {
    'account_number': 'account_number',
    'account number': 'account_number',
    'account no': 'account_number',
    'account no.': 'account_number',
    'service_address': 'service_address',
    'service address': 'service_address',
    'address': 'service_address',
    'meter_id': 'meter_id',
    'meter id': 'meter_id',
    'meter serial': 'meter_id',
    'meter': 'meter_id',
    'service_point_id': 'service_point_id',
    'service point id': 'service_point_id',
    'billing_period_start': 'period_start',
    'billing period start': 'period_start',
    'period start': 'period_start',
    'start date': 'period_start',
    'bill start': 'period_start',
    'billing_period_end': 'period_end',
    'billing period end': 'period_end',
    'period end': 'period_end',
    'end date': 'period_end',
    'bill end': 'period_end',
    'billing_days': 'billing_days',
    'billing days': 'billing_days',
    'days in period': 'billing_days',
    'days': 'billing_days',
    'kwh_consumption': 'kwh',
    'kwh consumption': 'kwh',
    'consumption kwh': 'kwh',
    'total kwh': 'kwh',
    'kwh': 'kwh',
    'usage (kwh)': 'kwh',
    'electric usage (kwh)': 'kwh',
    'peak_demand_kw': 'peak_demand_kw',
    'peak demand kw': 'peak_demand_kw',
    'peak demand (kw)': 'peak_demand_kw',
    'tariff_code': 'tariff_code',
    'tariff code': 'tariff_code',
    'rate schedule': 'tariff_code',
    'rate code': 'tariff_code',
    'tariff_description': 'tariff_description',
    'tariff description': 'tariff_description',
    'rate description': 'tariff_description',
    'total_charges_usd': 'total_charges',
    'total charges usd': 'total_charges',
    'total charges': 'total_charges',
    'total amount': 'total_charges',
    'read_type': 'read_type',
    'read type': 'read_type',
    'utility_name': 'utility_name',
    'utility name': 'utility_name',
    'utility': 'utility_name',
    'state': 'state',
    'egrid_subregion': 'egrid_subregion',
    'egrid subregion': 'egrid_subregion',
    'subregion': 'egrid_subregion',
}


def _normalize_header(col: str) -> str:
    return col.strip().lower().rstrip('.').replace('_', ' ')


def _map_columns(df: pd.DataFrame) -> dict:
    mapping = {}
    for col in df.columns:
        key = COLUMN_ALIASES.get(_normalize_header(col))
        if key and key not in mapping:
            mapping[key] = col
    return mapping


def _parse_date(value: str):
    if not value or not value.strip():
        return None
    from datetime import datetime
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _prorate_to_calendar_months(kwh: Decimal, period_start: date, period_end: date) -> list:
    """
    Split kWh proportionally across calendar months within the billing period.
    Returns list of (year, month, kwh_allocated).
    
    Example: 41,250 kWh from Jan 8 to Feb 6 (29 days)
      Jan: 24/29 × 41,250 = 34,138 kWh
      Feb:  5/29 × 41,250 =  7,112 kWh
    """
    total_days = (period_end - period_start).days
    if total_days <= 0:
        return [(period_start.year, period_start.month, kwh)]

    allocations = {}
    current = period_start
    while current < period_end:
        month_end = date(
            current.year + (current.month // 12),
            (current.month % 12) + 1,
            1
        ) if current.month < 12 else date(current.year + 1, 1, 1)
        chunk_end = min(month_end, period_end)
        days_in_chunk = (chunk_end - current).days
        key = (current.year, current.month)
        allocations[key] = allocations.get(key, 0) + days_in_chunk
        current = chunk_end

    result = []
    for (year, month), days in sorted(allocations.items()):
        allocated_kwh = kwh * Decimal(str(days)) / Decimal(str(total_days))
        result.append((year, month, allocated_kwh.quantize(Decimal('0.001'))))
    return result


def _auto_flags(kwh: Decimal, period_start: date, period_end: date, read_type: str) -> list:
    flags = []
    if kwh is None or kwh <= 0:
        flags.append('Zero or negative kWh consumption — verify meter reading')
    if period_start and period_end:
        days = (period_end - period_start).days
        if days > 45:
            flags.append(f'Unusually long billing period: {days} days (>45)')
        if days < 20:
            flags.append(f'Unusually short billing period: {days} days (<20)')
    if period_end and period_end > date.today():
        flags.append(f'Billing period end is in the future: {period_end}')
    if read_type and 'ESTIMATED' in read_type.upper():
        flags.append('Estimated meter read — actual consumption may differ')
    return flags


def parse_utility_file(file_obj, batch: IngestionBatch, tenant) -> dict:
    """
    Parse a utility billing summary CSV and create EmissionRecord rows.
    One EmissionRecord is created per billing period row (not per calendar month).
    Proration metadata is stored in activity_description for transparency.
    """
    raw_bytes = file_obj.read()
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    log = []
    created = warnings = errors = 0

    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except Exception as e:
        return {'created': 0, 'warnings': 0, 'errors': 1, 'log': [f'Parse failed: {e}']}

    df.columns = [c.strip() for c in df.columns]
    col_map = _map_columns(df)
    log.append(f'Columns identified: {list(col_map.keys())}')

    raw_records_to_create = []
    emission_records_to_create = []

    for idx, row in df.iterrows():
        raw_data = row.to_dict()
        parse_errors = []
        parse_status = 'OK'

        def get(key, default=''):
            col = col_map.get(key)
            return raw_data.get(col, default).strip() if col else default

        meter_id       = get('meter_id')
        account_number = get('account_number')
        period_start   = _parse_date(get('period_start'))
        period_end     = _parse_date(get('period_end'))
        kwh_raw        = get('kwh').replace(',', '')
        state          = get('state')
        egrid_subregion = get('egrid_subregion')
        tariff_code    = get('tariff_code')
        tariff_desc    = get('tariff_description')
        utility_name   = get('utility_name')
        read_type      = get('read_type')
        total_charges  = get('total_charges')
        service_address = get('service_address')

        # Parse kWh
        try:
            kwh = Decimal(kwh_raw) if kwh_raw else None
        except Exception:
            kwh = None
            parse_errors.append(f'Cannot parse kWh: {repr(kwh_raw)}')
            parse_status = 'ERROR'
            errors += 1

        if period_start is None:
            parse_errors.append('Missing billing period start date')
            parse_status = 'ERROR'
        if period_end is None:
            parse_errors.append('Missing billing period end date')
            parse_status = 'ERROR'

        # Get eGRID emission factor
        ef_data = get_egrid_factor(state=state, subregion=egrid_subregion)
        ef_factor = ef_data['factor']  # kg CO2e per kWh
        ef_label = ef_data.get('label', ef_data.get('subregion', 'US Average'))
        subregion_used = ef_data.get('subregion', 'US_AVG')

        # Compute CO2e
        co2e_kg = (kwh * ef_factor).quantize(Decimal('0.0001')) if kwh else Decimal('0')

        # Proration info for display
        proration_info = ''
        if kwh and period_start and period_end:
            allocations = _prorate_to_calendar_months(kwh, period_start, period_end)
            proration_parts = [f'{y}-{m:02d}: {k:.1f} kWh' for y, m, k in allocations]
            proration_info = ' | Calendar split: ' + ', '.join(proration_parts)

        # Auto-flags
        flag_reasons = _auto_flags(kwh, period_start, period_end, read_type)
        review_status = 'FLAGGED' if (flag_reasons or parse_status != 'OK') else 'PENDING'

        raw_rec = RawRecord(
            batch=batch,
            row_index=idx,
            raw_data=raw_data,
            parse_status=parse_status,
            parse_errors=parse_errors,
        )
        raw_records_to_create.append(raw_rec)

        er = EmissionRecord(
            tenant=tenant,
            batch=batch,
            raw_record=None,
            source_type=EmissionRecord.SourceType.UTILITY_ELECTRICITY,
            source_id=meter_id or account_number,
            source_period_start=period_start,
            source_period_end=period_end,
            activity_description=(
                f"Electricity | Meter: {meter_id} | {utility_name} | "
                f"Tariff: {tariff_code} {tariff_desc} | {service_address}"
                f"{proration_info}"
            ),
            scope=EmissionRecord.Scope.SCOPE_2,
            ghg_category='Purchased Electricity',
            ghg_category_code='S2',
            activity_value=kwh or Decimal('0'),
            activity_unit='kWh',
            original_value=kwh,
            original_unit='kWh',
            emission_factor=ef_factor,
            emission_factor_source=f'EPA eGRID2022 {subregion_used} ({ef_label})',
            emission_factor_year=2022,
            co2e_kg=co2e_kg,
            country_code='US',
            region=f'{state} / {subregion_used}' if state else subregion_used,
            facility_id=meter_id or account_number,
            facility_name=service_address[:255] if service_address else '',
            review_status=review_status,
            flag_reasons=flag_reasons,
        )
        emission_records_to_create.append(er)
        if parse_status == 'OK' and not flag_reasons:
            created += 1
        elif flag_reasons:
            warnings += 1

    RawRecord.objects.bulk_create(raw_records_to_create)
    for er, rr in zip(emission_records_to_create, raw_records_to_create):
        er.raw_record = rr
    EmissionRecord.objects.bulk_create(emission_records_to_create)

    log.append(f'Created {created} clean, {warnings} flagged, {errors} error records')
    return {
        'created': created,
        'warnings': warnings,
        'errors': errors,
        'log': log,
        'row_count': len(emission_records_to_create),
    }
