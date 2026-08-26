from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "trade_date",
        "account",
        "instrument",
        "operation_type",
        "quantity",
        "net_amount",
    )
    list_filter = ("operation_type", "cash_flow_type", "currency", "is_saveback")
    search_fields = ("external_id", "instrument__name", "account__name")
    date_hierarchy = "trade_date"
