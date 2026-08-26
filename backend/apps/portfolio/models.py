from typing import Any

from django.db import models

from apps.common.models import UUIDModel


class ManualAsset(UUIDModel):
    legacy_id = models.PositiveIntegerField(null=True, blank=True)
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="manual_assets"
    )
    provider = models.ForeignKey(
        "accounts.FinancialProvider",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="manual_assets",
    )
    provider_label = models.CharField(max_length=160, blank=True)
    name = models.CharField(max_length=200)
    asset_class = models.CharField(max_length=80)
    subtype = models.CharField(max_length=120, blank=True)
    value = models.DecimalField(max_digits=24, decimal_places=8)
    # Manual values are already expressed in the workspace reporting currency.
    currency = models.CharField(max_length=3)
    valued_at = models.DateField()
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "legacy_id"), name="manual_asset_legacy_id_unique"
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.currency:
            self.currency = self.workspace.base_currency
        super().save(*args, **kwargs)
