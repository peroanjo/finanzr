from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404
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
from apps.api.portfolio_projection import manual_asset_row
from apps.api.projection import number, provider_name
from apps.api.real_estate_projection import real_estate_row
from apps.api.real_estate_queries import real_estate_records
from apps.api.request_data import decimal, payload
from apps.api.savings_projection import savings_account_row, savings_snapshot_row
from apps.api.schemas import (
    InvestmentAccountRequestSerializer,
    InvestmentAccountUpdateRequestSerializer,
    ManualAssetRequestSerializer,
    ManualAssetUpdateRequestSerializer,
    NativeInvestmentSnapshotRequestSerializer,
    NativeSavingsSnapshotRequestSerializer,
    RealEstateRequestSerializer,
    RealEstateUpdateRequestSerializer,
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
from apps.planning.models import BudgetLine
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate
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


@api_view(["GET", "POST"])
def portfolio(request: Request) -> Response:
    current_workspace = workspace(request)
    items = ManualAsset.objects.filter(
        workspace=current_workspace, archived_at__isnull=True
    ).select_related("provider")
    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        serializer = ManualAssetRequestSerializer(data=payload(request))
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)
        data = serializer.validated_data
        provider, provider_label = resolve_provider(str(data.get("platform", "")))
        item = ManualAsset.objects.create(
            workspace=current_workspace,
            name=data["name"].strip(),
            asset_class=data["asset_class"].strip(),
            subtype=str(data.get("subtype", "")).strip(),
            provider=provider,
            provider_label=provider_label,
            value=data["value"],
            currency=normalize_currency(current_workspace.base_currency),
            valued_at=date.today(),
        )
        return Response(manual_asset_row(item), status=201)
    return Response([manual_asset_row(item) for item in items.order_by("name", "id")])


@api_view(["PUT", "DELETE"])
def portfolio_detail(request: Request, asset_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(ManualAsset, workspace=workspace(request), pk=asset_id)
    if request.method == "DELETE":
        item.delete()
        return Response({"ok": True})
    serializer = ManualAssetUpdateRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    if "name" in data:
        item.name = data["name"].strip()
    if "asset_class" in data:
        item.asset_class = data["asset_class"].strip()
    if "subtype" in data:
        item.subtype = data["subtype"].strip()
    if "platform" in data:
        item.provider, item.provider_label = resolve_provider(str(data["platform"]))
    if "value" in data:
        item.value = data["value"]
    item.save()
    return Response(manual_asset_row(item))


def save_real_estate(item: RealEstateInvestment, data: dict[str, Any]) -> None:
    if "name" in data:
        item.name = str(data["name"]).strip()
    if "platform" in data:
        item.provider = None
        item.provider_label = str(data["platform"]).strip()
    if "status" in data:
        item.status = str(data["status"])
    if "start_date" in data:
        item.start_date = data["start_date"]
    if "maturity_date" in data:
        item.maturity_date = data["maturity_date"]
    if "expected_profit" in data:
        item.expected_profit = data["expected_profit"]
    if "expected_irr_percent" in data:
        item.expected_irr = decimal(data["expected_irr_percent"]) / 100
    if "expected_term_months" in data:
        item.expected_term_months = int(data["expected_term_months"] or 0) or None
    if "origin" in data:
        item.origin = str(data["origin"])
    if "tax_rate" in data:
        item.tax_rate = data["tax_rate"]
    item.currency = normalize_currency(item.workspace.base_currency)
    item.save()
    existing_flows_list = list(item.cash_flows.all())
    existing_contribution = sum(
        (flow.amount for flow in existing_flows_list if flow.flow_type == "contribution"),
        Decimal("0"),
    )
    existing_reinvestment = sum(
        (flow.amount for flow in existing_flows_list if flow.flow_type == "reinvestment"),
        Decimal("0"),
    )
    initial = decimal(
        data.get("initial_capital"), str(existing_contribution + existing_reinvestment)
    )
    new = decimal(
        data.get("new_capital"),
        str(initial if "initial_capital" in data else existing_contribution),
    )
    movements = data.get("movements")
    existing_flows = {str(flow.id): flow for flow in item.cash_flows.all()}
    if not isinstance(movements, list):
        movements = [
            {
                "id": flow.id,
                "flow_type": flow.flow_type,
                "amount": flow.amount,
                "effective_date": flow.effective_date,
                "note": flow.source_note,
            }
            for flow in existing_flows_list
            if flow.flow_type
            in {
                RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                RealEstateCashFlow.FlowType.PROFIT,
            }
        ]
    item.cash_flows.all().delete()
    for flow_type, amount, effective, external in (
        ("contribution", new, item.start_date, True),
        ("reinvestment", max(Decimal(0), initial - new), item.start_date, False),
    ):
        if amount > 0:
            RealEstateCashFlow.objects.create(
                investment=item,
                flow_type=flow_type,
                amount=amount,
                effective_date=effective,
                is_external=external,
            )
    allowed_types = {
        RealEstateCashFlow.FlowType.CAPITAL_RETURN,
        RealEstateCashFlow.FlowType.PROFIT,
    }
    for movement in movements:
        if not isinstance(movement, dict):
            continue
        flow_type = str(movement.get("flow_type", ""))
        if flow_type not in allowed_types:
            raise ValueError(_("An invalid real-estate movement type was received"))
        amount = decimal(movement.get("amount"))
        if amount <= 0:
            continue
        flow_date: date | None = (
            movement.get("effective_date")
            if isinstance(movement.get("effective_date"), date)
            else None
        )
        existing_flow = existing_flows.get(str(movement.get("id") or ""))
        withholding_rate = (
            existing_flow.withholding_rate
            if flow_type == RealEstateCashFlow.FlowType.PROFIT
            and existing_flow is not None
            and existing_flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
            and existing_flow.withholding_rate is not None
            else (
                effective_withholding_rate(item)
                if flow_type == RealEstateCashFlow.FlowType.PROFIT
                else None
            )
        )
        RealEstateCashFlow.objects.create(
            investment=item,
            flow_type=flow_type,
            amount=amount,
            effective_date=flow_date,
            withholding_rate=withholding_rate,
            is_external=False,
            source_note=str(movement.get("note", ""))[:240],
        )


@api_view(["GET", "POST"])
def real_estate(request: Request) -> Response:
    if request.method == "GET":
        return Response(real_estate_records(request))
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = RealEstateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    item = RealEstateInvestment(
        workspace=workspace(request),
        name=str(data["name"]),
        start_date=data["start_date"],
    )
    try:
        with transaction.atomic():
            save_real_estate(item, data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    item.refresh_from_db()
    return Response(real_estate_row(item), status=201)


@api_view(["PUT", "DELETE"])
def real_estate_detail(request: Request, investment_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(RealEstateInvestment, workspace=workspace(request), pk=investment_id)
    if request.method == "DELETE":
        item.cash_flows.all().delete()
        item.delete()
        return Response({"ok": True})
    serializer = RealEstateUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        with transaction.atomic():
            save_real_estate(item, serializer.validated_data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(real_estate_row(item))


@api_view(["GET", "PUT"])
def budget(request: Request) -> Response:
    current_workspace = workspace(request)
    items = BudgetLine.objects.filter(workspace=current_workspace)
    if request.method == "PUT":
        if denied := forbidden_if_readonly(request):
            return denied
        submitted_rows = cast(list[dict[str, Any]], request.data)
        with transaction.atomic():
            items.delete()
            BudgetLine.objects.bulk_create(
                [
                    BudgetLine(
                        workspace=current_workspace,
                        category=str(row["categoria"]),
                        amount=decimal(row["cantidad"]),
                        currency=normalize_currency(current_workspace.base_currency),
                        line_type=str(row["tipo"]),
                        sort_order=index,
                    )
                    for index, row in enumerate(submitted_rows)
                ]
            )
        items = BudgetLine.objects.filter(workspace=current_workspace)
    return Response(
        [
            {
                "categoria": x.category,
                "cantidad": number(x.amount),
                "tipo": x.line_type,
                "moneda": x.currency,
            }
            for x in items
        ]
    )
