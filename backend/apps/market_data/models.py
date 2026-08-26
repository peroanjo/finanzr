from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel


class Instrument(TimeStampedModel):
    class Kind(models.TextChoices):
        FUND = "fund", _("Fund")
        STOCK = "stock", _("Stock")
        ETF = "etf", _("ETF")
        CRYPTO = "crypto", _("Crypto")

    kind = models.CharField(max_length=12, choices=Kind.choices)
    name = models.CharField(max_length=240)
    # Currency in which the instrument's primary quote/NAV is expressed.
    # ``base_currency`` is kept for backwards compatibility with the first
    # schema; new code should use ``quote_currency``.
    quote_currency = models.CharField(max_length=3, default="EUR")
    base_currency = models.CharField(max_length=4, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class InstrumentIdentifier(UUIDModel):
    class Scheme(models.TextChoices):
        ISIN = "isin", _("ISIN")
        YAHOO = "yahoo", _("Yahoo")
        CRYPTO_SYMBOL = "crypto_symbol", _("Crypto symbol")
        KRAKEN = "kraken", _("Kraken")
        OTHER = "other", _("Other")

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="identifiers")
    scheme = models.CharField(max_length=20, choices=Scheme.choices)
    value = models.CharField(max_length=120)
    venue = models.CharField(max_length=40, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("scheme", "value", "venue"), name="instrument_identifier_unique"
            ),
            models.UniqueConstraint(
                fields=("instrument", "scheme"),
                condition=Q(is_primary=True),
                name="instrument_primary_identifier_unique",
            ),
        ]
        indexes = [models.Index(fields=("scheme", "value"))]

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}"


class WorkspaceInstrument(UUIDModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="instrument_links",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="workspace_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "instrument"),
                name="workspace_instrument_unique",
            )
        ]
        ordering = ("instrument__name",)

    def __str__(self) -> str:
        return f"{self.workspace} · {self.instrument}"


class MarketPrice(TimeStampedModel):
    class Granularity(models.TextChoices):
        SPOT = "spot", _("Spot")
        DAY = "day", _("Day")
        WEEK = "week", _("Week")
        MONTH = "month", _("Month")

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="prices")
    quoted_at = models.DateTimeField()
    granularity = models.CharField(max_length=8, choices=Granularity.choices)
    open = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    high = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    low = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    close = models.DecimalField(max_digits=24, decimal_places=10)
    currency = models.CharField(max_length=4)
    source = models.CharField(max_length=40)

    class Meta:
        ordering = ("-quoted_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("instrument", "quoted_at", "granularity", "source"),
                name="market_price_unique",
            ),
            models.CheckConstraint(
                condition=Q(close__gte=0), name="market_price_close_nonnegative"
            ),
        ]
        indexes = [models.Index(fields=("instrument", "-quoted_at"))]

    def __str__(self) -> str:
        return f"{self.instrument} · {self.quoted_at:%Y-%m-%d}"


class WorkspaceMarketPriceOverride(TimeStampedModel):
    """A workspace-owned native-currency spot quote."""

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="market_price_overrides",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="workspace_price_overrides",
    )
    quoted_at = models.DateTimeField()
    close = models.DecimalField(max_digits=24, decimal_places=10)
    currency = models.CharField(max_length=4)
    source = models.CharField(max_length=40, default="manual")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "instrument"),
                name="workspace_market_price_override_unique",
            ),
            models.CheckConstraint(
                condition=Q(close__gte=0), name="workspace_market_price_close_nonnegative"
            ),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "instrument", "-quoted_at"),
                name="workspace_market_price_ix",
            )
        ]

    def __str__(self) -> str:
        return f"{self.workspace} · {self.instrument} · {self.quoted_at:%Y-%m-%d}"


class FxRate(TimeStampedModel):
    """A provider exchange-rate snapshot shared by all workspaces."""

    quote_currency = models.CharField(max_length=3)
    base_currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=24, decimal_places=12)
    source = models.CharField(max_length=40)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("quote_currency", "base_currency", "rate_date", "source"),
                name="fx_rate_pair_date_source_unique",
            ),
            models.CheckConstraint(condition=Q(rate__gt=0), name="fx_rate_positive"),
        ]
        indexes = [
            models.Index(
                fields=("quote_currency", "base_currency", "-rate_date"),
                name="market_data_fx_quote_6b5a7d_ix",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quote_currency}/{self.base_currency} · {self.rate_date}"


class WorkspaceFxOverride(TimeStampedModel):
    """A workspace-owned correction that takes precedence over provider rates."""

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="fx_overrides",
    )
    quote_currency = models.CharField(max_length=3)
    base_currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=24, decimal_places=12)
    source = models.CharField(max_length=40, default="manual")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "quote_currency", "base_currency", "rate_date"),
                name="workspace_fx_override_pair_date_unique",
            ),
            models.CheckConstraint(condition=Q(rate__gt=0), name="workspace_fx_override_positive"),
        ]
        indexes = [
            models.Index(
                fields=("workspace", "quote_currency", "base_currency", "-rate_date"),
                name="workspace_fx_pair_date_ix",
            )
        ]

    def __str__(self) -> str:
        return f"{self.workspace} · {self.quote_currency}/{self.base_currency} · {self.rate_date}"


class StockSplit(UUIDModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="stock_splits"
    )
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name="splits")
    effective_date = models.DateField()
    ratio = models.DecimalField(max_digits=24, decimal_places=12)
    source = models.CharField(max_length=120, default="manual")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_splits_confirmed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "instrument", "effective_date"),
                name="stock_split_unique",
            ),
            models.CheckConstraint(condition=Q(ratio__gt=0), name="stock_split_ratio_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.instrument} · {self.ratio}:1"
