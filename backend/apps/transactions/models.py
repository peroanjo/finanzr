from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.common.models import UUIDModel


class Transaction(UUIDModel):
    class OperationType(models.TextChoices):
        BUY = "buy", _("Buy")
        SELL = "sell", _("Sell")
        TRANSFER_IN = "transfer_in", _("Incoming transfer")
        TRANSFER_OUT = "transfer_out", _("Outgoing transfer")

    class CashFlowType(models.TextChoices):
        CONTRIBUTION = "contribution", _("Contribution")
        WITHDRAWAL = "withdrawal", _("Withdrawal")
        INTERNAL = "internal", _("Internal")
        NONE = "none", _("None")

    account = models.ForeignKey(
        "accounts.Account", on_delete=models.PROTECT, related_name="transactions"
    )
    instrument = models.ForeignKey(
        "market_data.Instrument", on_delete=models.PROTECT, related_name="transactions"
    )
    import_batch = models.ForeignKey(
        "imports.ImportBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    external_id = models.CharField(max_length=180, null=True, blank=True)
    trade_date = models.DateField()
    settlement_date = models.DateField(null=True, blank=True)
    operation_type = models.CharField(max_length=16, choices=OperationType.choices)
    cash_flow_type = models.CharField(
        max_length=16, choices=CashFlowType.choices, default=CashFlowType.NONE
    )
    quantity = models.DecimalField(max_digits=36, decimal_places=18)
    unit_price = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=24, decimal_places=8)
    fee = models.DecimalField(max_digits=24, decimal_places=8, default=0)
    currency = models.CharField(max_length=4, default="EUR")
    # Original values are kept above. These fields are an immutable snapshot
    # of the conversion into the workspace reporting currency at import/edit
    # time, so historical P&L never changes when today's FX quote changes.
    base_currency = models.CharField(max_length=3, default="EUR")
    base_unit_price = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    base_net_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    base_fee = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    fx_rate_to_base = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    fx_rate_date = models.DateField(null=True, blank=True)
    fx_source = models.CharField(max_length=40, blank=True)
    market = models.CharField(max_length=80, blank=True)
    is_saveback = models.BooleanField(default=False)
    provider_operation_type = models.CharField(max_length=80, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-trade_date", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("account", "external_id"),
                condition=Q(external_id__isnull=False),
                name="transaction_external_id_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="transaction_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(net_amount__gte=0), name="transaction_amount_nonnegative"
            ),
            models.CheckConstraint(condition=Q(fee__gte=0), name="transaction_fee_nonnegative"),
        ]
        indexes = [
            models.Index(fields=("account", "-trade_date")),
            models.Index(fields=("instrument", "-trade_date")),
            models.Index(fields=("import_batch",)),
        ]

    def __str__(self) -> str:
        return f"{self.get_operation_type_display()} · {self.instrument} · {self.trade_date}"
