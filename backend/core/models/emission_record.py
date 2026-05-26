"""
EmissionRecord — the central normalized table.

Design rationale:
- All three source types (SAP fuel, utility electricity, travel) collapse into
  this single model after normalization. This is deliberate: analysts see one
  unified view regardless of source. The source_type and raw_record fields
  preserve full provenance.
- activity_value is always stored in a canonical unit (liters for liquid fuels,
  kWh for electricity, km for travel distance, nights for hotels). The
  original_unit field records what the source gave us.
- co2e_kg is the computed output: activity_value × emission_factor. Analysts
  can verify this manually from the breakdown fields.
- The review workflow (PENDING → FLAGGED/APPROVED/REJECTED) with is_locked
  prevents modification after audit sign-off.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from .tenant import Tenant
from .batch import IngestionBatch


class RawRecord(models.Model):
    """
    Preserves the original parsed row exactly as read from the source file.
    Never mutated after creation — serves as the immutable source of truth
    for re-processing if parsing logic changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_records')
    row_index = models.IntegerField(help_text="0-based row index in the source file")
    raw_data = models.JSONField(help_text="Original parsed row as key-value dict")
    parse_status = models.CharField(
        max_length=10,
        choices=[('OK', 'OK'), ('WARN', 'Warning'), ('ERROR', 'Error')],
        default='OK'
    )
    parse_errors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['batch', 'row_index']

    def __str__(self):
        return f"Row {self.row_index} of {self.batch.filename}"


class EmissionRecord(models.Model):
    """
    The primary normalized emissions record.
    
    Scope classification follows GHG Protocol Corporate Standard:
    - Scope 1: Direct emissions from owned/controlled sources (fuel combustion)
    - Scope 2: Indirect emissions from purchased electricity/heat/steam/cooling
    - Scope 3: All other indirect emissions (business travel, procurement, etc.)
    """

    class Scope(models.TextChoices):
        SCOPE_1 = 'SCOPE_1', 'Scope 1 — Direct'
        SCOPE_2 = 'SCOPE_2', 'Scope 2 — Indirect (Energy)'
        SCOPE_3 = 'SCOPE_3', 'Scope 3 — Value Chain'

    class SourceType(models.TextChoices):
        SAP_FUEL = 'SAP_FUEL', 'SAP — Fuel Combustion'
        SAP_PROCUREMENT = 'SAP_PROCUREMENT', 'SAP — Procurement'
        UTILITY_ELECTRICITY = 'UTILITY_ELEC', 'Utility — Electricity'
        TRAVEL_FLIGHT = 'TRAVEL_FLIGHT', 'Travel — Flight'
        TRAVEL_HOTEL = 'TRAVEL_HOTEL', 'Travel — Hotel'
        TRAVEL_GROUND = 'TRAVEL_GROUND', 'Travel — Ground Transport'

    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        FLAGGED = 'FLAGGED', 'Flagged — Needs Attention'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    # ── Identity ─────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name='emission_records'
    )
    raw_record = models.OneToOneField(
        RawRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='emission_record'
    )

    # ── Source provenance ─────────────────────────────────────────────────────
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    # The unique identifier from the source system (SAP material doc, meter ID, trip ID)
    source_id = models.CharField(
        max_length=255, blank=True,
        help_text="Source-system identifier: SAP doc number, utility meter ID, Concur trip ID"
    )
    source_period_start = models.DateField(
        null=True, blank=True,
        help_text="Start of the reporting period this record covers"
    )
    source_period_end = models.DateField(
        null=True, blank=True,
        help_text="End of the reporting period this record covers"
    )
    # Human-readable description of the activity
    activity_description = models.TextField(blank=True)

    # ── GHG Scope & Category ──────────────────────────────────────────────────
    scope = models.CharField(max_length=10, choices=Scope.choices)
    # GHG Protocol category name, e.g. "Stationary Combustion", "Purchased Electricity"
    ghg_category = models.CharField(max_length=100, blank=True)
    # For Scope 3: Category number, e.g. "Cat 6" for Business Travel
    ghg_category_code = models.CharField(max_length=20, blank=True)

    # ── Activity data (normalized) ────────────────────────────────────────────
    # Always stored in canonical units:
    #   SAP fuel → liters (L)
    #   Utility electricity → kWh
    #   Travel flight → km (passenger-km)
    #   Travel hotel → nights
    #   Travel ground → km (vehicle-km)
    activity_value = models.DecimalField(
        max_digits=18, decimal_places=6,
        help_text="Normalized activity quantity in canonical unit"
    )
    activity_unit = models.CharField(
        max_length=20,
        help_text="Canonical unit: L, kWh, km, nights"
    )
    # What the source actually gave us — for transparency
    original_value = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    original_unit = models.CharField(max_length=30, blank=True)

    # ── Emission factor ───────────────────────────────────────────────────────
    emission_factor = models.DecimalField(
        max_digits=18, decimal_places=8,
        help_text="kg CO2e per activity_unit"
    )
    emission_factor_source = models.CharField(
        max_length=255,
        help_text="e.g. 'DEFRA 2023', 'EPA eGRID2022 RFCW', 'IPCC AR5'"
    )
    emission_factor_year = models.PositiveSmallIntegerField(null=True, blank=True)

    # ── Computed emissions ────────────────────────────────────────────────────
    co2e_kg = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="activity_value × emission_factor, in kg CO2e"
    )

    # ── Location / facility ───────────────────────────────────────────────────
    country_code = models.CharField(max_length=3, blank=True)
    region = models.CharField(
        max_length=100, blank=True,
        help_text="State, eGRID subregion, SAP plant description, etc."
    )
    facility_id = models.CharField(
        max_length=100, blank=True,
        help_text="SAP plant code, utility meter ID, Concur cost center"
    )
    facility_name = models.CharField(max_length=255, blank=True)

    # ── Analyst review workflow ───────────────────────────────────────────────
    review_status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    # Once locked, no further edits or status changes are allowed
    is_locked = models.BooleanField(
        default=False,
        help_text="True after analyst approval + lock-for-audit. Immutable thereafter."
    )

    # ── Auto-flagging metadata ────────────────────────────────────────────────
    flag_reasons = models.JSONField(
        default=list, blank=True,
        help_text="List of auto-detected issues: zero value, outlier, future date, etc."
    )

    # ── Edit tracking (source-of-truth provenance) ───────────────────────────
    # If an analyst corrects a value (e.g. wrong unit in SAP), we record both
    # the original and the edit, plus who made it and why.
    is_edited = models.BooleanField(default=False)
    original_activity_value = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        help_text="Pre-edit value, set when analyst corrects activity_value"
    )
    edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='edited_records'
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    edit_reason = models.TextField(blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-source_period_end', 'source_type']
        indexes = [
            models.Index(fields=['tenant', 'review_status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['tenant', 'source_type']),
            models.Index(fields=['tenant', 'source_period_start', 'source_period_end']),
            models.Index(fields=['batch']),
        ]

    def __str__(self):
        return f"{self.get_source_type_display()} | {self.activity_value} {self.activity_unit} | {self.co2e_kg} kg CO2e"

    @property
    def co2e_tonnes(self):
        """Returns CO2e in metric tonnes for display."""
        return self.co2e_kg / Decimal('1000')


class AuditLog(models.Model):
    """
    Append-only log of every state change on an EmissionRecord.
    
    Design: we never delete audit log entries. The before/after JSONB fields
    capture exactly what changed. This satisfies ISO 14064 and GHG Protocol
    audit trail requirements.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emission_record = models.ForeignKey(
        EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs'
    )
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='audit_actions'
    )
    action = models.CharField(
        max_length=50,
        help_text="e.g. CREATED, APPROVED, REJECTED, FLAGGED, EDITED, LOCKED"
    )
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.action} on {self.emission_record_id} by {self.actor} at {self.timestamp}"
