"""Canonical native projections for savings API and workspace exports."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from apps.accounts.models import Account, AccountSnapshot
from apps.api.projection import number, provider_name
from apps.workspaces.models import WorkspaceMembership


def savings_account_row(account: Account) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "name": account.name,
        "bank": provider_name(account),
        "type": account.subtype,
        "currency": account.currency,
    }


def savings_account_responses(accounts: list[Account]) -> list[dict[str, Any]]:
    personal_ids = {account.workspace_id for account in accounts if account.workspace.is_personal}
    owners: dict[UUID, list[str]] = defaultdict(list)
    for workspace_id, display_name in WorkspaceMembership.objects.filter(
        workspace_id__in=personal_ids, role=WorkspaceMembership.Role.OWNER
    ).values_list("workspace_id", "user__display_name"):
        name = display_name.strip()
        owners[workspace_id].append("" if "@" in name else name)

    labels = {workspace_id: names[0] for workspace_id, names in owners.items() if len(names) == 1}
    return [
        {
            **savings_account_row(account),
            "workspace_id": str(account.workspace_id),
            "workspace_name": (
                labels.get(account.workspace_id, "")
                if account.workspace.is_personal
                else account.workspace.name
            ),
        }
        for account in accounts
    ]


def savings_snapshot_row(snapshot: AccountSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "account_id": str(snapshot.account_id),
        "date": snapshot.date.isoformat(),
        "balance": number(
            snapshot.base_value if snapshot.base_value is not None else snapshot.value
        ),
        "balance_original": number(snapshot.value),
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
