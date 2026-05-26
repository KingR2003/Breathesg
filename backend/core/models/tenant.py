"""
Tenant model — root of multi-tenancy.
Every record in the system is scoped to a tenant (= client company).
"""
import uuid
from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    # Reporting year for audit purposes
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1, help_text="1=January")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
