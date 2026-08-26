from django.contrib import admin

from .models import RealEstateCashFlow, RealEstateInvestment


class CashFlowInline(admin.TabularInline):  # type: ignore[type-arg]
    model = RealEstateCashFlow
    extra = 0


@admin.register(RealEstateInvestment)
class RealEstateInvestmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "workspace", "status", "start_date", "maturity_date")
    list_filter = ("status", "provider")
    search_fields = ("name", "provider_label")
    inlines = (CashFlowInline,)
