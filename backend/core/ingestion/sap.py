"""
SAP flat-file ingestion parser.

Handles: semicolon-delimited ALV exports from ME2N/ME2L/MB51 transactions.
Both German (;-delimited, DD.MM.YYYY dates, German decimal format 1.234,56)
and English header variants are supported.

Design decisions documented in DECISIONS.md:
- We chose ALV flat-file over IDoc or OData because sustainability teams
  universally export via SAP List Viewer — it requires no middleware.
- We handle fuel material groups (Scope 1) only. Procurement spend (Scope 3 Cat 1)
  is stubbed — see TRADEOFFS.md.
- German decimal format (period=thousands, comma=decimal) must be handled before
  any numeric parsing.
"""

import re
import io
import csv
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import pandas as pd

from core.models import IngestionBatch, RawRecord, EmissionRecord
from .emission_factors import (
    SAP_MATERIAL_GROUP_MAP, SAP_UOM_CONVERSION,
    get_fuel_factor, FUEL_FACTORS
)

logger = logging.getLogger(__name__)


# ── Column name aliases (German ↔ English ↔ abbreviated) ─────────────────
# Maps any of these column names to a canonical internal key.
COLUMN_ALIASES = {
    # Purchase order / document number
    'purchasing doc.': 'doc_number',
    'einkaufsbeleg': 'doc_number',
    'mat. doc.': 'doc_number',
    'material document': 'doc_number',
    # Item
    'item': 'item',
    'position': 'item',
    # Posting / document date
    'posting date': 'posting_date',
    'pstng date': 'posting_date',
    'document date': 'posting_date',
    'belegdatum': 'posting_date',
    'buchungsdatum': 'posting_date',
    'doc. date': 'posting_date',
    # Plant
    'plant': 'plant',
    'werk': 'plant',
    # Material group
    'material group': 'material_group',
    'materialgruppe': 'material_group',
    'mat. group': 'material_group',
    # Material number
    'material': 'material',
    # Material description
    'material description': 'description',
    'materialkurztext': 'description',
    'short text': 'description',
    'kurztext': 'description',
    'bezeichnung': 'description',
    # Quantity
    'order qty': 'quantity',
    'order quantity': 'quantity',
    'bestellmenge': 'quantity',
    'quantity': 'quantity',
    'menge': 'quantity',
    'qty in une': 'quantity',
    # Unit of measure
    'order unit': 'uom',
    'unit of measure': 'uom',
    'bestellmengeneinheit': 'uom',
    'me': 'uom',
    'mengeneinheit': 'uom',
    'unit of entry': 'uom',
    # Cost center
    'cost center': 'cost_center',
    'kostenstelle': 'cost_center',
    # Vendor
    'vendor': 'vendor',
    'lieferant': 'vendor',
    'vendor name': 'vendor_name',
    'lieferantenname': 'vendor_name',
    # Currency
    'currency': 'currency',
    'währung': 'currency',
    'curr.': 'currency',
    # Net value
    'net value': 'net_value',
    'nettowert': 'net_value',
    'amount in lc': 'net_value',
    # Movement type (MB51)
    'mvt type': 'movement_type',
    'movement type': 'movement_type',
    'bewegungsart': 'movement_type',
    # Company code
    'company code': 'company_code',
    'buchungskreis': 'company_code',
    'bukrs': 'company_code',
}

# SAP movement types that indicate fuel consumption (goods issue)
FUEL_MOVEMENT_TYPES = {
    '201',  # Goods issue to cost center
    '261',  # Goods issue to production order
    '551',  # Scrapping
    '101',  # Goods receipt (MB51 — already received)
}


def _normalize_header(col: str) -> str:
    """Lowercase and strip a column header for alias lookup."""
    return col.strip().lower().rstrip('.')


def _detect_delimiter(text_sample: str) -> str:
    """
    Detect whether the file uses semicolon (European SAP) or comma delimiter.
    Semicolons dominate in DE/AT/CH SAP systems.
    """
    semicolons = text_sample.count(';')
    commas = text_sample.count(',')
    return ';' if semicolons > commas else ','


def _parse_german_number(value: str) -> Optional[Decimal]:
    """
    Parse German-format numbers where period=thousands, comma=decimal.
    '1.234,56' → Decimal('1234.56')
    '10.000'   → Decimal('10000') (ten thousand)
    '1,459'    → Decimal('1.459')
    """
    if not value or not value.strip():
        return None
    value = value.strip()
    # Remove thousands separators (period in German format)
    # Then replace decimal comma with period
    cleaned = value.replace('.', '').replace(',', '.')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(value: str) -> Optional[date]:
    """
    Parse SAP date formats: DD.MM.YYYY, YYYYMMDD, MM/DD/YYYY.
    """
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ('%d.%m.%Y', '%Y%m%d', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _map_columns(df: pd.DataFrame) -> dict:
    """
    Build a mapping from canonical key → actual DataFrame column name.
    """
    mapping = {}
    for col in df.columns:
        normalized = _normalize_header(col)
        canonical = COLUMN_ALIASES.get(normalized)
        if canonical and canonical not in mapping:
            mapping[canonical] = col
    return mapping


def _identify_fuel_type(material_group: str, description: str) -> Optional[str]:
    """
    Identify fuel type from SAP material group code or description text.
    Returns a key from FUEL_FACTORS or None if not a fuel.
    """
    if material_group:
        mg_upper = material_group.strip().upper()
        fuel = SAP_MATERIAL_GROUP_MAP.get(mg_upper)
        if fuel:
            return fuel
        # Handle ENG001 → electricity (not fuel — don't process as Scope 1)
        if mg_upper == 'ENG001':
            return None

    # Fallback: text-based matching
    if description:
        desc_lower = description.lower()
        if any(k in desc_lower for k in ['diesel', 'gasoil', 'gas oil']):
            return 'DIESEL'
        if any(k in desc_lower for k in ['benzin', 'petrol', 'gasoline', 'unleaded']):
            return 'PETROL'
        if any(k in desc_lower for k in ['erdgas', 'natural gas', 'methane']):
            return 'NATURAL_GAS'
        if any(k in desc_lower for k in ['flüssiggas', 'lpg', 'propan', 'butan']):
            return 'LPG'
        if any(k in desc_lower for k in ['heizöl', 'heating oil', 'fuel oil']):
            return 'HEATING_OIL'
        if any(k in desc_lower for k in ['kerosin', 'kerosin', 'jet', 'aviation']):
            return 'JET_FUEL'
    return None


def _auto_flags(record: dict, fuel_type: str, activity_value: Decimal,
                posting_date: date) -> list:
    """Generate a list of auto-detected issues for analyst review."""
    flags = []
    if activity_value is None or activity_value <= 0:
        flags.append('Zero or negative activity value — check source data')
    if posting_date and posting_date > date.today():
        flags.append(f'Future posting date: {posting_date}')
    if posting_date and (date.today() - posting_date).days > 730:
        flags.append(f'Posting date is more than 2 years ago: {posting_date}')
    if fuel_type is None:
        flags.append('Could not identify fuel type — emission factor not applied')
    return flags


def parse_sap_file(file_obj, batch: IngestionBatch, tenant) -> dict:
    """
    Main entry point. Parse a SAP flat-file export and create EmissionRecord rows.
    
    Returns: {'created': int, 'warnings': int, 'errors': int, 'log': list}
    """
    from django.utils import timezone

    log = []
    created = warnings = errors = 0

    # Read raw bytes → detect encoding
    raw_bytes = file_obj.read()
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1', 'utf-8'):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw_bytes.decode('latin-1', errors='replace')

    # Detect delimiter from first 2KB
    delimiter = _detect_delimiter(text[:2000])
    log.append(f'Detected delimiter: {repr(delimiter)}')

    # Parse with pandas
    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            on_bad_lines='warn',
        )
    except Exception as e:
        return {'created': 0, 'warnings': 0, 'errors': 1, 'log': [f'Parse failed: {e}']}

    df.columns = [c.strip() for c in df.columns]
    col_map = _map_columns(df)
    log.append(f'Identified columns: {list(col_map.keys())}')
    log.append(f'Total rows: {len(df)}')

    emission_records_to_create = []
    raw_records_to_create = []

    for idx, row in df.iterrows():
        raw_data = row.to_dict()
        parse_errors = []
        parse_status = 'OK'

        # ── Extract fields ──────────────────────────────────────────────
        def get(key):
            col = col_map.get(key)
            return raw_data.get(col, '').strip() if col else ''

        doc_number     = get('doc_number')
        posting_date   = _parse_date(get('posting_date'))
        plant          = get('plant')
        material_group = get('material_group')
        description    = get('description')
        quantity_raw   = get('quantity')
        uom_raw        = get('uom').upper()
        cost_center    = get('cost_center')
        vendor         = get('vendor')
        vendor_name    = get('vendor_name')
        movement_type  = get('movement_type')

        # ── Skip rows that are not fuel consumption ───────────────────
        # If movement_type is present and not a fuel-consumption type, skip
        if movement_type and movement_type not in FUEL_MOVEMENT_TYPES:
            continue

        # ── Parse quantity ──────────────────────────────────────────────
        quantity = _parse_german_number(quantity_raw)
        if quantity is None:
            parse_errors.append(f'Cannot parse quantity: {repr(quantity_raw)}')
            parse_status = 'ERROR'
            errors += 1

        # ── Identify fuel type ──────────────────────────────────────────
        fuel_type = _identify_fuel_type(material_group, description)

        # ── Unit conversion ─────────────────────────────────────────────
        uom_info = SAP_UOM_CONVERSION.get(uom_raw)
        if uom_info is None:
            parse_errors.append(f'Unknown unit of measure: {repr(uom_raw)}')
            parse_status = 'WARN' if parse_status == 'OK' else parse_status
            warnings += 1

        # ── Compute activity value in canonical unit ────────────────────
        activity_value = None
        activity_unit = uom_raw
        if quantity is not None and uom_info:
            activity_value = quantity * uom_info['factor']
            activity_unit = uom_info['canonical']

        # ── Get emission factor ─────────────────────────────────────────
        ef_info = get_fuel_factor(fuel_type) if fuel_type else None
        if ef_info is None and fuel_type is not None:
            parse_errors.append(f'No emission factor for fuel type: {fuel_type}')
            parse_status = 'WARN' if parse_status == 'OK' else parse_status

        # ── Compute CO2e ────────────────────────────────────────────────
        co2e_kg = Decimal('0')
        emission_factor = Decimal('0')
        ef_source = 'N/A'
        if ef_info and activity_value is not None:
            # For gas: factor is per Nm3; for liquid: per liter
            # Both already in canonical units after conversion above
            emission_factor = ef_info['factor']
            ef_source = ef_info['source']
            co2e_kg = activity_value * emission_factor

        # ── Auto-flags ──────────────────────────────────────────────────
        flag_reasons = _auto_flags(
            raw_data, fuel_type, activity_value, posting_date
        )
        review_status = 'FLAGGED' if flag_reasons else 'PENDING'

        if parse_status == 'ERROR':
            review_status = 'FLAGGED'
            flag_reasons.insert(0, 'Parse error — see parse_errors field')

        # ── Create raw record ───────────────────────────────────────────
        raw_rec = RawRecord(
            batch=batch,
            row_index=idx,
            raw_data=raw_data,
            parse_status=parse_status,
            parse_errors=parse_errors,
        )
        raw_records_to_create.append(raw_rec)

        # ── Create emission record ──────────────────────────────────────
        er = EmissionRecord(
            tenant=tenant,
            batch=batch,
            raw_record=None,  # set after bulk_create below
            source_type=EmissionRecord.SourceType.SAP_FUEL,
            source_id=doc_number,
            source_period_start=posting_date,
            source_period_end=posting_date,
            activity_description=(
                f"{description or 'Fuel purchase'} | "
                f"Plant: {plant} | Vendor: {vendor_name or vendor}"
            ),
            scope=EmissionRecord.Scope.SCOPE_1,
            ghg_category='Stationary Combustion / Mobile Combustion',
            ghg_category_code='S1',
            activity_value=activity_value or Decimal('0'),
            activity_unit=activity_unit,
            original_value=quantity,
            original_unit=uom_raw,
            emission_factor=emission_factor,
            emission_factor_source=ef_source,
            emission_factor_year=2023,
            co2e_kg=co2e_kg,
            country_code='',  # Enriched from plant lookup in real deployment
            region='',
            facility_id=plant,
            facility_name=plant,
            review_status=review_status,
            flag_reasons=flag_reasons,
        )
        emission_records_to_create.append(er)
        if parse_status == 'OK' and not flag_reasons:
            created += 1
        elif flag_reasons:
            warnings += 1

    # ── Bulk insert ─────────────────────────────────────────────────────
    RawRecord.objects.bulk_create(raw_records_to_create)
    # Link raw records to emission records
    for er, rr in zip(emission_records_to_create, raw_records_to_create):
        er.raw_record = rr
    EmissionRecord.objects.bulk_create(emission_records_to_create)

    log.append(f'Created {created} records, {warnings} warnings, {errors} errors')
    return {
        'created': created,
        'warnings': warnings,
        'errors': errors,
        'log': log,
        'row_count': len(emission_records_to_create),
    }
