"""
Management command to seed the database with demo data.

Creates:
- 2 tenants (Acme Manufacturing DE, GlobalTech US)
- 3 users (admin, analyst1, analyst2)
- Processes sample CSV files for all three source types
- Simulates some reviews (approve, flag, reject)

Usage: python manage.py seed_demo
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from rest_framework.authtoken.models import Token

from core.models import Tenant, IngestionBatch
from core.ingestion import parse_sap_file, parse_utility_file, parse_travel_file


class Command(BaseCommand):
    help = 'Seed the database with demo tenants, users, and sample emission data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('[*] Seeding demo data...'))

        # ── Create tenants ──────────────────────────────────────────────────
        tenant1, _ = Tenant.objects.get_or_create(
            slug='acme-manufacturing',
            defaults={
                'name': 'Acme Manufacturing GmbH',
                'fiscal_year_start_month': 1,
            }
        )
        tenant2, _ = Tenant.objects.get_or_create(
            slug='globaltech-us',
            defaults={
                'name': 'GlobalTech US Inc.',
                'fiscal_year_start_month': 4,  # April fiscal year start
            }
        )
        self.stdout.write(f'  [+] Tenants: {tenant1.name}, {tenant2.name}')

        # ── Create users ────────────────────────────────────────────────────
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin', email='admin@breatheesg.com',
                password='breathe2024', first_name='Admin', last_name='User'
            )
        else:
            admin = User.objects.get(username='admin')
        Token.objects.get_or_create(user=admin)

        if not User.objects.filter(username='analyst1').exists():
            analyst1 = User.objects.create_user(
                username='analyst1', email='analyst1@breatheesg.com',
                password='breathe2024', first_name='Sarah', last_name='Chen'
            )
        else:
            analyst1 = User.objects.get(username='analyst1')
        Token.objects.get_or_create(user=analyst1)

        if not User.objects.filter(username='analyst2').exists():
            analyst2 = User.objects.create_user(
                username='analyst2', email='analyst2@breatheesg.com',
                password='breathe2024', first_name='James', last_name='Patel'
            )
        else:
            analyst2 = User.objects.get(username='analyst2')
        Token.objects.get_or_create(user=analyst2)

        self.stdout.write('  [+] Users: admin / analyst1 / analyst2 (password: breathe2024)')

        # ── Ingest sample data ──────────────────────────────────────────────
        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
        data_dir = os.path.abspath(data_dir)

        sample_files = [
            ('sample_sap.csv', IngestionBatch.SourceType.SAP, parse_sap_file, tenant1),
            ('sample_utility.csv', IngestionBatch.SourceType.UTILITY, parse_utility_file, tenant1),
            ('sample_travel.csv', IngestionBatch.SourceType.TRAVEL, parse_travel_file, tenant2),
        ]

        for filename, source_type, parser_fn, tenant in sample_files:
            filepath = os.path.join(data_dir, filename)
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f'  [!] Sample file not found: {filepath}'))
                continue

            batch = IngestionBatch.objects.create(
                tenant=tenant,
                source_type=source_type,
                filename=filename,
                uploaded_by=admin,
                status=IngestionBatch.Status.PROCESSING,
            )

            with open(filepath, 'rb') as f:
                result = parser_fn(f, batch, tenant)

            batch.status = IngestionBatch.Status.DONE
            batch.row_count = result.get('row_count', 0)
            batch.error_count = result.get('errors', 0)
            batch.warning_count = result.get('warnings', 0)
            batch.parse_log = result.get('log', [])
            batch.save()

            self.stdout.write(
                f'  [+] {filename}: {batch.row_count} records '
                f'({batch.error_count} errors, {batch.warning_count} warnings)'
            )

        self.stdout.write(self.style.SUCCESS('\n[OK] Demo data seeded successfully!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  admin / breathe2024 (superuser)')
        self.stdout.write('  analyst1 / breathe2024')
        self.stdout.write('  analyst2 / breathe2024')
