from django.contrib import admin

from .models import BudgetLine


@admin.register(BudgetLine)
class BudgetLineAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("category", "workspace", "amount", "line_type", "sort_order")
    list_filter = ("line_type",)
