from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    login_view, logout_view, me_view,
    TenantViewSet, BatchViewSet, EmissionRecordViewSet,
    ingest_sap, ingest_utility, ingest_travel,
    summary_view,
)

router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'records', EmissionRecordViewSet, basename='record')

urlpatterns = [
    path('', include(router.urls)),
    # Auth
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/me/', me_view, name='me'),
    # Ingestion
    path('ingest/sap/', ingest_sap, name='ingest-sap'),
    path('ingest/utility/', ingest_utility, name='ingest-utility'),
    path('ingest/travel/', ingest_travel, name='ingest-travel'),
    # Summary
    path('summary/', summary_view, name='summary'),
]
