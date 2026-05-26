# Key Design Decisions

This document explains the choices I made at each major decision point. For each one I describe what the alternatives were, why I rejected them, and what I actually went with.

## SAP Data Format

The obvious question with SAP is whether to use IDocs, OData, or flat file exports. IDocs are the traditional SAP integration format but they're a system-to-system EDI mechanism, not something a sustainability team can hand you. You'd need SAP Basis involvement to set up a partner profile and message type, which no enterprise client is going to provision for a prototype.

OData would be cleaner in theory since it's a proper REST API layered on top of SAP Fiori. The problem is that OData access requires the SAP Gateway component and API credentials that the sustainability team typically doesn't control. The people who handle ESG data extraction are usually in finance or operations, not IT, and they don't have API access.

What actually happens in practice is that sustainability managers run a transaction in SAP (usually MB51 for material documents or ME2N for purchase orders), export the results as an ALV grid, and save it as a CSV or Excel file. That's what they email to their consultants or upload to a reporting tool. So that's what I built an ingester for.

The SAP flat file has some quirks that are worth handling properly. The date format in German-locale systems is DD.MM.YYYY rather than YYYY-MM-DD. The decimal separator is a comma rather than a period, so 1.234,56 means one thousand two hundred thirty four point five six. Column headers are sometimes in German (Buchungsdatum, Menge, Mengeneinheit) and sometimes in English depending on the user's SAP language setting, so the parser handles both. Material group codes (L001, G001, etc.) need to be mapped to actual fuel types to know which emission factor to apply.

## Utility Data Format

For electricity bills the realistic options are PDF invoices, Green Button CSV exports, or direct API access via the utility's customer portal.

PDF is out because it requires OCR and the accuracy would be unreliable for something that feeds into regulatory disclosures. Direct API access requires utility enrollment and OAuth credentials that facilities teams almost never have available on demand.

Green Button is the right answer. It's an open standard supported by most major US utilities and it produces a well-structured CSV that facilities managers can download from the same portal they use to pay their bills. The format has consistent column names and handles the key complication which is billing periods that don't align with calendar months. A bill might run from January 15 to February 12, and for monthly reporting you need to split that consumption proportionally across January and February. The ingester handles this automatically.

The emission factor source for electricity is EPA eGRID, which publishes annual grid emission factors by NERC subregion. The subregion is usually available in the utility bill data or can be inferred from the service address state. Using location-based factors is the GHG Protocol default; market-based factors using RECs are not implemented in this prototype because they require the client to provide REC certificate data separately.

## Travel Data Format

For corporate travel the two main platforms are Concur (owned by SAP) and Navan (formerly TripActions). Concur has roughly 80 million users globally and is dominant in enterprises above a certain size, so I modelled the export format on Concur.

The Concur standard expense report CSV has all the fields needed: expense type to distinguish flights from hotels from ground transport, origin and destination as IATA airport codes for flights, cabin class, check-in and check-out dates for hotels, and distance or vendor type for ground transport.

One complication is that flights in Concur don't always include the distance. The GHG Protocol methodology requires distance to apply the per-passenger-kilometre emission factor. To handle this, the ingester computes great-circle distance from the origin and destination IATA codes using the Haversine formula and a bundled airport coordinate database. This is accurate enough for GHG accounting purposes.

Emission factors for flights come from DEFRA's 2023 guidance and vary by cabin class. Business class carries a higher factor than economy because it occupies more physical space on the aircraft per passenger. The factors include a radiative forcing multiplier to account for the additional warming effect of contrails and high-altitude emissions beyond CO2 alone.

## Authentication

I used Django's built-in authentication system with DRF token authentication rather than JWT or OAuth. Token auth is simpler to implement and debug, produces no expiry complications for a prototype, and is perfectly adequate for a system where all users are internal analysts. JWT would add complexity (refresh token rotation, blacklisting on logout) without meaningful benefit at this scale. OAuth would require an identity provider which is out of scope.

## Database

PostgreSQL over SQLite because the project uses JSONB columns for raw_data and before_state or after_state in the audit log. SQLite doesn't support JSONB, only JSON stored as text, which loses the ability to query inside the JSON efficiently. PostgreSQL also handles concurrent writes better which matters once more than one analyst is working at the same time.

## Synchronous Ingestion

File processing happens synchronously within the HTTP request rather than being handed off to a Celery worker queue. For a prototype with files in the hundreds of rows this is fine. The Django test timeout is high enough that parsing 100 rows of SAP data completes well within the window. The tradeoff section has more on this.

## Frontend Stack

React with Vite rather than Next.js because there's no server-side rendering requirement. The app is entirely client-side data fetching from the Django API, so SSR would only add build complexity. Zustand over Redux because the state is simple enough that a one-file store is sufficient. Recharts for the dashboard charts because it has good React integration and doesn't require a separate D3 version to manage.
