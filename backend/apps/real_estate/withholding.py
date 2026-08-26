from __future__ import annotations

from decimal import Decimal

from apps.common.models import InstallationSettings

from .models import RealEstateInvestment


def effective_withholding_rate(
    investment: RealEstateInvestment,
    default_rate: Decimal | None = None,
) -> Decimal:
    """Return the project override or the current installation default."""

    if investment.tax_rate is not None:
        return investment.tax_rate
    return (
        default_rate
        if default_rate is not None
        else InstallationSettings.load().default_crowdfunding_tax_rate
    )


def net_profit(gross: Decimal, rate: Decimal) -> Decimal:
    """Calculate profit after withholding from a gross amount."""

    if gross <= 0:
        return gross
    return gross * (Decimal("1") - rate / Decimal("100"))
