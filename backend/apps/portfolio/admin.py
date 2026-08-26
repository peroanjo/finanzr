from django.contrib import admin

from .models import ManualAsset


@admin.register(ManualAsset)
class ManualAssetAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "workspace", "asset_class", "value", "currency", "valued_at")
    list_filter = ("asset_class", "currency")
    search_fields = ("name", "provider_label")
