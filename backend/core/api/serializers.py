"""
Django REST Framework serializers for all core models.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import Tenant, IngestionBatch, RawRecord, EmissionRecord, AuditLog


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class BatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'tenant', 'source_type', 'source_type_display',
            'filename', 'uploaded_by', 'uploaded_by_name', 'uploaded_at',
            'status', 'row_count', 'error_count', 'warning_count',
            'parse_log', 'notes',
        ]
        read_only_fields = ['id', 'uploaded_at', 'status', 'row_count', 'error_count', 'warning_count']

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'batch', 'row_index', 'raw_data', 'parse_status', 'parse_errors', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Compact serializer for list views — avoids large text fields."""
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    co2e_tonnes = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'tenant', 'batch', 'source_type', 'source_type_display',
            'source_id', 'source_period_start', 'source_period_end',
            'scope', 'scope_display', 'ghg_category', 'ghg_category_code',
            'activity_value', 'activity_unit', 'emission_factor',
            'emission_factor_source', 'co2e_kg', 'co2e_tonnes',
            'country_code', 'region', 'facility_id', 'facility_name',
            'review_status', 'review_status_display', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'is_locked', 'is_edited', 'flag_reasons',
            'created_at', 'updated_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_co2e_tonnes(self, obj):
        return float(obj.co2e_tonnes)


class EmissionRecordDetailSerializer(EmissionRecordListSerializer):
    """Full serializer for detail view — includes raw record and audit."""
    raw_record = RawRecordSerializer(read_only=True)
    activity_description = serializers.CharField()
    review_notes = serializers.CharField()
    original_value = serializers.DecimalField(max_digits=18, decimal_places=6, allow_null=True)
    original_unit = serializers.CharField()

    class Meta(EmissionRecordListSerializer.Meta):
        fields = EmissionRecordListSerializer.Meta.fields + [
            'raw_record', 'activity_description', 'review_notes',
            'original_value', 'original_unit',
            'original_activity_value', 'edited_by', 'edited_at', 'edit_reason',
        ]


class EmissionRecordEditSerializer(serializers.ModelSerializer):
    """Serializer for analyst edits — only editable fields."""
    class Meta:
        model = EmissionRecord
        fields = ['activity_value', 'review_notes', 'edit_reason']

    def validate(self, data):
        instance = self.instance
        if instance and instance.is_locked:
            raise serializers.ValidationError(
                'This record is locked for audit and cannot be modified.'
            )
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ['id', 'emission_record', 'actor', 'actor_name', 'action',
                  'before_state', 'after_state', 'notes', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.username
        return 'System'


class SummarySerializer(serializers.Serializer):
    """Dashboard summary tiles."""
    total_co2e_kg = serializers.DecimalField(max_digits=20, decimal_places=4)
    total_co2e_tonnes = serializers.DecimalField(max_digits=20, decimal_places=4)
    pending_count = serializers.IntegerField()
    flagged_count = serializers.IntegerField()
    approved_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    total_records = serializers.IntegerField()
    by_scope = serializers.ListField()
    by_source_type = serializers.ListField()
