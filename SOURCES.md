# Sources and Research Notes

This document explains how I researched each data format, what I found, why the sample files look the way they do, and what gaps remain between the prototype and production reality.

## SAP Flat File Export

I researched what SAP export files actually look like by studying documentation for SAP transactions MB51 (material document list), ME2N (purchase orders by PO number), and FAGLL03 (general ledger line items). The MB51 report is what a sustainability or finance team would run to pull fuel consumption data from goods issue movements.

The key finding was that real SAP exports from German-locale systems use German number formatting (period as thousands separator, comma as decimal separator) and German column headers alongside or instead of English ones. Common German headers in fuel-related exports include Buchungsdatum for posting date, Werk for plant, Menge for quantity, Mengeneinheit for unit of measure, Materialgruppe for material group, and Kostenstelle for cost center.

The material group code is how you know a goods issue is fuel. SAP material groups are customised per company, but common conventions in German manufacturing include L001 for diesel, L002 for petrol, G001 for natural gas, and G002 for LPG. These are not standardised across SAP customers, which is a real headache. A production ingester would need the client to provide their material group to fuel type mapping.

The movement type field distinguishes different kinds of goods movements. Movement type 201 is a goods issue to a cost center, which is the relevant one for fuel combustion. Movement type 101 is a goods receipt. The parser filters for movement types that indicate consumption rather than procurement.

The sample file I created has 15 rows covering two plants (one German, one US), multiple fuel types, a mix of English and German headers, German decimal formats, and one row with an unrecognised material group to demonstrate the flagging behaviour. Dates are in DD.MM.YYYY format to match German locale.

What would break in production: The material group to fuel type mapping is hardcoded and would need to be configurable per client. Some SAP systems export XLSX rather than CSV and the parser would need openpyxl support for those. Clients sometimes export from custom ALV layouts with renamed or reordered columns that don't match any known alias.

## Utility Electricity CSV

I researched utility data formats focusing on the US market where Green Button is the closest thing to a standard. Green Button was launched by the US Department of Energy and is supported by most large US utilities including PG&E, ConEdison, National Grid, and many others. It defines a common CSV export format that portal users can download from their online accounts.

The key fields in a Green Button CSV are account number, meter ID, service address, billing period start, billing period end, consumption in kWh, peak demand in kW, tariff code, and total charges. Not all of these are required for emissions purposes but the billing period dates and kWh consumption are the minimum.

The billing period complication is real and affects most utilities. Bills are generated on a rolling 30-day cycle that starts from the meter installation date, not on the first of the month. This means a January electricity bill might cover December 18 to January 16. For monthly GHG reporting you need to split the consumption: 13 days worth in December and 16 days worth in January. The ingester does this proportionally by days.

Emission factors come from EPA eGRID which publishes annual CO2 emission rates by NERC subregion. The US grid is divided into about a dozen subregions (SRSO for the US Southeast, WECC for the Western grid, NPCC for the Northeast, etc.) each with a different emission rate because the generation mix varies. SRSO (Southeast) is heavier on fossil fuels and has a higher rate than WECC (West) which has more hydro and renewables. The 2023 eGRID factors are used in this prototype.

The sample file has 12 rows covering 6 months of data across 2 meters. One meter has a zero-consumption month which triggers an auto-flag. The billing periods are deliberately misaligned with calendar months. The eGRID subregion is SRSO.

What would break in production: Non-US utility formats are different. UK half-hourly settlement data is structured differently. EU metering data follows ESPI or national utility standards that vary by country. The parser would need format detection or format-specific implementations for each region.

## Concur Travel CSV

I researched Concur because it's the dominant corporate travel and expense platform, used by most enterprises above a certain size. SAP acquired Concur in 2014 and it has roughly 80 million users globally.

The Concur standard expense report export has a well-documented CSV format used by finance teams for reconciliation. The relevant fields for emissions are expense type (which distinguishes Airfare, Hotel, Car Rental, Taxi or Rideshare, and Train), transaction date, origin and destination for flights as IATA airport codes, cabin class, hotel check-in and check-out dates, hotel city and country, and ground transport miles or kilometres.

The IATA airport code to distance calculation uses the Haversine formula applied to the latitude and longitude coordinates of each airport. The airport coordinate database is from OpenFlights which is an open dataset covering about 7000 airports worldwide. The great-circle distance underestimates actual flight distance slightly because planes don't fly in a straight line, but the error is small enough for GHG accounting purposes and is consistent with GHG Protocol guidance.

Emission factors for flights come from DEFRA's 2023 greenhouse gas reporting conversion factors. DEFRA publishes these annually and they are the standard source used by UK-listed companies and widely adopted internationally. The factors are per passenger-kilometre and vary by cabin class (economy, premium economy, business, first) because higher classes occupy more space per passenger. DEFRA factors include a radiative forcing multiplier of around 1.9 applied to the CO2 component to account for the additional warming effect of contrails and NOx emissions at altitude. This is the correct approach under GHG Protocol Scope 3 guidance.

Hotel emission factors use DEFRA's per room-night figure averaged globally. In a production system you would want country-specific hotel factors because a hotel night in Norway (where the grid is almost entirely hydro) has very different emissions from a hotel night in Poland (which is heavily coal). DEFRA publishes country-specific hotel factors but implementing the country lookup adds complexity.

Ground transport factors distinguish car rental (average petrol car), taxi or rideshare (similar but accounting for the empty return trip), and rail (much lower than road or air).

The sample file has 20 rows covering 10 business trips for 3 employees. The trips include domestic flights within Europe, international flights between continents, hotel stays, car rentals, and taxi journeys. One trip has a missing cabin class to demonstrate the auto-flag for incomplete data. One trip has only the IATA codes with no pre-computed distance to demonstrate the Haversine distance calculation.

What would break in production: Concur is not the only travel platform. Companies using Navan, Egencia, or custom travel booking tools export differently structured files. Some travel files include taxi and rideshare via Uber for Business or Lyft Business feeds that have their own export formats. Rail travel is handled inconsistently across platforms. Train emissions in Europe vary significantly by country grid mix in a way that per-km flat factors don't capture.
