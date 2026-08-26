from typing import Any

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel


class RealEstateInvestment(TimeStampedModel):
    legacy_id = models.PositiveIntegerField(null=True, blank=True)

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        COMPLETED = "completed", _("Completed")
        DEFAULTED = "defaulted", _("Defaulted")
        CANCELLED = "cancelled", _("Cancelled")

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="real_estate_investments"
    )
    provider = models.ForeignKey(
        "accounts.FinancialProvider",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="real_estate_investments",
    )
    provider_label = models.CharField(max_length=160, blank=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    start_date = models.DateField()
    maturity_date = models.DateField(null=True, blank=True)
    expected_profit = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    expected_irr = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    expected_term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    origin = models.CharField(max_length=160, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Optional withholding tax rate override percentage."),
    )
    # Cash flows are entered directly in the workspace reporting currency.
    currency = models.CharField(max_length=3)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-start_date", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "legacy_id"), name="real_estate_legacy_id_unique"
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.currency:
            self.currency = self.workspace.base_currency
        super().save(*args, **kwargs)


class RealEstateCashFlow(UUIDModel):
    class FlowType(models.TextChoices):
        CONTRIBUTION = "contribution", _("Contribution")
        REINVESTMENT = "reinvestment", _("Reinvestment")
        CAPITAL_RETURN = "capital_return", _("Capital return")
        PROFIT = "profit", _("Profit")

    investment = models.ForeignKey(
        RealEstateInvestment, on_delete=models.PROTECT, related_name="cash_flows"
    )
    effective_date = models.DateField(null=True, blank=True)
    flow_type = models.CharField(max_length=16, choices=FlowType.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    withholding_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Withholding rate applied to this profit flow."),
    )
    is_external = models.BooleanField(default=False)
    source_note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("effective_date", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="real_estate_cash_flow_nonnegative"
            )
        ]

    def __str__(self) -> str:
        return f"{self.investment} · {self.get_flow_type_display()}"
