"""
Corporate travel ingestion parser — Concur-style CSV export.

Format: SAP Concur standard expense/travel report CSV.
Handles three segment types: AIR, HOTEL, CAR/RAIL/TAXI.

Design decisions documented in DECISIONS.md:
- Concur chosen over Navan because it is the dominant enterprise platform
  (~80M users per SAP's own figures). Navan has similar field structure.
- Airport great-circle distances are computed via the Haversine formula using
  the OpenFlights dataset (bundled in data/airports.csv — ~7,000 airports).
- We apply the ICAO routing factor (1.09×) to convert great-circle to
  representative flown distance.
- DEFRA 2023 factors WITH Radiative Forcing Index (×1.9) are used. This is
  debated in the ESG community; some clients want without-RFI figures.
  We store the factor source so analysts can identify which approach was used.
- Cabin class falls back to ECONOMY if not specified (flagged for review).

Scope: Scope 3, Category 6 (Business Travel).
"""

import io
import math
import logging
from datetime import date
from decimal import Decimal

import pandas as pd

from core.models import IngestionBatch, RawRecord, EmissionRecord
from .emission_factors import (
    get_flight_factor, get_hotel_factor, get_ground_factor,
    FLIGHT_ROUTING_FACTOR, CABIN_CLASS_MAP
)

logger = logging.getLogger(__name__)


# ── Airport coordinates (subset — full DB loaded from airports.csv) ────────
# Bundled fallback for the most common airports in business travel
# Full dataset loaded from data/airports.csv on first call
_AIRPORT_DB = None

AIRPORT_FALLBACK = {
    'ORD': (41.9742, -87.9073), 'LHR': (51.4775, -0.4614),
    'JFK': (40.6413, -73.7781), 'SFO': (37.6213, -122.3790),
    'LAX': (33.9425, -118.4081), 'BOS': (42.3656, -71.0096),
    'ATL': (33.6367, -84.4281), 'DFW': (32.8998, -97.0403),
    'EWR': (40.6895, -74.1745), 'CDG': (49.0097, 2.5479),
    'FRA': (50.0379, 8.5622),   'NRT': (35.7720, 140.3929),
    'HND': (35.5494, 139.7798), 'PEK': (40.0799, 116.6031),
    'SYD': (-33.9461, 151.1772),'DXB': (25.2532, 55.3657),
    'AMS': (52.3105, 4.7683),   'MAD': (40.4936, -3.5668),
    'FCO': (41.7999, 12.2462),  'HKG': (22.3080, 113.9185),
    'SIN': (1.3644, 103.9915),  'ICN': (37.4602, 126.4407),
    'MIA': (25.7959, -80.2870), 'ORD': (41.9742, -87.9073),
    'DEN': (39.8561, -104.6737),'SEA': (47.4502, -122.3088),
    'PHX': (33.4373, -112.0078),'MSP': (44.8820, -93.2218),
    'DTW': (42.2124, -83.3534), 'IAD': (38.9531, -77.4565),
    'CLT': (35.2140, -80.9431), 'MDW': (41.7868, -87.7522),
}


def _load_airport_db(airports_csv_path: str) -> dict:
    """Load OpenFlights airports.csv into an IATA-keyed dict."""
    try:
        df = pd.read_csv(
            airports_csv_path,
            header=None,
            names=['id', 'name', 'city', 'country', 'iata', 'icao',
                   'lat', 'lon', 'alt', 'tz', 'dst', 'tz_name', 'type', 'source'],
            dtype=str, keep_default_na=False
        )
        db = {}
        for _, row in df.iterrows():
            iata = row['iata'].strip().upper()
            if iata and len(iata) == 3:
                try:
                    db[iata] = (float(row['lat']), float(row['lon']))
                except ValueError:
                    pass
        return db
    except Exception as e:
        logger.warning(f'Could not load airports.csv: {e}')
        return {}


def _get_airport_db() -> dict:
    """Lazy-load airport coordinates database."""
    global _AIRPORT_DB
    if _AIRPORT_DB is None:
        import os
        csv_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'airports.csv'
        )
        _AIRPORT_DB = _load_airport_db(os.path.abspath(csv_path))
        # Merge fallback for any missing airports
        for code, coords in AIRPORT_FALLBACK.items():
            if code not in _AIRPORT_DB:
                _AIRPORT_DB[code] = coords
    return _AIRPORT_DB


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points using the Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _flight_distance_km(origin: str, destination: str) -> tuple:
    """
    Compute representative flight distance from IATA codes.
    Returns (distance_km_with_routing, great_circle_km, error_message).
    """
    db = _get_airport_db()
    origin = origin.strip().upper()
    destination = destination.strip().upper()

    origin_coords = db.get(origin)
    dest_coords = db.get(destination)

    if not origin_coords:
        return None, None, f'Unknown origin airport: {origin}'
    if not dest_coords:
        return None, None, f'Unknown destination airport: {destination}'

    gc_km = _haversine_km(*origin_coords, *dest_coords)
    # Apply ICAO routing factor (1.09) to account for airways and ATC routing
    routed_km = gc_km * float(FLIGHT_ROUTING_FACTOR)
    return routed_km, gc_km, None


COLUMN_ALIASES = {
    'trip_id': 'trip_id', 'trip id': 'trip_id',
    'booking_id': 'booking_id', 'booking id': 'booking_id',
    'employee_id': 'employee_id', 'employee id': 'employee_id', 'traveler_employee_id': 'employee_id',
    'employee_name': 'employee_name', 'employee name': 'employee_name',
    'traveler_name': 'employee_name', 'traveler name': 'employee_name',
    'department': 'department', 'traveler_department': 'department',
    'cost_center': 'cost_center', 'traveler_cost_center': 'cost_center',
    'segment_type': 'segment_type', 'expense_type': 'segment_type',
    'travel_date': 'travel_date', 'transaction_date': 'travel_date',
    'origin_airport_code': 'origin', 'origin airport code': 'origin',
    'city_from': 'origin_city', 'city from': 'origin_city',
    'destination_airport_code': 'destination', 'destination airport code': 'destination',
    'city_to': 'dest_city', 'city to': 'dest_city',
    'cabin_class': 'cabin_class', 'cabin class': 'cabin_class',
    'cabin_class_code': 'cabin_class_code',
    'airline_code': 'airline', 'airline code': 'airline',
    'airline_name': 'airline_name',
    'flight_number': 'flight_number',
    'ticket_cost_usd': 'ticket_cost', 'ticket cost usd': 'ticket_cost',
    'check_in_date': 'check_in', 'check in date': 'check_in', 'hotel check-in': 'check_in',
    'check_out_date': 'check_out', 'check out date': 'check_out', 'hotel check-out': 'check_out',
    'nights': 'nights',
    'hotel_name': 'hotel_name', 'hotel name': 'hotel_name',
    'city': 'city',
    'country': 'country',
    'nightly_rate_usd': 'nightly_rate', 'nightly rate usd': 'nightly_rate',
    'total_cost_usd': 'total_cost', 'total cost usd': 'total_cost',
    'vehicle_type': 'vehicle_type', 'vehicle type': 'vehicle_type',
    'miles_driven': 'miles_driven', 'miles driven': 'miles_driven',
    'vendor_name': 'vendor_name', 'vendor name': 'vendor_name',
}


def _normalize_header(col: str) -> str:
    return col.strip().lower().rstrip('.')


def _map_columns(df: pd.DataFrame) -> dict:
    mapping = {}
    for col in df.columns:
        # Try underscore version first (e.g. 'Segment_Type' -> 'segment_type')
        key = COLUMN_ALIASES.get(_normalize_header(col))
        if not key:
            # Try space version (e.g. 'segment type')
            key = COLUMN_ALIASES.get(_normalize_header(col).replace('_', ' '))
        if key and key not in mapping:
            mapping[key] = col
    return mapping


def _parse_date(value: str):
    if not value or not value.strip():
        return None
    from datetime import datetime
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _normalize_cabin(raw: str) -> str:
    if not raw:
        return 'ECONOMY'
    raw_up = raw.strip().upper()
    return CABIN_CLASS_MAP.get(raw_up, CABIN_CLASS_MAP.get(raw.strip().title().replace(' ', '_'), 'ECONOMY'))


def _parse_segment(row: dict, col_map: dict) -> tuple:
    """
    Returns (segment_type, parse_errors) where segment_type is one of:
    AIR, HOTEL, CAR, RAIL, TAXI, or None if unrecognized.
    """
    def get(key, default=''):
        col = col_map.get(key)
        return row.get(col, default).strip() if col else default

    raw_type = get('segment_type').upper()
    if 'AIR' in raw_type or 'FLIGHT' in raw_type:
        return 'AIR', []
    if 'HOTEL' in raw_type or 'LODGING' in raw_type:
        return 'HOTEL', []
    if 'CAR' in raw_type or 'RENTAL' in raw_type or 'RENT' in raw_type:
        return 'CAR', []
    if 'RAIL' in raw_type or 'TRAIN' in raw_type:
        return 'RAIL', []
    if 'TAXI' in raw_type or 'RIDESHARE' in raw_type or 'GROUND' in raw_type or 'TRANSPORT' in raw_type:
        return 'TAXI', []
    return None, [f'Unrecognized segment type: {repr(raw_type)}']


def parse_travel_file(file_obj, batch: IngestionBatch, tenant) -> dict:
    """
    Parse a Concur-style travel CSV and create EmissionRecord rows.
    Each booking segment (flight, hotel, car) produces one EmissionRecord.
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
        flag_reasons = []

        def get(key, default=''):
            col = col_map.get(key)
            return raw_data.get(col, default).strip() if col else default

        segment_type, seg_errors = _parse_segment(raw_data, col_map)
        parse_errors.extend(seg_errors)

        employee_id  = get('employee_id')
        employee_name = get('employee_name')
        department   = get('department')
        cost_center  = get('cost_center')
        trip_id      = get('trip_id')
        booking_id   = get('booking_id')

        # ── AIR ──────────────────────────────────────────────────────────
        if segment_type == 'AIR':
            travel_date  = _parse_date(get('travel_date'))
            origin       = get('origin')
            destination  = get('destination')
            origin_city  = get('origin_city')
            dest_city    = get('dest_city')
            cabin_raw    = get('cabin_class') or get('cabin_class_code')
            airline      = get('airline') or get('airline_name')
            flight_num   = get('flight_number')

            cabin = _normalize_cabin(cabin_raw)
            if not cabin_raw:
                flag_reasons.append('Cabin class not specified — defaulting to Economy')

            if not origin or not destination:
                parse_errors.append('Missing origin or destination airport code')
                parse_status = 'ERROR'
                errors += 1
                distance_km = None
                gc_km = None
                dist_error = 'Missing IATA codes'
            else:
                distance_km, gc_km, dist_error = _flight_distance_km(origin, destination)
                if dist_error:
                    flag_reasons.append(f'Distance calc: {dist_error}')
                    distance_km = None

            ef_per_pkm = Decimal('0')
            haul_type = 'LONG'
            if distance_km:
                ef_per_pkm, haul_type, cabin = get_flight_factor(distance_km, cabin)

            co2e_kg = (Decimal(str(distance_km)) * ef_per_pkm).quantize(Decimal('0.0001')) \
                if distance_km else Decimal('0')

            desc = (f"Flight {origin}→{destination} ({haul_type.lower()}-haul, {cabin.lower()}) | "
                    f"{airline} {flight_num} | {employee_name} ({department})")
            if gc_km:
                desc += f" | GC: {gc_km:.0f}km, Flown: {distance_km:.0f}km (×{FLIGHT_ROUTING_FACTOR})"

            if not distance_km:
                flag_reasons.append('Could not compute flight distance — CO2e is 0')

            source_type = EmissionRecord.SourceType.TRAVEL_FLIGHT
            activity_value = Decimal(str(distance_km)) if distance_km else Decimal('0')
            activity_unit = 'km'
            ef_source = f'DEFRA 2023 -- {haul_type} {cabin} with RFI*1.9'
            period_start = travel_date
            period_end = travel_date
            source_id = booking_id or trip_id
            facility_id = cost_center
            region = f'{origin}->{destination}'
            country = ''  # not applicable for flight segment

        # ── HOTEL ─────────────────────────────────────────────────────────
        elif segment_type == 'HOTEL':
            check_in     = _parse_date(get('check_in'))
            check_out    = _parse_date(get('check_out'))
            nights_raw   = get('nights')
            hotel_name   = get('hotel_name')
            city         = get('city')
            country      = get('country')

            # Prefer computed nights over stated nights
            if check_in and check_out:
                nights = (check_out - check_in).days
                if nights_raw:
                    try:
                        stated_nights = int(nights_raw)
                        if stated_nights != nights:
                            flag_reasons.append(
                                f'Stated nights ({stated_nights}) ≠ computed nights ({nights})'
                            )
                    except ValueError:
                        pass
            else:
                nights = int(nights_raw) if nights_raw else 0
                if not check_in:
                    flag_reasons.append('Missing check-in date')

            if nights <= 0:
                flag_reasons.append('Zero or negative hotel nights')

            ef_per_night = get_hotel_factor(country)
            co2e_kg = (Decimal(str(nights)) * ef_per_night).quantize(Decimal('0.0001'))

            desc = (f"Hotel: {hotel_name or '?'}, {city or ''} {country or ''} | "
                    f"{nights} nights | {employee_name} ({department})")

            source_type = EmissionRecord.SourceType.TRAVEL_HOTEL
            activity_value = Decimal(str(nights))
            activity_unit = 'nights'
            ef_source = f'Cornell CHSB 2023 — {country or "GLOBAL"} hotel average'
            ef_per_pkm = ef_per_night
            period_start = check_in
            period_end = check_out
            source_id = booking_id or trip_id
            facility_id = cost_center
            region = f'{city}, {country}' if city else country
            ef_per_pkm = ef_per_night

        # ── CAR / TAXI / RAIL ─────────────────────────────────────────────
        elif segment_type in ('CAR', 'TAXI', 'RAIL'):
            travel_date  = _parse_date(get('travel_date'))
            vehicle_type = get('vehicle_type')
            miles_raw    = get('miles_driven')
            city         = get('city')
            country      = get('country')
            vendor       = get('vendor_name')

            # Convert miles to km
            km_driven = None
            if miles_raw:
                try:
                    miles = Decimal(miles_raw.replace(',', ''))
                    km_driven = (miles * Decimal('1.60934')).quantize(Decimal('0.001'))
                except Exception:
                    flag_reasons.append(f'Cannot parse miles: {repr(miles_raw)}')

            if km_driven is None:
                flag_reasons.append('Distance not available — CO2e is 0')

            ef_ground = get_ground_factor(vehicle_type, segment_type)
            co2e_kg = (km_driven * ef_ground).quantize(Decimal('0.0001')) \
                if km_driven else Decimal('0')

            mode_label = {'CAR': 'Car Rental', 'TAXI': 'Taxi/Rideshare', 'RAIL': 'Rail'}[segment_type]
            if km_driven:
                desc = f"{mode_label}: {vendor or vehicle_type or '?'} | {float(km_driven):.1f}km | {employee_name} ({department})"
            else:
                desc = f"{mode_label}: {vendor or '?'} | {employee_name} ({department})"

            source_type = EmissionRecord.SourceType.TRAVEL_GROUND
            activity_value = km_driven or Decimal('0')
            activity_unit = 'km'
            ef_per_pkm = ef_ground
            ef_source = f'DEFRA 2023 — {segment_type}'
            period_start = travel_date
            period_end = travel_date
            source_id = booking_id or trip_id
            facility_id = cost_center
            region = f'{city}, {country}' if city else country

        else:
            # Unrecognized segment — still create raw record
            parse_status = 'ERROR'
            errors += 1

            raw_rec = RawRecord(
                batch=batch, row_index=idx, raw_data=raw_data,
                parse_status='ERROR', parse_errors=parse_errors,
            )
            raw_records_to_create.append(raw_rec)
            continue

        review_status = 'FLAGGED' if (flag_reasons or parse_status != 'OK') else 'PENDING'

        raw_rec = RawRecord(
            batch=batch, row_index=idx, raw_data=raw_data,
            parse_status=parse_status, parse_errors=parse_errors,
        )
        raw_records_to_create.append(raw_rec)

        er = EmissionRecord(
            tenant=tenant,
            batch=batch,
            raw_record=None,
            source_type=source_type,
            source_id=source_id,
            source_period_start=period_start,
            source_period_end=period_end,
            activity_description=desc,
            scope=EmissionRecord.Scope.SCOPE_3,
            ghg_category='Business Travel',
            ghg_category_code='S3C6',
            activity_value=activity_value,
            activity_unit=activity_unit,
            original_value=activity_value,
            original_unit=activity_unit,
            emission_factor=ef_per_pkm,
            emission_factor_source=ef_source,
            emission_factor_year=2023,
            co2e_kg=co2e_kg,
            country_code=country[:3] if country else '',
            region=region or '',
            facility_id=facility_id or '',
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
