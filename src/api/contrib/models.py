from django.db import models


class Publication(models.Model):
    """Durable idempotency record, committed with the published changes."""

    key = models.CharField(max_length=200, primary_key=True)
    payload_hash = models.CharField(max_length=64)
    changeset = models.JSONField()
    contribution_ids = models.JSONField(default=list)
    status = models.CharField(max_length=16, default='pending')
    result = models.JSONField(null=True)
    error = models.TextField(blank=True)
    processed = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True)
