from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account, AccountSnapshot
from apps.api.account_projection import account_row
from apps.api.account_queries import (
    find_manual_investment_account,
    find_savings_account,
    find_traded_account,
    kind_accounts,
    resolve_provider,
)
from apps.api.context import workspace
from apps.api.investment_projection import investment_account_row, investment_snapshot_row
from apps.api.permissions import forbidden_if_readonly
from apps.api.projection import provider_name
from apps.api.request_data import payload
from apps.api.savings_projection import savings_account_row, savings_snapshot_row
from apps.api.schemas import (
    InvestmentAccountRequestSerializer,
    InvestmentAccountUpdateRequestSerializer,
    NativeInvestmentSnapshotRequestSerializer,
    NativeSavingsSnapshotRequestSerializer,
    SavingsAccountRequestSerializer,
    SavingsAccountUpdateRequestSerializer,
    TradedAccountRequestSerializer,
    TradedAccountUpdateRequestSerializer,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rate_to_base,
)
from apps.transactions.models import Transaction
from finanzr.domain.investments import monthly_pnl
from finanzr.importers import importers

ACCOUNT_IMPORT_TARGETS = {
    Account.Kind.FUNDS: "fund_orders",
    Account.Kind.STOCKS: "stock_orders",
    Account.Kind.CRYPTO: "crypto_orders",
}


def account_importer(data: dict[str, Any], kind: str, current: str | None = None) -> str:
    if kind not in ACCOUNT_IMPORT_TARGETS:
        return ""
    if "importer_slug" not in data:
        if current is not None:
            return current
        raise ValueError(_("Select the account importer"))
    slug = str(data.get("importer_slug") or "").strip()
    if slug in {"none", "manual"}:
        return ""
    if not slug:
        return ""
    try:
        importer = importers.get(slug)
    except KeyError:
        raise ValueError(_("The selected importer does not exist")) from None
    if importer.target != ACCOUNT_IMPORT_TARGETS[Account.Kind(kind)]:
        raise ValueError(_("The importer is not compatible with this account type"))
    return slug


def account_collection(request: Request, kind: str) -> Response:
    accounts = kind_accounts(request, kind)
    if request.method == "GET":
        return Response([account_row(item) for item in accounts])
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = TradedAccountRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    try:
        importer_slug = account_importer(data, kind)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    try:
        account_currency = normalize_currency(
            data.get("currency") or workspace(request).base_currency
        )
    except CurrencyConversionError:
        return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("platform", "")))
    item = Account.objects.create(
        workspace=workspace(request),
        name=str(data["name"]),
        kind=kind,
        subtype=str(data.get("type", "")).strip(),
        provider=provider,
        provider_label=provider_label,
        importer_slug=importer_slug,
        currency=account_currency,
        external_id=None,
    )
    cache.clear()
    return Response(account_row(item), status=201)


def account_detail(request: Request, kind: str, account_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = find_traded_account(request, kind, account_id)
    if request.method == "DELETE":
        with transaction.atomic():
            # ImportBatch and its transactions both protect the account from
            # deletion, so remove dependents in a deterministic order.
            item.transactions.all().delete()
            item.snapshots.all().delete()
            # A valid transaction may have been moved to another account while
            # retaining provenance from this account's import batch. Detach it
            # before deleting the batch, while keeping the moved transaction.
            Transaction.objects.filter(import_batch__account=item).update(import_batch=None)
            item.import_batches.all().delete()
            item.delete()
        cache.clear()
        return Response({"ok": True})
    serializer = TradedAccountUpdateRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    try:
        item.importer_slug = account_importer(data, kind, item.importer_slug)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    if "name" in data:
        item.name = str(data["name"])
    item.subtype = str(data.get("type", item.subtype)).strip()
    if "currency" in data:
        try:
            item.currency = normalize_currency(data.get("currency") or item.currency)
        except CurrencyConversionError:
            return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("platform", provider_name(item))))
    item.provider = provider
    item.provider_label = provider_label
    item.save()
    cache.clear()
    return Response(account_row(item))


@api_view(["GET", "POST"])
def savings_accounts(request: Request) -> Response:
    accounts = kind_accounts(request, Account.Kind.SAVINGS)
    if request.method == "GET":
        return Response([savings_account_row(item) for item in accounts])
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = SavingsAccountRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    try:
        account_currency = normalize_currency(
            data.get("currency") or workspace(request).base_currency
        )
    except CurrencyConversionError:
        return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("bank", "")))
    item = Account.objects.create(
        workspace=workspace(request),
        name=data["name"].strip(),
        kind=Account.Kind.SAVINGS,
        subtype=str(data.get("type", "")).strip(),
        provider=provider,
        provider_label=provider_label,
        currency=account_currency,
        external_id=None,
    )
    cache.clear()
    return Response(savings_account_row(item), status=201)


@api_view(["PUT", "DELETE"])
def savings_account(request: Request, account_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = find_savings_account(request, account_id)
    if request.method == "DELETE":
        item.transactions.all().delete()
        item.snapshots.all().delete()
        item.delete()
        cache.clear()
        return Response({"ok": True})
    serializer = SavingsAccountUpdateRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    item.name = str(data.get("name", item.name)).strip()
    item.subtype = str(data.get("type", item.subtype)).strip()
    if "currency" in data:
        try:
            item.currency = normalize_currency(data.get("currency") or item.currency)
        except CurrencyConversionError:
            return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("bank", provider_name(item))))
    item.provider = provider
    item.provider_label = provider_label
    item.save()
    cache.clear()
    return Response(savings_account_row(item))


@api_view(["GET", "POST"])
def investment_accounts(request: Request) -> Response:
    accounts = kind_accounts(request, Account.Kind.MANUAL_INVESTMENT)
    if request.method == "GET":
        return Response([investment_account_row(item) for item in accounts])
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = InvestmentAccountRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    try:
        account_currency = normalize_currency(
            data.get("currency") or workspace(request).base_currency
        )
    except CurrencyConversionError:
        return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("platform", "")))
    item = Account.objects.create(
        workspace=workspace(request),
        name=data["name"].strip(),
        kind=Account.Kind.MANUAL_INVESTMENT,
        subtype=str(data.get("type", "")).strip(),
        provider=provider,
        provider_label=provider_label,
        currency=account_currency,
        external_id=None,
    )
    cache.clear()
    return Response(investment_account_row(item), status=201)


@api_view(["PUT", "DELETE"])
def investment_account(request: Request, account_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = find_manual_investment_account(request, account_id)
    if request.method == "DELETE":
        item.transactions.all().delete()
        item.snapshots.all().delete()
        item.delete()
        cache.clear()
        return Response({"ok": True})
    serializer = InvestmentAccountUpdateRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    item.name = str(data.get("name", item.name)).strip()
    item.subtype = str(data.get("type", item.subtype)).strip()
    if "currency" in data:
        try:
            item.currency = normalize_currency(data.get("currency") or item.currency)
        except CurrencyConversionError:
            return Response({"error": _("The currency code is invalid")}, status=400)
    provider, provider_label = resolve_provider(str(data.get("platform", provider_name(item))))
    item.provider = provider
    item.provider_label = provider_label
    item.save()
    cache.clear()
    return Response(investment_account_row(item))


@api_view(["GET", "POST"])
def fund_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.FUNDS)


@api_view(["PUT", "DELETE"])
def fund_account(request: Request, account_id: UUID) -> Response:
    return account_detail(request, Account.Kind.FUNDS, account_id)


@api_view(["GET", "POST"])
def stock_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.STOCKS)


@api_view(["PUT", "DELETE"])
def stock_account(request: Request, account_id: UUID) -> Response:
    return account_detail(request, Account.Kind.STOCKS, account_id)


@api_view(["GET", "POST"])
def crypto_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.CRYPTO)


@api_view(["PUT", "DELETE"])
def crypto_account(request: Request, account_id: UUID) -> Response:
    return account_detail(request, Account.Kind.CRYPTO, account_id)


@api_view(["GET", "POST"])
def savings_history(request: Request) -> Response:
    queryset = AccountSnapshot.objects.select_related("account").filter(
        account__workspace=workspace(request), account__kind=Account.Kind.SAVINGS
    )
    if "cuenta_id" in request.query_params:
        return Response({"error": _("Use account_id for account filtering")}, status=400)
    account_filter = request.query_params.get("account_id")
    if account_filter:
        try:
            account_uuid = UUID(account_filter)
        except ValueError:
            return Response({"error": _("A valid account ID was expected")}, status=400)
        account = find_savings_account(request, account_uuid)
        queryset = queryset.filter(account=account)
    if request.method == "GET":
        return Response([savings_snapshot_row(item) for item in queryset.order_by("date")])
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = NativeSavingsSnapshotRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    account = find_savings_account(request, data["account_id"])
    snapshot_date = data["date"].replace(day=monthrange(data["date"].year, data["date"].month)[1])
    value = data["balance"]
    contribution = data["contribution"]
    earnings = data["interest"]
    try:
        conversion = rate_to_base(
            account.currency,
            account.workspace.base_currency,
            snapshot_date,
            workspace=account.workspace,
        )
    except CurrencyConversionError:
        return Response(
            {"error": _("Currency conversion is unavailable for this date")}, status=400
        )
    item, _created = AccountSnapshot.objects.update_or_create(
        account=account,
        date=snapshot_date,
        defaults={
            "value": value,
            "contribution": contribution,
            "earnings": earnings,
            "currency": normalize_currency(account.currency),
            "base_currency": normalize_currency(account.workspace.base_currency),
            "base_value": value * conversion.rate,
            "base_contribution": contribution * conversion.rate,
            "base_earnings": earnings * conversion.rate,
            "fx_rate_to_base": conversion.rate,
            "fx_rate_date": conversion.rate_date,
            "fx_source": conversion.source,
        },
    )
    return Response(savings_snapshot_row(item), status=201)


@api_view(["GET", "POST"])
def investment_history(request: Request) -> Response:
    queryset = AccountSnapshot.objects.select_related("account").filter(
        account__workspace=workspace(request), account__kind=Account.Kind.MANUAL_INVESTMENT
    )
    if "cuenta_id" in request.query_params:
        return Response({"error": _("Use account_id for account filtering")}, status=400)
    account_filter = request.query_params.get("account_id")
    if account_filter:
        try:
            account_uuid = UUID(account_filter)
        except ValueError:
            return Response({"error": _("A valid account ID was expected")}, status=400)
        account = find_manual_investment_account(request, account_uuid)
        queryset = queryset.filter(account=account)
    if request.method == "GET":
        return Response([investment_snapshot_row(item) for item in queryset.order_by("date")])
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = NativeInvestmentSnapshotRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    account = find_manual_investment_account(request, data["account_id"])
    snapshot_date = data["date"].replace(day=monthrange(data["date"].year, data["date"].month)[1])
    value = data["value"]
    contribution = data["contribution"]
    if "interest" in data:
        earnings = data["interest"]
    else:
        records = [
            {
                "fecha": item.date.isoformat(),
                "cuenta_id": str(item.account_id),
                "valor": item.value,
                "aporte": item.contribution,
            }
            for item in queryset.filter(account=account)
        ]
        earnings = Decimal(
            str(
                monthly_pnl(
                    records,
                    account_id=account.id,
                    date=snapshot_date.isoformat(),
                    value=value,
                    contribution=contribution,
                    explicit_pnl=None,
                )
            )
        )
    try:
        conversion = rate_to_base(
            account.currency,
            account.workspace.base_currency,
            snapshot_date,
            workspace=account.workspace,
        )
    except CurrencyConversionError:
        return Response(
            {"error": _("Currency conversion is unavailable for this date")}, status=400
        )
    item, _created = AccountSnapshot.objects.update_or_create(
        account=account,
        date=snapshot_date,
        defaults={
            "value": value,
            "contribution": contribution,
            "earnings": earnings,
            "currency": normalize_currency(account.currency),
            "base_currency": normalize_currency(account.workspace.base_currency),
            "base_value": value * conversion.rate,
            "base_contribution": contribution * conversion.rate,
            "base_earnings": earnings * conversion.rate,
            "fx_rate_to_base": conversion.rate,
            "fx_rate_date": conversion.rate_date,
            "fx_source": conversion.source,
        },
    )
    return Response(investment_snapshot_row(item), status=201)


@api_view(["DELETE"])
def investment_snapshot_detail(request: Request, account_id: UUID, value_date: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    try:
        snapshot_date = date.fromisoformat(value_date)
    except ValueError:
        return Response({"error": _("A valid date was expected")}, status=400)
    AccountSnapshot.objects.filter(
        account=find_manual_investment_account(request, account_id), date=snapshot_date
    ).delete()
    return Response({"ok": True})


@api_view(["DELETE"])
def savings_snapshot_detail(request: Request, account_id: UUID, value_date: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    try:
        snapshot_date = date.fromisoformat(value_date)
    except ValueError:
        return Response({"error": _("A valid date was expected")}, status=400)
    AccountSnapshot.objects.filter(
        account=find_savings_account(request, account_id), date=snapshot_date
    ).delete()
    return Response({"ok": True})
