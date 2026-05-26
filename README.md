# BreatheESG — Emissions Ingestion Platform

A full-stack ESG data ingestion and analyst review platform built with Django REST Framework and React.

## What It Does

Ingests emissions and activity data from three enterprise source types, normalises everything into a unified emissions record model, and surfaces an analyst review dashboard where records can be approved, flagged, or rejected before being locked for audit.

## Source Types Supported

SAP flat file exports (fuel material documents, German ALV format with German decimal and date formats), utility portal CSVs (Green Button format, billing period splitting), and Concur travel expense reports (flights with IATA-based distance calculation, hotels, ground transport).

## Running Locally

You need Python 3.10+ and Node 18+.

Backend:

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with admin / breathe2024.

## Demo Credentials

admin / breathe2024 (superuser, sees all tenants)
analyst1 / breathe2024
analyst2 / breathe2024

## Sample Data

The seed command loads three sample files from backend/data/: a 15-row SAP fuel export, a 12-row utility electricity CSV, and a 20-row Concur travel export. These demonstrate all three source types, scope classifications, unit normalisation, and auto-flagging behaviour.

## Documentation

MODEL.md explains the data model and design rationale.
DECISIONS.md explains format choices and technology decisions.
TRADEOFFS.md is honest about what the prototype does not handle.
SOURCES.md covers the research behind each sample data format.
