from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel


class AuditEvent(UUIDModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.PROTECT, related_name="audit_events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("workspace", "-created_at"))]

    def __str__(self) -> str:
        return f"{self.event_type} · {self.created_at}"
