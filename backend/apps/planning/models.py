from typing import Any

from django.db import models
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
