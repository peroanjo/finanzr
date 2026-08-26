from django.contrib import admin

from .models import Account, AccountSnapshot, FinancialProvider, ProviderConnection


@admin.register(FinancialProvider)
class FinancialProviderAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "provider_type", "is_active")
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "slug")


@admin.register(ProviderConnection)
class ProviderConnectionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("label", "workspace", "provider", "auth_type", "status")
    list_filter = ("auth_type", "status")
    readonly_fields = ("encrypted_payload",)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "workspace",
        "kind",
        "currency",
        "provider",
        "importer_slug",
        "archived_at",
    )
    list_filter = ("kind", "importer_slug", "archived_at")
    search_fields = ("name", "external_id", "provider_label", "importer_slug")


@admin.register(AccountSnapshot)
class AccountSnapshotAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("account", "date", "value", "currency", "base_value", "base_currency")
    list_filter = ("date",)
    date_hierarchy = "date"
