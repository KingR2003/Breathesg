# Tradeoffs

This document is honest about what this prototype does not do well and what would need to change before it could handle real production workloads.

## Synchronous file processing

Right now when you upload a file, the HTTP request stays open while the parser runs. Django processes every row, creates the raw records, runs the emission factor logic, writes the emission records, and then responds with a success. For files with hundreds of rows this is fine. For files with tens of thousands of rows it would time out.

In production the right approach is to accept the file, write it to storage, create the batch in PENDING status, and immediately return a 202 Accepted. A background worker (Celery with Redis as the broker) picks up the job, processes the file, and updates the batch status when it's done. The frontend polls the batch endpoint or opens a websocket to get notified when processing completes.

I didn't implement this because Celery adds meaningful operational complexity (you need to run the worker process separately, manage the broker, handle retries and dead letters) and the prototype files are small enough that synchronous processing works fine for demonstration purposes.

## Only location-based Scope 2

The GHG Protocol allows two methods for Scope 2 electricity: location-based and market-based. Location-based uses average grid emission factors for the region where the electricity was consumed. Market-based uses the emission rate of the specific electricity contract, including renewable energy certificates.

This prototype only implements location-based. Market-based is harder because it requires the client to provide their REC certificate data separately, match it to billing periods, and handle cases where certificates don't cover the full consumption volume. This is operationally complex and varies significantly between clients. For a prototype, location-based is the correct starting point and is what most companies report under GHG Protocol anyway.

## SAP fuel only, not procurement

The SAP ingester handles fuel consumption (material documents with fuel material groups) which is Scope 1. It does not handle procurement data which would be Scope 3 Category 1 (purchased goods and services). Scope 3 Category 1 is actually the largest category for most companies but it's also the hardest to compute. You need spend data from purchase orders, then either a spend-based emission factor (dollars per category) or a physical quantity-based factor (kilograms of steel, etc.), and the spend-based approach has very high uncertainty. Building a credible Scope 3 Category 1 ingester requires supplier-specific emission factors that most clients can't provide. I stubbed the category in the model (SAP_PROCUREMENT source type exists) but left the parser logic for a future iteration.

## No email notifications

When a batch finishes processing or when a record gets flagged, there are no email or Slack notifications. In production, analysts need to know when new data arrives and when something requires their attention. This is a gap in the current prototype that would need a notification system (Django's email backend or a webhook integration) before real deployment.

## No column mapping UI

The SAP ingester uses a set of known column aliases to handle the most common header variations (English and German). But real SAP exports vary more than that depending on the client's SAP version, their custom ALV layouts, and which transaction they used to generate the export. A production-grade ingester would need a column mapping step in the UI where the user can look at the detected columns and manually map anything that wasn't automatically recognised before processing starts.

## No re-processing support

If the emission factors change (DEFRA publishes updated factors annually, EPA eGRID is updated every two years), the historical records should ideally be recomputed using the new factors. The raw data is preserved in RawRecord specifically to enable this. But there's no reprocessing job or UI in the current prototype. An analyst would need to delete the affected records and re-upload the original files to get updated figures.

## No market-rate currency conversion

Some source files contain monetary amounts in various currencies (the SAP file includes net values in EUR and USD depending on the plant location). These amounts are stored as-is and not converted to a base currency. This doesn't affect the CO2e calculations but would be a problem if you wanted to do spend-based emissions estimates or report financial exposure in one currency.

## Single-region deployment

The application is deployed as a single instance with a single database. There's no replication, no failover, and no data residency separation. For a large enterprise client with operations in the EU and US, data residency might be a legal requirement (GDPR requires EU customer data to stay in the EU). A production version would need regional deployment with appropriate data isolation.

## Hardcoded emission factors

The emission factors are loaded from a seed script at startup. They're not editable from the UI. If a reviewer disagrees with a factor or wants to use a client-specific factor rather than the DEFRA default, there's no mechanism to update it without a code deploy. A production system would need a factor management interface and a way to track which factor version was used for which records.
