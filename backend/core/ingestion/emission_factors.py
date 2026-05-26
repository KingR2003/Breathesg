"""
Emission factor lookup tables.

Sources:
- Fuel combustion: DEFRA/BEIS UK Greenhouse Gas Reporting Conversion Factors 2023
  and EPA Emission Factors for Greenhouse Gas Inventories (April 2024)
- Electricity: EPA eGRID2022 subregion CO2e factors (released Jan 2024)
- Business travel flights: DEFRA 2023, including RFI × 1.9 for non-CO2 warming effects
- Hotels: Cornell Hotel Sustainability Benchmarking Index 2023
- Ground transport: DEFRA 2023

All factors in kg CO2e per stated unit.
"""

from decimal import Decimal

# ── Fuel combustion (Scope 1) ──────────────────────────────────────────────
# Source: DEFRA 2023 / EPA 2024 Emission Factors for GHG Inventories
# Unit: kg CO2e per LITER of fuel
FUEL_FACTORS = {
    # Diesel / Gas oil
    'DIESEL':       {'factor': Decimal('2.6878'), 'unit': 'L', 'source': 'DEFRA 2023'},
    'GASOIL':       {'factor': Decimal('2.6878'), 'unit': 'L', 'source': 'DEFRA 2023'},
    # Petrol / Gasoline
    'PETROL':       {'factor': Decimal('2.3105'), 'unit': 'L', 'source': 'DEFRA 2023'},
    'GASOLINE':     {'factor': Decimal('2.3105'), 'unit': 'L', 'source': 'DEFRA 2023'},
    'BENZIN':       {'factor': Decimal('2.3105'), 'unit': 'L', 'source': 'DEFRA 2023'},
    # Natural gas — factor per m³ at standard conditions (0°C, 1 atm)
    # Note: we store in m³ → factor below; 1 Nm³ ≈ 2.0 kg CO2e
    'NATURAL_GAS':  {'factor': Decimal('2.0440'), 'unit': 'Nm3', 'source': 'DEFRA 2023'},
    'ERDGAS':       {'factor': Decimal('2.0440'), 'unit': 'Nm3', 'source': 'DEFRA 2023'},
    # LPG (propane/butane mix)
    'LPG':          {'factor': Decimal('1.5599'), 'unit': 'L',   'source': 'DEFRA 2023'},
    # Heating oil / fuel oil (light)
    'HEATING_OIL':  {'factor': Decimal('2.5202'), 'unit': 'L',   'source': 'DEFRA 2023'},
    'HEIZOEL':      {'factor': Decimal('2.5202'), 'unit': 'L',   'source': 'DEFRA 2023'},
    # Aviation / jet fuel (kerosene)
    'JET_FUEL':     {'factor': Decimal('2.5397'), 'unit': 'L',   'source': 'DEFRA 2023'},
    'KEROSIN':      {'factor': Decimal('2.5397'), 'unit': 'L',   'source': 'DEFRA 2023'},
    # HFO (Heavy Fuel Oil)
    'HFO':          {'factor': Decimal('3.1790'), 'unit': 'L',   'source': 'DEFRA 2023'},
}

# SAP material group → fuel type mapping
# These are representative patterns; real clients would provide their own mapping
SAP_MATERIAL_GROUP_MAP = {
    # eCl@ss / SAP standard
    'RO1100': 'DIESEL',      # Kraftstoffe (general fuel)
    'RO1110': 'DIESEL',      # Dieselkraftstoff
    'RO1120': 'PETROL',      # Benzin
    'RO1130': 'NATURAL_GAS', # Erdgas
    'RO1140': 'LPG',         # Flüssiggas
    'RO1150': 'HEATING_OIL', # Heizöl
    'RO1160': 'JET_FUEL',    # Kerosin
    'ENG001': None,          # Electricity — handled separately as Scope 2
    'ENG002': 'NATURAL_GAS',
    'ENG003': 'HEATING_OIL',
    'FUEL01': 'DIESEL',
    'FUEL02': 'PETROL',
    'FUEL03': 'JET_FUEL',
    # Numeric patterns
    '19110': 'DIESEL',
    '19120': 'PETROL',
}

# SAP Unit of Measure → canonical unit + conversion to canonical
# canonical: liquid fuels → liters, gas → Nm³, energy → kWh
SAP_UOM_CONVERSION = {
    'L':    {'canonical': 'L',   'factor': Decimal('1.0')},
    'LTR':  {'canonical': 'L',   'factor': Decimal('1.0')},
    'KL':   {'canonical': 'L',   'factor': Decimal('1000.0')},
    'GAL':  {'canonical': 'L',   'factor': Decimal('3.78541')},   # US gallon
    'M3':   {'canonical': 'Nm3', 'factor': Decimal('1.0')},
    'NM3':  {'canonical': 'Nm3', 'factor': Decimal('1.0')},
    'KG':   {'canonical': 'KG',  'factor': Decimal('1.0')},
    'T':    {'canonical': 'KG',  'factor': Decimal('1000.0')},
    'TO':   {'canonical': 'KG',  'factor': Decimal('907.185')},   # short ton
    'MWH':  {'canonical': 'kWh', 'factor': Decimal('1000.0')},
    'KWH':  {'canonical': 'kWh', 'factor': Decimal('1.0')},
    'GJ':   {'canonical': 'kWh', 'factor': Decimal('277.778')},
    'ST':   {'canonical': 'EA',  'factor': Decimal('1.0')},       # Stück (each)
    'EA':   {'canonical': 'EA',  'factor': Decimal('1.0')},
}


# ── Electricity / Scope 2 (location-based) ────────────────────────────────
# Source: EPA eGRID2022 (released January 2024)
# Unit: kg CO2e per kWh (converted from lb CO2e/MWh ÷ 2204.62)
# Formula: lb_per_MWh × 0.453592 / 1000 = kg per kWh

def lb_mwh_to_kg_kwh(lb_per_mwh: float) -> Decimal:
    return Decimal(str(round(lb_per_mwh * 0.453592 / 1000, 8)))

EGRID_FACTORS = {
    # Subregion: (kg CO2e/kWh, states covered)
    'AKGD': {'factor': lb_mwh_to_kg_kwh(1094.9), 'label': 'Alaska Grid'},
    'CAMX': {'factor': lb_mwh_to_kg_kwh(520.0),  'label': 'California/Mexico'},
    'ERCT': {'factor': lb_mwh_to_kg_kwh(820.7),  'label': 'Texas (ERCOT)'},
    'FRCC': {'factor': lb_mwh_to_kg_kwh(870.0),  'label': 'Florida'},
    'HIMS': {'factor': lb_mwh_to_kg_kwh(1580.8), 'label': 'Hawaii'},
    'MROE': {'factor': lb_mwh_to_kg_kwh(1020.3), 'label': 'Midwest RE East (WI)'},
    'MROW': {'factor': lb_mwh_to_kg_kwh(1145.7), 'label': 'Midwest RE West'},
    'NEWE': {'factor': lb_mwh_to_kg_kwh(541.7),  'label': 'New England'},
    'NWPP': {'factor': lb_mwh_to_kg_kwh(629.0),  'label': 'Northwest Power Pool'},
    'NYCW': {'factor': lb_mwh_to_kg_kwh(648.4),  'label': 'New York City'},
    'NYLI': {'factor': lb_mwh_to_kg_kwh(900.1),  'label': 'Long Island, NY'},
    'NYUP': {'factor': lb_mwh_to_kg_kwh(324.7),  'label': 'Upstate New York'},
    'RFCE': {'factor': lb_mwh_to_kg_kwh(826.2),  'label': 'RFC East (PA/NJ/MD)'},
    'RFCM': {'factor': lb_mwh_to_kg_kwh(1096.5), 'label': 'RFC Michigan'},
    'RFCW': {'factor': lb_mwh_to_kg_kwh(1353.5), 'label': 'RFC West (OH/IN/KY)'},
    'RMPA': {'factor': lb_mwh_to_kg_kwh(1296.2), 'label': 'Rocky Mountain (CO)'},
    'SPNO': {'factor': lb_mwh_to_kg_kwh(1338.2), 'label': 'SPP North'},
    'SPSO': {'factor': lb_mwh_to_kg_kwh(1388.1), 'label': 'SPP South (OK/TX)'},
    'SRMW': {'factor': lb_mwh_to_kg_kwh(1355.2), 'label': 'SERC Midwest (MO/IL)'},
    'SRMV': {'factor': lb_mwh_to_kg_kwh(827.0),  'label': 'SERC Mississippi Valley'},
    'SRSO': {'factor': lb_mwh_to_kg_kwh(1011.7), 'label': 'SERC South (AL/GA/SC)'},
    'SRVC': {'factor': lb_mwh_to_kg_kwh(755.1),  'label': 'SERC Virginia-Carolina'},
    'SRTEN': {'factor': lb_mwh_to_kg_kwh(873.0), 'label': 'SERC Tennessee'},
    # Fallback: US national average eGRID2022
    'US_AVG': {'factor': lb_mwh_to_kg_kwh(855.0), 'label': 'US National Average'},
}

# US State → eGRID subregion (best-fit; many states span multiple subregions)
STATE_TO_EGRID = {
    'AL': 'SRSO', 'AK': 'AKGD', 'AZ': 'NWPP', 'AR': 'SRMV',
    'CA': 'CAMX', 'CO': 'RMPA', 'CT': 'NEWE', 'DE': 'RFCE',
    'DC': 'RFCE', 'FL': 'FRCC', 'GA': 'SRSO', 'HI': 'HIMS',
    'ID': 'NWPP', 'IL': 'SRMW', 'IN': 'RFCW', 'IA': 'MROW',
    'KS': 'SPNO', 'KY': 'RFCW', 'LA': 'SRMV', 'ME': 'NEWE',
    'MD': 'RFCE', 'MA': 'NEWE', 'MI': 'RFCM', 'MN': 'MROW',
    'MS': 'SRMV', 'MO': 'SRMW', 'MT': 'NWPP', 'NE': 'MROW',
    'NV': 'NWPP', 'NH': 'NEWE', 'NJ': 'RFCE', 'NM': 'RMPA',
    'NY': 'NYCW', 'NC': 'SRVC', 'ND': 'MROW', 'OH': 'RFCW',
    'OK': 'SPSO', 'OR': 'NWPP', 'PA': 'RFCE', 'RI': 'NEWE',
    'SC': 'SRVC', 'SD': 'MROW', 'TN': 'SRTEN', 'TX': 'ERCT',
    'UT': 'NWPP', 'VT': 'NEWE', 'VA': 'SRVC', 'WA': 'NWPP',
    'WV': 'RFCW', 'WI': 'MROE', 'WY': 'RMPA',
}


# ── Business Travel — Flights (Scope 3, Cat 6) ─────────────────────────────
# Source: DEFRA/BEIS 2023 Greenhouse Gas Reporting Conversion Factors
# Includes Radiative Forcing Index (RFI × 1.9) for non-CO2 warming effects.
# Unit: kg CO2e per passenger-km
# Short-haul: < 3,700 km; Long-haul: ≥ 3,700 km

FLIGHT_FACTORS = {
    ('SHORT', 'ECONOMY'):          Decimal('0.25519'),
    ('SHORT', 'PREMIUM_ECONOMY'):  Decimal('0.25519'),  # No dedicated short-haul PE factor
    ('SHORT', 'BUSINESS'):         Decimal('0.37289'),
    ('SHORT', 'FIRST'):            Decimal('0.37289'),  # No dedicated short-haul First
    ('LONG',  'ECONOMY'):          Decimal('0.19510'),
    ('LONG',  'PREMIUM_ECONOMY'):  Decimal('0.28686'),
    ('LONG',  'BUSINESS'):         Decimal('0.59613'),
    ('LONG',  'FIRST'):            Decimal('0.86000'),
}

FLIGHT_HAUL_THRESHOLD_KM = 3700  # DEFRA 2023 threshold
FLIGHT_ROUTING_FACTOR = Decimal('1.09')  # ICAO detour factor for actual vs. great-circle distance

# Cabin class code → normalized name
CABIN_CLASS_MAP = {
    # GDS booking class codes → cabin
    'F': 'FIRST', 'A': 'FIRST', 'P': 'FIRST',
    'J': 'BUSINESS', 'C': 'BUSINESS', 'D': 'BUSINESS', 'I': 'BUSINESS', 'Z': 'BUSINESS',
    'W': 'PREMIUM_ECONOMY', 'S': 'PREMIUM_ECONOMY',
    'Y': 'ECONOMY', 'B': 'ECONOMY', 'H': 'ECONOMY', 'K': 'ECONOMY',
    'M': 'ECONOMY', 'L': 'ECONOMY', 'V': 'ECONOMY', 'N': 'ECONOMY',
    'Q': 'ECONOMY', 'T': 'ECONOMY', 'E': 'ECONOMY', 'X': 'ECONOMY', 'U': 'ECONOMY',
    # Text labels (case-insensitive, normalized in parser)
    'ECONOMY': 'ECONOMY',
    'PREMIUM ECONOMY': 'PREMIUM_ECONOMY',
    'PREMIUM_ECONOMY': 'PREMIUM_ECONOMY',
    'BUSINESS': 'BUSINESS',
    'FIRST': 'FIRST',
    'FIRST CLASS': 'FIRST',
}


# ── Business Travel — Hotels (Scope 3, Cat 6) ─────────────────────────────
# Source: Cornell Hotel Sustainability Benchmarking Index 2023
# Unit: kg CO2e per room-night
HOTEL_FACTORS = {
    'US':      Decimal('31.6'),
    'GB':      Decimal('36.0'),
    'DE':      Decimal('25.0'),
    'FR':      Decimal('25.0'),
    'NL':      Decimal('25.0'),
    'JP':      Decimal('42.0'),
    'AU':      Decimal('42.0'),
    'SG':      Decimal('42.0'),
    'AE':      Decimal('55.0'),
    'SA':      Decimal('55.0'),
    'IN':      Decimal('42.0'),
    'CN':      Decimal('42.0'),
    'GLOBAL':  Decimal('31.0'),  # Default when country unknown
}


# ── Business Travel — Ground Transport (Scope 3, Cat 6) ───────────────────
# Source: DEFRA 2023
# Unit: kg CO2e per vehicle-km (assuming 1 occupant for business travel)
GROUND_FACTORS = {
    'RENTAL_SMALL':    Decimal('0.1482'),  # Small petrol car
    'RENTAL_MEDIUM':   Decimal('0.1922'),  # Medium petrol car
    'RENTAL_LARGE':    Decimal('0.2799'),  # Large petrol car
    'RENTAL_AVERAGE':  Decimal('0.1703'),  # Average petrol car (default for unspecified)
    'RENTAL_ELECTRIC': Decimal('0.0530'),  # EV on US average grid
    'TAXI':            Decimal('0.1700'),  # US taxi estimate
    'RIDESHARE':       Decimal('0.1500'),  # Uber/Lyft average
    'RAIL_AMTRAK':     Decimal('0.0477'),  # Amtrak (per passenger-km)
    'RAIL_UK':         Decimal('0.0357'),  # UK National Rail
    'BUS':             Decimal('0.0898'),  # Average diesel bus
}

# SIPP vehicle category → rental type
SIPP_MAP = {
    'M': 'RENTAL_SMALL',    # Mini
    'N': 'RENTAL_SMALL',    # Mini Elite
    'E': 'RENTAL_SMALL',    # Economy
    'H': 'RENTAL_SMALL',    # Economy Elite
    'C': 'RENTAL_MEDIUM',   # Compact
    'D': 'RENTAL_MEDIUM',   # Compact Elite
    'I': 'RENTAL_MEDIUM',   # Intermediate
    'J': 'RENTAL_MEDIUM',   # Intermediate Elite
    'S': 'RENTAL_LARGE',    # Standard
    'R': 'RENTAL_LARGE',    # Standard Elite
    'F': 'RENTAL_LARGE',    # Full-size
    'G': 'RENTAL_LARGE',    # Full-size Elite
    'P': 'RENTAL_LARGE',    # Premium
    'U': 'RENTAL_LARGE',    # Premium Elite
    'L': 'RENTAL_LARGE',    # Luxury
    'W': 'RENTAL_LARGE',    # Luxury Elite
    'O': 'RENTAL_LARGE',    # Oversize
    'X': 'RENTAL_LARGE',    # Special
}


def get_fuel_factor(fuel_type: str) -> dict:
    """Return emission factor dict for a fuel type, or None if not found."""
    return FUEL_FACTORS.get(fuel_type.upper())


def get_egrid_factor(state: str = None, subregion: str = None) -> dict:
    """Return eGRID emission factor for a US state or subregion."""
    if subregion and subregion.upper() in EGRID_FACTORS:
        return EGRID_FACTORS[subregion.upper()]
    if state and state.upper() in STATE_TO_EGRID:
        sr = STATE_TO_EGRID[state.upper()]
        return {**EGRID_FACTORS[sr], 'subregion': sr}
    return {**EGRID_FACTORS['US_AVG'], 'subregion': 'US_AVG'}


def get_flight_factor(distance_km: float, cabin_class_raw: str) -> tuple:
    """
    Return (kg_co2e_per_pkm, haul_type, cabin_class_normalized).
    """
    cabin = CABIN_CLASS_MAP.get(cabin_class_raw.strip().upper(), 'ECONOMY')
    haul = 'SHORT' if distance_km < FLIGHT_HAUL_THRESHOLD_KM else 'LONG'
    factor = FLIGHT_FACTORS.get((haul, cabin), FLIGHT_FACTORS[('LONG', 'ECONOMY')])
    return factor, haul, cabin


def get_hotel_factor(country_code: str) -> Decimal:
    """Return hotel emission factor (kg CO2e/room-night) for a country."""
    return HOTEL_FACTORS.get(country_code.upper() if country_code else '', HOTEL_FACTORS['GLOBAL'])


def get_ground_factor(vehicle_type: str, segment_subtype: str = None) -> Decimal:
    """Return ground transport emission factor (kg CO2e/km)."""
    if segment_subtype and segment_subtype.upper() in ('TAXI', 'RIDESHARE'):
        return GROUND_FACTORS['RIDESHARE']
    # Try SIPP code first
    if vehicle_type:
        sipp_key = SIPP_MAP.get(vehicle_type.upper()[:1])
        if sipp_key:
            return GROUND_FACTORS[sipp_key]
        # Text descriptions
        vt = vehicle_type.upper()
        if 'SMALL' in vt or 'MINI' in vt or 'ECONOMY' in vt or 'COMPACT' in vt:
            return GROUND_FACTORS['RENTAL_SMALL']
        if 'LARGE' in vt or 'FULL' in vt or 'PREMIUM' in vt or 'LUXURY' in vt:
            return GROUND_FACTORS['RENTAL_LARGE']
    return GROUND_FACTORS['RENTAL_AVERAGE']
