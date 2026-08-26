from django.contrib import admin

from .models import (
    FxRate,
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    StockSplit,
    WorkspaceFxOverride,
    WorkspaceMarketPriceOverride,
)


class IdentifierInline(admin.TabularInline):  # type: ignore[type-arg]
    model = InstrumentIdentifier
    extra = 0


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "kind", "quote_currency", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "identifiers__value")
    inlines = (IdentifierInline,)


@admin.register(MarketPrice)
class MarketPriceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("instrument", "quoted_at", "close", "currency", "source")
    list_filter = ("granularity", "source", "currency")


@admin.register(WorkspaceMarketPriceOverride)
class WorkspaceMarketPriceOverrideAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("workspace", "instrument", "quoted_at", "close", "currency")
    list_filter = ("workspace", "currency")
    date_hierarchy = "quoted_at"


@admin.register(StockSplit)
class StockSplitAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("instrument", "workspace", "effective_date", "ratio", "source")
    date_hierarchy = "effective_date"


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("quote_currency", "base_currency", "rate_date", "rate", "source")
    list_filter = ("quote_currency", "base_currency", "source")


@admin.register(WorkspaceFxOverride)
class WorkspaceFxOverrideAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("workspace", "quote_currency", "base_currency", "rate_date", "rate")
    list_filter = ("workspace", "quote_currency", "base_currency")
    date_hierarchy = "rate_date"
