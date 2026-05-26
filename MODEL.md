# Model Design

The whole point of this project is to take messy, inconsistent data from three very different enterprise systems and get it into a single clean table that an analyst can actually reason about. Everything in the design flows from that constraint.

## The Central Table: EmissionRecord

Every row in EmissionRecord represents one normalised activity data point. It doesn't matter whether it came from a SAP material document, a utility bill, or a Concur travel expense report. By the time it lands in this table it has the same shape: an activity quantity in a known unit, an emission factor from a cited source, and a computed CO2e figure. That uniformity is what makes cross-source analysis possible.

The fields break into a few groups.

Source traceability fields tell you where the row came from. The source_type enum (SAP_FUEL, UTILITY_ELEC, TRAVEL_FLIGHT, TRAVEL_HOTEL, TRAVEL_GROUND) identifies the system of origin. The source_id carries the original reference from that system, whether that's a vendor number, a meter ID, or an employee expense report ID. The period_start and period_end dates record when the activity happened, not when it was uploaded.

Activity data fields store the normalised quantity. Everything is converted to a standard unit at ingestion time: liters for fuel, kWh for electricity, km for travel distance, nights for hotels. The original unit from the source file is not stored here because it no longer matters once normalisation is done. The raw row, including the original unit, is preserved separately in RawRecord.

Emission computation fields store the factor and the result. The emission_factor is recorded together with its source citation and year. The co2e_kg is just activity_value multiplied by emission_factor, stored explicitly so analysts can verify the arithmetic without needing to reconstruct it.

GHG scope and category fields classify each record under the GHG Protocol framework. Scope 1 covers fuel combustion we control directly. Scope 2 is purchased electricity. Scope 3 Category 6 is business travel.

Review workflow fields support the analyst sign-off process. A record starts as PENDING and can be approved, rejected, or flagged. Approving a record sets is_locked to true, after which the record cannot be edited or re-reviewed. This is what makes the data audit-ready.

Edit tracking fields exist because analysts sometimes need to correct a parsed value. For example, a meter reading might have a decimal point error. When an analyst corrects the activity_value, the original value is preserved in original_activity_value and the reason for the change is required in edit_reason. Nothing is silently overwritten.

## RawRecord

Before any normalisation happens, the parsed row is written to RawRecord exactly as it came off the file, stored as a JSON blob. This record is never modified. If the parsing logic changes, or if an emission factor gets updated and records need to be recomputed, the raw data is still there as the source of truth.

## IngestionBatch

Every file upload creates an IngestionBatch. It records who uploaded the file, when, what the status is (pending, processing, done, or failed), and how many rows were clean versus flagged versus errored. The parse_log field stores a detailed account of what the parser found: which columns it identified, how it handled ambiguous headers, and what decisions it made. This is useful for debugging unexpected parsing behaviour.

## AuditLog

Every state change on an EmissionRecord produces an AuditLog entry. The entry captures who made the change, when, what the action was, and what the before and after states looked like. These entries are never deleted or modified. The audit log is the accountability backbone of the whole system.

## Tenant

Every record, every batch, and every user belongs to a tenant. The tenant is the company that owns the data. All database queries filter by tenant so that one company's analysts cannot see another company's records, even if they know a record ID. Superusers can see across all tenants for administrative purposes. The demo data has two tenants: a German manufacturing company and a US technology company, to show that the isolation works across different source profiles.

## EmissionFactor

The lookup table for emission factors stores the factor values used at ingestion time. At the moment the ingestion parser runs, it looks up the appropriate factor, copies it into the EmissionRecord fields, and records the source citation. The lookup table exists so factors can be updated over time without losing the historical values that were applied to existing records.

## How Scope Classification Works

SAP material documents for fuel-related material groups get classified as Scope 1 under Stationary Combustion. The material group code is how we know it's fuel. For example L001 maps to diesel and G001 maps to natural gas. Utility electricity bills are always Scope 2 under Purchased Electricity, using the location-based method with EPA eGRID factors. Travel records are always Scope 3 Category 6 under Business Travel regardless of whether they are flights, hotels, or ground transport.

## Why Records Are Locked After Approval

Once an analyst approves a record, it is locked. Any attempt to edit or re-review it via the API returns an error. The reason is that approved records are meant to be submitted to external reporting frameworks like CDP or used in audited sustainability disclosures. If records could be silently changed after approval, the approval itself would be meaningless. Locking forces any correction to go through a new edit-and-re-approve cycle, which the audit log will capture.
