from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import UUIDModel


class ImportBatch(UUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        COMPLETED = "completed", _("Completed")
        PARTIAL = "partial", _("Partial")
        FAILED = "failed", _("Failed")
        ROLLED_BACK = "rolled_back", _("Rolled back")

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.PROTECT, related_name="import_batches"
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_batches_created",
    )
    importer_slug = models.CharField(max_length=80)
    source_filename = models.CharField(max_length=255)
    content_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    source_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("workspace", "-created_at")),
            models.Index(fields=("content_sha256", "importer_slug")),
        ]

    def __str__(self) -> str:
        return f"{self.importer_slug} · {self.source_filename}"


class ImportIssue(UUIDModel):
    class Severity(models.TextChoices):
        WARNING = "warning", _("Warning")
        ERROR = "error", _("Error")

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="issues")
    severity = models.CharField(max_length=8, choices=Severity.choices)
    code = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    row_number = models.PositiveIntegerField(null=True, blank=True)
    value_preview = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("row_number", "id")

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
