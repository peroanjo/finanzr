from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel


class FinancialProvider(UUIDModel):
    class ProviderType(models.TextChoices):
        BANK = "bank", _("Bank")
        BROKER = "broker", _("Broker")
        EXCHANGE = "exchange", _("Exchange")
        REAL_ESTATE = "real_estate", _("Real estate")
        OTHER = "other", _("Other")

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(Lower("name"), name="provider_name_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.name


class ProviderConnection(TimeStampedModel):
    class AuthType(models.TextChoices):
        OAUTH = "oauth", _("OAuth")
        API_KEY = "api_key", _("API key")
        CREDENTIALS = "credentials", _("Credentials")
        NONE = "none", _("No authentication")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACTIVE = "active", _("Active")
        EXPIRED = "expired", _("Expired")
        REVOKED = "revoked", _("Revoked")
        ERROR = "error", _("Error")

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="provider_connections"
    )
    provider = models.ForeignKey(
        FinancialProvider, on_delete=models.PROTECT, related_name="connections"
    )
    label = models.CharField(max_length=120)
    auth_type = models.CharField(max_length=20, choices=AuthType.choices, default=AuthType.NONE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    secret_reference = models.CharField(max_length=255, null=True, blank=True)
    encrypted_payload = models.BinaryField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_connections_created",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(auth_type="none")
                    | Q(secret_reference__isnull=False)
                    | Q(encrypted_payload__isnull=False)
                ),
                name="connection_requires_secret",
            )
        ]

    def __str__(self) -> str:
        return f"{self.label} · {self.provider}"


class Account(TimeStampedModel):
    class Kind(models.TextChoices):
        SAVINGS = "savings", _("Savings")
        MANUAL_INVESTMENT = "manual_investment", _("Manual investment")
        FUNDS = "funds", _("Funds")
        STOCKS = "stocks", _("Stocks")
        CRYPTO = "crypto", _("Crypto")

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="accounts"
    )
    provider = models.ForeignKey(
        FinancialProvider,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    provider_label = models.CharField(max_length=160, blank=True)
    connection = models.ForeignKey(
        ProviderConnection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounts",
    )
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    subtype = models.CharField(max_length=80, blank=True)
    importer_slug = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    external_id = models.CharField(max_length=180, null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=("workspace", "kind", "archived_at"))]
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "provider", "external_id"),
                condition=Q(external_id__isnull=False),
                name="account_external_id_unique",
            )
        ]

    def __str__(self) -> str:
        return self.name


class AccountSnapshot(TimeStampedModel):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="snapshots")
    date = models.DateField()
    value = models.DecimalField(max_digits=24, decimal_places=8)
    contribution = models.DecimalField(max_digits=24, decimal_places=8, default=0)
    earnings = models.DecimalField(max_digits=24, decimal_places=8, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    base_currency = models.CharField(max_length=3, default="EUR")
    base_value = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    base_contribution = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    base_earnings = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    fx_rate_to_base = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    fx_rate_date = models.DateField(null=True, blank=True)
    fx_source = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=("account", "date"), name="account_snapshot_unique")
        ]
        indexes = [models.Index(fields=("account", "-date"))]

    def __str__(self) -> str:
        return f"{self.account} · {self.date}"
