from typing import Any

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.common.models import UUIDModel


class BudgetLine(UUIDModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="budget_lines"
    )
    category = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    # Budget amounts are entered directly in the workspace reporting currency.
    currency = models.CharField(max_length=3)
    line_type = models.CharField(max_length=40)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "category")
        constraints = [
            models.UniqueConstraint(
                Lower("category"), "workspace", name="budget_category_ci_unique"
            )
        ]

    def __str__(self) -> str:
        return self.category

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.currency:
            self.currency = self.workspace.base_currency
        super().save(*args, **kwargs)


class AllocationRule(UUIDModel):
    legacy_id = models.PositiveIntegerField(null=True, blank=True)
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="allocation_rules"
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allocation_rules",
    )
    provider = models.ForeignKey(
        "accounts.FinancialProvider",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="allocation_rules",
    )
    provider_label = models.CharField(max_length=160, blank=True)
    name = models.CharField(max_length=160)
    asset_class = models.CharField(max_length=80)
    subtype = models.CharField(max_length=120, blank=True)
    target_weight = models.DecimalField(max_digits=12, decimal_places=8)
    enabled = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "legacy_id"), name="allocation_rule_legacy_id_unique"
            ),
            models.CheckConstraint(
                condition=Q(target_weight__gte=0) & Q(target_weight__lte=1),
                name="allocation_weight_between_zero_and_one",
            ),
        ]

    def __str__(self) -> str:
        return self.name
