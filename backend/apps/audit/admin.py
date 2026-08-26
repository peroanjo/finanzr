from django.contrib import admin
from django.http import HttpRequest

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_at", "workspace", "actor", "event_type", "object_type")
    list_filter = ("event_type", "object_type")
    search_fields = ("event_type", "object_type", "object_id")
    readonly_fields = (
        "workspace",
        "actor",
        "event_type",
        "object_type",
        "object_id",
        "metadata",
        "ip_hash",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AuditEvent | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditEvent | None = None) -> bool:
        return False
