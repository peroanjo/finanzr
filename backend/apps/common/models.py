import uuid
from decimal import Decimal
from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _


def default_summary_sources_value() -> list[str]:
    return ["savings", "manual_investments", "crowdfunding"]


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class InstallationSettings(models.Model):
    """Singleton settings shared by every user in a self-hosted installation."""

    SINGLETON_PK = 1

    class Language(models.TextChoices):
        SPANISH = "es-ES", _("Spanish")
        ENGLISH = "en", _("English")

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_PK, editable=False)
    default_language = models.CharField(
        _("default language"),
        max_length=5,
        choices=Language.choices,
        default=Language.SPANISH,
    )
    default_crowdfunding_tax_rate = models.DecimalField(
        _("default crowdfunding tax rate"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("19.00"),
    )
    default_summary_sources = models.JSONField(
        _("default summary sources"),
        default=default_summary_sources_value,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("installation settings")
        verbose_name_plural = _("installation settings")

    def __str__(self) -> str:
        return str(_("Installation settings"))

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "InstallationSettings":
        settings, _created = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings


class SummaryPreference(models.Model):
    """Per-user, per-workspace composition of the net-worth overview."""

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="summary_preferences"
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="summary_preferences"
    )
    included_sources = models.JSONField(default=list, verbose_name=_("included summary sources"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("summary preference")
        verbose_name_plural = _("summary preferences")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "workspace"), name="summary_preference_user_workspace_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.workspace}"
