"""
API views for BreatheESG.

Endpoints:
  POST /api/auth/login/
  POST /api/auth/logout/
  GET  /api/auth/me/

  GET  /api/tenants/
  GET  /api/batches/
  POST /api/ingest/sap/
  POST /api/ingest/utility/
  POST /api/ingest/travel/

  GET  /api/records/
  GET  /api/records/{id}/
  PATCH /api/records/{id}/
  POST /api/records/{id}/approve/
  POST /api/records/{id}/reject/
  POST /api/records/{id}/flag/
  POST /api/records/bulk-action/

  GET  /api/records/{id}/audit/
  GET  /api/summary/
"""

import logging
from decimal import Decimal
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status, viewsets, filters
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from core.models import Tenant, IngestionBatch, EmissionRecord, AuditLog, RawRecord
from core.ingestion import parse_sap_file, parse_utility_file, parse_travel_file
from .serializers import (
    TenantSerializer, BatchSerializer,
    EmissionRecordListSerializer, EmissionRecordDetailSerializer,
    EmissionRecordEditSerializer, AuditLogSerializer,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _write_audit_log(record: EmissionRecord, actor, action: str, before: dict, after: dict, notes: str = ''):
    AuditLog.objects.create(
        emission_record=record,
        actor=actor,
        action=action,
        before_state=before,
        after_state=after,
        notes=notes,
    )


def _record_to_dict(record: EmissionRecord) -> dict:
    return {
        'review_status': record.review_status,
        'activity_value': str(record.activity_value),
        'co2e_kg': str(record.co2e_kg),
        'review_notes': record.review_notes,
        'is_locked': record.is_locked,
        'is_edited': record.is_edited,
    }


# ── Auth ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'is_staff': user.is_staff,
        }
    })


@api_view(['POST'])
def logout_view(request):
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({'detail': 'Logged out'})


@api_view(['GET'])
def me_view(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': user.get_full_name(),
        'is_staff': user.is_staff,
    })


# ── Tenant ─────────────────────────────────────────────────────────────────

class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]


# ── Ingestion ──────────────────────────────────────────────────────────────

class IngestView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, request):
        tenant_id = request.data.get('tenant_id') or request.query_params.get('tenant_id')
        if not tenant_id:
            # Default to first tenant for demo
            return Tenant.objects.first()
        return Tenant.objects.get(id=tenant_id)

    def post(self, request, source_type: str):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = self._get_tenant(request)
        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_type=source_type,
            filename=file_obj.name,
            raw_file=file_obj,
            uploaded_by=request.user,
            status=IngestionBatch.Status.PROCESSING,
        )

        try:
            if source_type == IngestionBatch.SourceType.SAP:
                result = parse_sap_file(file_obj, batch, tenant)
            elif source_type == IngestionBatch.SourceType.UTILITY:
                result = parse_utility_file(file_obj, batch, tenant)
            elif source_type == IngestionBatch.SourceType.TRAVEL:
                result = parse_travel_file(file_obj, batch, tenant)
            else:
                return Response({'error': f'Unknown source type: {source_type}'}, status=400)

            batch.status = IngestionBatch.Status.DONE
            batch.row_count = result.get('row_count', 0)
            batch.error_count = result.get('errors', 0)
            batch.warning_count = result.get('warnings', 0)
            batch.parse_log = result.get('log', [])
            batch.save()

            return Response({
                'batch_id': str(batch.id),
                'status': 'done',
                'row_count': batch.row_count,
                'error_count': batch.error_count,
                'warning_count': batch.warning_count,
                'log': batch.parse_log,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f'Ingestion failed for batch {batch.id}')
            batch.status = IngestionBatch.Status.FAILED
            batch.parse_log = [f'Fatal error: {str(e)}']
            batch.save()
            return Response({'error': str(e), 'batch_id': str(batch.id)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def ingest_sap(request):
    return IngestView().post(request, IngestionBatch.SourceType.SAP)


@api_view(['POST'])
def ingest_utility(request):
    return IngestView().post(request, IngestionBatch.SourceType.UTILITY)


@api_view(['POST'])
def ingest_travel(request):
    return IngestView().post(request, IngestionBatch.SourceType.TRAVEL)


# ── Batches ────────────────────────────────────────────────────────────────

class BatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['uploaded_at', 'status', 'source_type']
    ordering = ['-uploaded_at']

    def get_queryset(self):
        qs = IngestionBatch.objects.select_related('uploaded_by', 'tenant')
        if source_type := self.request.query_params.get('source_type'):
            qs = qs.filter(source_type=source_type)
        if status_filter := self.request.query_params.get('status'):
            qs = qs.filter(status=status_filter)
        return qs


# ── EmissionRecords ────────────────────────────────────────────────────────

class EmissionRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['source_period_end', 'co2e_kg', 'review_status', 'created_at']
    ordering = ['-source_period_end']
    search_fields = ['source_id', 'activity_description', 'facility_name', 'region']

    def get_queryset(self):
        qs = EmissionRecord.objects.select_related(
            'tenant', 'batch', 'raw_record', 'reviewed_by'
        )
        params = self.request.query_params

        if scope := params.get('scope'):
            qs = qs.filter(scope=scope)
        if source_type := params.get('source_type'):
            qs = qs.filter(source_type=source_type)
        if review_status := params.get('review_status'):
            qs = qs.filter(review_status=review_status)
        if batch_id := params.get('batch'):
            qs = qs.filter(batch_id=batch_id)
        if tenant_id := params.get('tenant'):
            qs = qs.filter(tenant_id=tenant_id)
        if period_start := params.get('period_start'):
            qs = qs.filter(source_period_end__gte=period_start)
        if period_end := params.get('period_end'):
            qs = qs.filter(source_period_start__lte=period_end)
        if flagged := params.get('flagged'):
            if flagged.lower() == 'true':
                qs = qs.exclude(flag_reasons=[])

        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionRecordDetailSerializer
        if self.action in ('update', 'partial_update'):
            return EmissionRecordEditSerializer
        return EmissionRecordListSerializer

    def perform_update(self, serializer):
        record = self.get_object()
        if record.is_locked:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Record is locked for audit.')

        before = _record_to_dict(record)
        edit_data = serializer.validated_data

        # If activity_value changed, recompute co2e and track edit history
        new_value = edit_data.get('activity_value')
        if new_value and new_value != record.activity_value:
            if not record.is_edited:
                serializer.save(
                    is_edited=True,
                    original_activity_value=record.activity_value,
                    edited_by=self.request.user,
                    edited_at=timezone.now(),
                    co2e_kg=(new_value * record.emission_factor).quantize(Decimal('0.0001')),
                )
            else:
                serializer.save(
                    edited_by=self.request.user,
                    edited_at=timezone.now(),
                    co2e_kg=(new_value * record.emission_factor).quantize(Decimal('0.0001')),
                )
        else:
            serializer.save()

        after = _record_to_dict(record)
        _write_audit_log(record, self.request.user, 'EDITED', before, after,
                         edit_data.get('edit_reason', ''))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({'error': 'Record is locked.'}, status=400)
        before = _record_to_dict(record)
        notes = request.data.get('notes', '')
        lock = request.data.get('lock', False)
        record.review_status = EmissionRecord.ReviewStatus.APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        if lock:
            record.is_locked = True
        record.save()
        _write_audit_log(record, request.user, 'APPROVED' + (' + LOCKED' if lock else ''),
                         before, _record_to_dict(record), notes)
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({'error': 'Record is locked.'}, status=400)
        before = _record_to_dict(record)
        notes = request.data.get('notes', '')
        record.review_status = EmissionRecord.ReviewStatus.REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        record.save()
        _write_audit_log(record, request.user, 'REJECTED', before, _record_to_dict(record), notes)
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({'error': 'Record is locked.'}, status=400)
        before = _record_to_dict(record)
        reason = request.data.get('reason', 'Manually flagged by analyst')
        record.review_status = EmissionRecord.ReviewStatus.FLAGGED
        record.flag_reasons = record.flag_reasons + [f'[Manual] {reason}']
        record.save()
        _write_audit_log(record, request.user, 'FLAGGED', before, _record_to_dict(record), reason)
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=False, methods=['post'], url_path='bulk-action')
    def bulk_action(self, request):
        ids = request.data.get('ids', [])
        action = request.data.get('action')
        notes = request.data.get('notes', '')

        if not ids or action not in ('approve', 'reject', 'flag'):
            return Response({'error': 'Provide ids and action (approve/reject/flag)'}, status=400)

        records = EmissionRecord.objects.filter(id__in=ids, is_locked=False)
        now = timezone.now()
        updated = 0
        for record in records:
            before = _record_to_dict(record)
            if action == 'approve':
                record.review_status = EmissionRecord.ReviewStatus.APPROVED
                audit_action = 'APPROVED'
            elif action == 'reject':
                record.review_status = EmissionRecord.ReviewStatus.REJECTED
                audit_action = 'REJECTED'
            else:
                record.review_status = EmissionRecord.ReviewStatus.FLAGGED
                audit_action = 'FLAGGED'
            record.reviewed_by = request.user
            record.reviewed_at = now
            record.review_notes = notes
            record.save()
            _write_audit_log(record, request.user, f'BULK_{audit_action}',
                             before, _record_to_dict(record), notes)
            updated += 1
        return Response({'updated': updated})

    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(emission_record=record).select_related('actor')
        return Response(AuditLogSerializer(logs, many=True).data)


# ── Summary dashboard ──────────────────────────────────────────────────────

@api_view(['GET'])
def summary_view(request):
    qs = EmissionRecord.objects.all()
    tenant_id = request.query_params.get('tenant')
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    agg = qs.aggregate(
        total_co2e_kg=Sum('co2e_kg'),
        pending_count=Count('id', filter=Q(review_status='PENDING')),
        flagged_count=Count('id', filter=Q(review_status='FLAGGED')),
        approved_count=Count('id', filter=Q(review_status='APPROVED')),
        rejected_count=Count('id', filter=Q(review_status='REJECTED')),
        total_records=Count('id'),
    )

    total_kg = agg['total_co2e_kg'] or Decimal('0')

    by_scope = list(
        qs.values('scope').annotate(
            co2e_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope')
    )
    by_source = list(
        qs.values('source_type').annotate(
            co2e_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('source_type')
    )

    return Response({
        'total_co2e_kg': str(total_kg),
        'total_co2e_tonnes': str((total_kg / Decimal('1000')).quantize(Decimal('0.001'))),
        'pending_count': agg['pending_count'],
        'flagged_count': agg['flagged_count'],
        'approved_count': agg['approved_count'],
        'rejected_count': agg['rejected_count'],
        'total_records': agg['total_records'],
        'by_scope': [
            {**item, 'co2e_kg': str(item['co2e_kg'] or 0),
             'scope_label': dict(EmissionRecord.Scope.choices).get(item['scope'], item['scope'])}
            for item in by_scope
        ],
        'by_source_type': [
            {**item, 'co2e_kg': str(item['co2e_kg'] or 0),
             'source_label': dict(EmissionRecord.SourceType.choices).get(item['source_type'], item['source_type'])}
            for item in by_source
        ],
    })
