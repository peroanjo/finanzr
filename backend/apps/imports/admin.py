from django.contrib import admin

from .models import ImportBatch, ImportIssue


class ImportIssueInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ImportIssue
    extra = 0
    readonly_fields = ("severity", "code", "message", "row_number", "value_preview")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "source_filename",
        "workspace",
        "importer_slug",
        "status",
        "imported_rows",
        "created_at",
    )
    list_filter = ("status", "importer_slug")
    search_fields = ("source_filename", "content_sha256")
    readonly_fields = ("content_sha256", "created_at", "started_at", "completed_at")
    inlines = (ImportIssueInline,)
