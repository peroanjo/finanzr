"""Build a reproducible currency snapshot for one transaction."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.accounts.models import Account
from apps.market_data.fx import CurrencyConversionError, normalize_currency, rate_to_base
from apps.market_data.models import FxRate, WorkspaceFxOverride


def transaction_currency(record: dict[str, Any], account: Account) -> str:
    return normalize_currency(record.get("divisa") or record.get("moneda") or account.currency)


def conversion_snapshot(
    *,
    account: Account,
    currency: str,
    trade_date: date,
    settlement_date: date | None,
    unit_price: Decimal,
    net_amount: Decimal,
    fee: Decimal,
    provided_rate: Decimal | None = None,
    provided_rate_date: date | None = None,
    provided_source: str = "manual",
    allow_pending: bool = False,
    skip_external: bool = False,
) -> dict[str, Any]:
    """Return original and workspace-base values without mutating originals."""
    base_currency = normalize_currency(account.workspace.base_currency)
    conversion_date = settlement_date or trade_date
    stored_rate = None
    if skip_external and currency != base_currency and provided_rate is None:
        stored_override = (
            WorkspaceFxOverride.objects.filter(
                workspace=account.workspace,
                quote_currency=currency,
                base_currency=base_currency,
                rate_date__lte=conversion_date,
                rate_date__gte=conversion_date - timedelta(days=7),
            )
            .order_by("-rate_date")
            .first()
        )
        stored_provider = (
            FxRate.objects.filter(
                quote_currency="GBP" if currency == "GBp" else currency,
                base_currency="GBP" if base_currency == "GBp" else base_currency,
                rate_date__lte=conversion_date,
                rate_date__gte=conversion_date - timedelta(days=7),
            )
            .order_by("-rate_date")
            .first()
        )
        stored_rate = stored_override or stored_provider
    if skip_external and currency != base_currency and provided_rate is None and not stored_rate:
        if not allow_pending:
            raise CurrencyConversionError(
                f"An exchange rate is required for {currency}/{base_currency}"
            )
        return {
            "base_currency": base_currency,
            "base_unit_price": None,
            "base_net_amount": None,
            "base_fee": None,
            "fx_rate_to_base": None,
            "fx_rate_date": None,
            "fx_source": "pending",
        }
    try:
        conversion = rate_to_base(
            currency,
            base_currency,
            conversion_date,
            provided_rate=provided_rate,
            provided_date=provided_rate_date,
            provided_source=provided_source,
            workspace=account.workspace,
        )
    except CurrencyConversionError:
        if not allow_pending:
            raise
        return {
            "base_currency": base_currency,
            "base_unit_price": None,
            "base_net_amount": None,
            "base_fee": None,
            "fx_rate_to_base": None,
            "fx_rate_date": None,
            "fx_source": "pending",
        }
    return {
        "base_currency": base_currency,
        "base_unit_price": unit_price * conversion.rate,
        "base_net_amount": net_amount * conversion.rate,
        "base_fee": fee * conversion.rate,
        "fx_rate_to_base": conversion.rate,
        "fx_rate_date": conversion.rate_date,
        "fx_source": conversion.source,
    }
