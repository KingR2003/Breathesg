from django.contrib import admin
from core.models import Tenant, IngestionBatch, RawRecord, EmissionRecord, AuditLog


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name', 'slug']


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ['filename', 'source_type', 'tenant', 'status', 'row_count', 'uploaded_at']
    list_filter = ['source_type', 'status', 'tenant']
    search_fields = ['filename']
    readonly_fields = ['uploaded_at']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['source_type', 'scope', 'activity_value', 'activity_unit',
                    'co2e_kg', 'review_status', 'is_locked', 'tenant']
    list_filter = ['scope', 'source_type', 'review_status', 'is_locked', 'tenant']
    search_fields = ['source_id', 'activity_description', 'facility_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'actor', 'emission_record', 'timestamp']
    list_filter = ['action']
    readonly_fields = ['timestamp']
