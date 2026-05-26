"""
IngestionBatch — one batch per file upload or API pull.
Acts as the provenance anchor: every EmissionRecord traces back to a batch.

Design decision: we keep the raw file reference so that if our parsing logic
changes, we can re-process from scratch without losing the original data.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from .tenant import Tenant


class IngestionBatch(models.Model):
    class SourceType(models.TextChoices):
        SAP = 'SAP', 'SAP Export (Fuel / Procurement)'
        UTILITY = 'UTILITY', 'Utility Portal CSV (Electricity)'
        TRAVEL = 'TRAVEL', 'Corporate Travel Export (Concur-style)'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        DONE = 'DONE', 'Done'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    filename = models.CharField(max_length=500)
    raw_file = models.FileField(upload_to='raw_uploads/%Y/%m/', null=True, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='uploaded_batches'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    # Ingestion metadata for debugging
    parse_log = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.source_type} | {self.filename} | {self.uploaded_at.date()}"
