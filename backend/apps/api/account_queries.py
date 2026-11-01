from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.request import Request

from apps.accounts.models import Account, FinancialProvider
from apps.api.sharing import require_resource_write, visible_accounts


def kind_accounts(request: Request, kind: str) -> QuerySet[Account]:
    return visible_accounts(request).filter(kind=kind, archived_at__isnull=True)


def find_traded_account(request: Request, kind: str, account_id: UUID) -> Account:
    """Resolve a traded account by its native UUID within the active workspace."""

    item = get_object_or_404(kind_accounts(request, kind), pk=account_id)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_resource_write(request, item)
    return item


def find_savings_account(request: Request, account_id: UUID) -> Account:
    return find_traded_account(request, Account.Kind.SAVINGS, account_id)


def find_manual_investment_account(request: Request, account_id: UUID) -> Account:
    return find_traded_account(request, Account.Kind.MANUAL_INVESTMENT, account_id)


def resolve_provider(label: str) -> tuple[FinancialProvider | None, str]:
    value = label.strip()
    provider = FinancialProvider.objects.filter(name__iexact=value).first() if value else None
    return provider, "" if provider else value
