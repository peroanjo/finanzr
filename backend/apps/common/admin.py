from typing import TYPE_CHECKING

from django.contrib import admin

from .models import InstallationSettings

if TYPE_CHECKING:
    ModelAdminBase = admin.ModelAdmin[InstallationSettings]
else:
    ModelAdminBase = admin.ModelAdmin


@admin.register(InstallationSettings)
class InstallationSettingsAdmin(ModelAdminBase):
    fields = ("default_language", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request: object) -> bool:
        return not InstallationSettings.objects.exists()

    def has_delete_permission(self, request: object, obj: object | None = None) -> bool:
        return False
