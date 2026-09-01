"""Canonical native projections for manual investment API and exports."""

from __future__ import annotations

from typing import Any

from apps.accounts.models import Account, AccountSnapshot
from apps.api.legacy import number, provider_name


def investment_account_row(account: Account) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "name": account.name,
        "platform": provider_name(account),
        "type": account.subtype,
        "currency": account.currency,
    }


def investment_snapshot_row(snapshot: AccountSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "account_id": str(snapshot.account_id),
        "date": snapshot.date.isoformat(),
        "value": number(snapshot.base_value if snapshot.base_value is not None else snapshot.value),
        "value_original": number(snapshot.value),
        "contribution": number(
            snapshot.base_contribution
            if snapshot.base_contribution is not None
            else snapshot.contribution
        ),
        "contribution_original": number(snapshot.contribution),
        "interest": number(
            snapshot.base_earnings if snapshot.base_earnings is not None else snapshot.earnings
        ),
        "interest_original": number(snapshot.earnings),
        "currency": snapshot.currency or snapshot.account.currency,
        "base_currency": snapshot.base_currency or snapshot.account.workspace.base_currency,
        "exchange_rate": number(snapshot.fx_rate_to_base or 1),
        "exchange_rate_date": (
            snapshot.fx_rate_date.isoformat()
            if snapshot.fx_rate_date
            else snapshot.date.isoformat()
        ),
        "exchange_rate_source": snapshot.fx_source or "legacy",
    }
