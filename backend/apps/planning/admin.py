from django.contrib import admin

from .models import AllocationRule, BudgetLine


@admin.register(BudgetLine)
class BudgetLineAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("category", "workspace", "amount", "line_type", "sort_order")
    list_filter = ("line_type",)


@admin.register(AllocationRule)
class AllocationRuleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "workspace", "target_weight", "enabled", "sort_order")
    list_filter = ("enabled", "asset_class")
