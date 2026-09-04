from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account, AccountSnapshot, FinancialProvider
from apps.api.account_projection import account_row
from apps.api.investment_projection import investment_account_row, investment_snapshot_row
from apps.api.market_data_projection import (
    instrument_calculation_row,
    instrument_row,
    price_calculation_row,
    price_row,
)
from apps.api.portfolio_projection import manual_asset_row
from apps.api.position_projection import native_position_rows
from apps.api.projection import identifier, number, provider_name, select_identifier
from apps.api.real_estate_projection import real_estate_row
from apps.api.savings_projection import savings_account_row, savings_snapshot_row
from apps.api.schemas import (
    CryptoTransactionRequestSerializer,
    FundTransactionRequestSerializer,
    InvestmentAccountRequestSerializer,
    InvestmentAccountUpdateRequestSerializer,
    ManualAssetRequestSerializer,
    ManualAssetUpdateRequestSerializer,
    NativeInvestmentSnapshotRequestSerializer,
    NativeSavingsSnapshotRequestSerializer,
    PriceRequestSerializer,
    RealEstateRequestSerializer,
    RealEstateUpdateRequestSerializer,
    SavingsAccountRequestSerializer,
    SavingsAccountUpdateRequestSerializer,
    StockSplitRequestSerializer,
    StockTransactionRequestSerializer,
    TradedAccountRequestSerializer,
    TradedAccountUpdateRequestSerializer,
    normalize_instrument_identifier_value,
    validate_instrument_identifiers,
)
from apps.api.transaction_projection import (
    _calculation_operation_label,
    _transaction_calculation_row,
    transaction_row,
)
from apps.common.models import InstallationSettings
from apps.common.summary_preferences import (
    SUMMARY_SOURCE_KEYS,
    effective_summary_sources,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rate_to_base,
    rates_to_base,
)
from apps.market_data.locking import instrument_identifier_lock_keys, lock_logical_keys
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    StockSplit,
    WorkspaceInstrument,
    WorkspaceMarketPriceOverride,
)
from apps.market_data.yahoo import (
    MarketDataError,
    quote_price,
    search,
)
from apps.market_data.yahoo import (
    chart as yahoo_chart,
)
from apps.planning.models import BudgetLine
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from finanzr.domain.crypto import calculate_crypto_positions
from finanzr.domain.funds import calculate_fund_positions
from finanzr.domain.investment_performance import calculate_investment_performance
from finanzr.domain.investments import monthly_pnl
from finanzr.domain.net_worth import current_total, monthly_history
from finanzr.domain.real_estate import live_capital
from finanzr.domain.stocks import calculate_stock_positions
from finanzr.importers import importers

__all__ = ["MarketDataError", "timezone"]

ACCOUNT_IMPORT_TARGETS = {
    Account.Kind.FUNDS: "fund_orders",
    Account.Kind.STOCKS: "stock_orders",
    Account.Kind.CRYPTO: "crypto_orders",
}


def payload(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except InvalidOperation as exc:
        raise ValueError(_("A valid number was expected")) from exc


def percentage_rate(value: Any) -> Decimal:
    """Parse a withholding rate and enforce the public percentage range."""

    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(_("A valid percentage between 0 and 100 was expected")) from exc
    if not rate.is_finite() or rate < 0 or rate > 100:
        raise ValueError(_("A valid percentage between 0 and 100 was expected"))
    return rate


def active_membership(request: Request) -> WorkspaceMembership:
    user = cast(User, request.user)
    memberships = WorkspaceMembership.objects.select_related("workspace").filter(
        user=user, workspace__archived_at__isnull=True
    )
    workspace_id = request.session.get("active_workspace_id")
    if workspace_id:
        selected = memberships.filter(workspace_id=workspace_id).first()
        if selected:
            return selected
    membership = memberships.first()
    if not membership:
        raise Workspace.DoesNotExist
    request.session["active_workspace_id"] = str(membership.workspace_id)
    return membership


def workspace(request: Request) -> Workspace:
    return active_membership(request).workspace


def forbidden_if_readonly(request: Request) -> Response | None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if active_membership(request).role == WorkspaceMembership.Role.VIEWER:
        return Response({"error": _("Insufficient permissions")}, status=403)
    return None


def kind_accounts(request: Request, kind: str) -> QuerySet[Account]:
    return Account.objects.filter(workspace=workspace(request), kind=kind, archived_at__isnull=True)


def find_traded_account(request: Request, kind: str, account_id: UUID) -> Account:
    """Resolve a traded account by its native UUID within the active workspace."""

    return get_object_or_404(kind_accounts(request, kind), pk=account_id)


def find_savings_account(request: Request, account_id: UUID) -> Account:
    return get_object_or_404(kind_accounts(request, Account.Kind.SAVINGS), pk=account_id)


def find_manual_investment_account(request: Request, account_id: UUID) -> Account:
    return get_object_or_404(kind_accounts(request, Account.Kind.MANUAL_INVESTMENT), pk=account_id)


def resolve_provider(label: str) -> tuple[FinancialProvider | None, str]:
    value = label.strip()
    provider = FinancialProvider.objects.filter(name__iexact=value).first() if value else None
    return provider, "" if provider else value


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


def real_estate_records(request: Request) -> list[dict[str, Any]]:
    items = (
        RealEstateInvestment.objects.filter(workspace=workspace(request), archived_at__isnull=True)
        .prefetch_related("cash_flows", "provider")
        .order_by("-start_date", "name", "id")
    )
    default_tax_rate = InstallationSettings.load().default_crowdfunding_tax_rate
    return [real_estate_row(item, default_tax_rate=default_tax_rate) for item in items]


def _normalized_match_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("-", " ").split())


def _manual_asset_is_real_estate_duplicate(
    item: ManualAsset, properties: list[dict[str, Any]]
) -> bool:
    """Exclude only a manual row proven to mirror a real-estate project.

    Asset class labels are user-controlled and are not evidence of a
    duplicate.  Correlation therefore requires the canonical project name
    and current value to match (and, when both are available, its provider).
    This keeps legitimate manually entered property-like assets visible.
    """

    item_name = _normalized_match_text(item.name)
    item_provider = _normalized_match_text(provider_name(item))
    item_value = number(item.value)
    for project in properties:
        if item_name != _normalized_match_text(project.get("name")):
            continue
        project_provider = _normalized_match_text(project.get("platform"))
        if item_provider and project_provider and item_provider != project_provider:
            continue
        if abs(item_value - number(live_capital(project))) <= 0.01:
            return True
    return False


def _summary_manual_assets(request: Request, properties: list[dict[str, Any]]) -> list[ManualAsset]:
    return [
        item
        for item in ManualAsset.objects.filter(
            workspace=workspace(request), archived_at__isnull=True
        ).select_related("provider")
        if not _manual_asset_is_real_estate_duplicate(item, properties)
    ]


def _market_close_in_base(
    price: MarketPrice | WorkspaceMarketPriceOverride,
    current_workspace: Workspace,
    conversion_cache: dict[tuple[str, date], Decimal],
) -> Decimal | None:
    """Convert a stored market close without fabricating a missing FX history."""

    try:
        quote_currency = normalize_currency(price.currency)
        base_currency = normalize_currency(current_workspace.base_currency)
    except CurrencyConversionError:
        return None
    if quote_currency == base_currency:
        return price.close
    cache_key = (quote_currency, price.quoted_at.date())
    if cache_key not in conversion_cache:
        try:
            conversion_cache[cache_key] = rate_to_base(
                quote_currency,
                base_currency,
                price.quoted_at.date(),
                workspace=current_workspace,
            ).rate
        except CurrencyConversionError:
            return None
    return price.close * conversion_cache[cache_key]


def _traded_source_history(request: Request, kind: str) -> list[dict[str, Any]]:
    """Value traded positions at stored monthly closes when available.

    Market sources do not have synthetic history: months come from
    transactions and stored market closes. Valid closes are carried forward;
    an open position without a usable close is conservatively valued at its
    open base cost rather than being converted to zero.
    """

    current_workspace = workspace(request)
    instruments: list[Instrument] = list(workspace_instruments(request, kind))
    if not instruments:
        return []
    instrument_ids = [item.id for item in instruments]
    identity_scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
        if kind == "crypto"
        else InstrumentIdentifier.Scheme.ISIN
    )
    identity_by_instrument = {item.id: identifier(item, identity_scheme) for item in instruments}
    prices: list[MarketPrice] = list(
        MarketPrice.objects.filter(
            instrument_id__in=instrument_ids,
            granularity=MarketPrice.Granularity.SPOT,
        ).order_by("instrument_id", "quoted_at", "created_at")
    )
    overrides: list[WorkspaceMarketPriceOverride] = list(
        WorkspaceMarketPriceOverride.objects.filter(
            workspace=current_workspace, instrument_id__in=instrument_ids
        ).order_by("instrument_id", "quoted_at")
    )
    conversion_cache: dict[tuple[str, date], Decimal] = {}
    prices_by_month: dict[str, dict[str, tuple[date, Decimal]]] = {}

    def add_price(price: MarketPrice | WorkspaceMarketPriceOverride) -> None:
        key = identity_by_instrument.get(price.instrument_id, "")
        close_value = _market_close_in_base(price, current_workspace, conversion_cache)
        if not key or close_value is None:
            return
        month = price.quoted_at.date().isoformat()[:7]
        by_instrument = prices_by_month.setdefault(month, {})
        previous = by_instrument.get(key)
        if previous is None or price.quoted_at.date() >= previous[0]:
            by_instrument[key] = (price.quoted_at.date(), close_value)

    for price in prices:
        add_price(price)
    for override in overrides:
        add_price(override)

    transactions = list(
        Transaction.objects.filter(account__workspace=current_workspace, instrument__kind=kind)
        .select_related("account", "instrument")
        .prefetch_related("instrument__identifiers")
    )
    transaction_conversion_cache: dict[tuple[str, str, date], Decimal | None] = {}
    base_amounts: dict[Any, float | None] = {}
    invalid_instruments: set[Any] = set()
    for item in transactions:
        amount: float | None = (
            number(item.base_net_amount) if item.base_net_amount is not None else None
        )
        if amount is None:
            try:
                quote_currency = normalize_currency(item.currency)
                base_currency = normalize_currency(current_workspace.base_currency)
                if quote_currency == base_currency:
                    amount = number(item.net_amount)
                else:
                    cache_key = (quote_currency, base_currency, item.trade_date)
                    if cache_key not in transaction_conversion_cache:
                        try:
                            transaction_conversion_cache[cache_key] = rate_to_base(
                                quote_currency,
                                base_currency,
                                item.trade_date,
                                persist=False,
                                workspace=current_workspace,
                            ).rate
                        except CurrencyConversionError:
                            transaction_conversion_cache[cache_key] = None
                    rate = transaction_conversion_cache[cache_key]
                    amount = None if rate is None else number(item.net_amount * rate)
            except CurrencyConversionError:
                amount = None
        base_amounts[item.pk] = amount
        if amount is None:
            invalid_instruments.add(item.instrument_id)

    # An unresolved FX leg invalidates the whole instrument history. Keeping
    # earlier buys while dropping an unconverted sell would overstate holdings.
    valid_transactions = [
        item for item in transactions if item.instrument_id not in invalid_instruments
    ]
    valid_identity_keys = {
        identity_by_instrument[item.instrument_id]
        for item in valid_transactions
        if identity_by_instrument.get(item.instrument_id)
    }
    prices_by_month = {
        month: {key: value for key, value in values.items() if key in valid_identity_keys}
        for month, values in prices_by_month.items()
    }
    prices_by_month = {month: values for month, values in prices_by_month.items() if values}

    def effective_date(item: Transaction) -> date:
        if kind == "fund" and item.settlement_date is not None:
            return item.settlement_date
        return item.trade_date

    transaction_rows = []
    for item in valid_transactions:
        row = _transaction_calculation_row(item)
        row["importe_base"] = number(base_amounts[item.pk])
        transaction_rows.append(row)
    months = set(prices_by_month)
    months.update(effective_date(item).isoformat()[:7] for item in valid_transactions)
    if not months:
        return []

    fund_map = (
        {
            instrument_calculation_row(item)["isin"]: instrument_calculation_row(item)
            for item in instruments
        }
        if kind == "fund"
        else {}
    )
    split_rows: list[dict[str, Any]] = (
        [
            {
                "isin": identifier(split.instrument, InstrumentIdentifier.Scheme.ISIN),
                "fecha": split.effective_date.isoformat(),
                "ratio": number(split.ratio),
            }
            for split in StockSplit.objects.filter(
                workspace=current_workspace, instrument_id__in=instrument_ids
            )
            .select_related("instrument")
            .prefetch_related("instrument__identifiers")
        ]
        if kind == "stock"
        else []
    )
    ordered_months = sorted(months)
    result: list[dict[str, Any]] = []
    for month in ordered_months:
        month_end = date.fromisoformat(f"{month}-01")
        if month_end.month == 12:
            month_end = date(month_end.year, 12, 31)
        else:
            month_end = date(month_end.year, month_end.month + 1, 1) - timedelta(days=1)
        prices_as_of: dict[str, Decimal] = {}
        for price_month in ordered_months:
            if price_month > month:
                break
            prices_as_of.update(
                {key: value for key, (_date, value) in prices_by_month.get(price_month, {}).items()}
            )
        rows_as_of = [
            row
            for row in transaction_rows
            if str(
                (
                    row.get("fecha_liquidacion")
                    if kind == "fund" and row.get("fecha_liquidacion")
                    else row.get("fecha_operacion")
                )
                or ""
            )[:10]
            <= month_end.isoformat()
        ]
        if kind == "fund":
            positions = calculate_fund_positions(rows_as_of, fund_map, prices_as_of)
        elif kind == "stock":
            positions = calculate_stock_positions(
                rows_as_of,
                prices_as_of,
                [item for item in split_rows if item["fecha"] <= month_end.isoformat()],
            )
        else:
            positions = calculate_crypto_positions(rows_as_of, prices_as_of)
        # A missing close is not a zero valuation.  Keep the open position at
        # its base cost until a valid close (or FX conversion) is available;
        # this is conservative and avoids manufacturing a P&L loss.
        value = 0.0
        for position in positions:
            marked_value = position.get("valor_actual")
            if marked_value not in (None, ""):
                value += number(marked_value)
            elif kind == "fund":
                value += number(position.get("total_invertido"))
            else:
                value += number(position.get("coste_total"))
        contribution = 0.0
        for item in valid_transactions:
            if effective_date(item).isoformat()[:7] != month:
                continue
            amount = number(base_amounts[item.pk])
            if item.is_saveback:
                continue
            if item.cash_flow_type == Transaction.CashFlowType.CONTRIBUTION:
                contribution += amount
            elif item.cash_flow_type == Transaction.CashFlowType.WITHDRAWAL:
                contribution -= amount
            elif item.operation_type == Transaction.OperationType.BUY:
                contribution += amount
            elif item.operation_type == Transaction.OperationType.SELL:
                contribution -= amount
        result.append(
            {
                "fecha": month,
                "cuenta_id": f"summary:{kind}",
                "valor": value,
                "aporte": contribution,
            }
        )
    return result


def _summary_snapshot_row(snapshot: AccountSnapshot) -> dict[str, Any]:
    """Keep summary's internal calculation keys independent of legacy IDs."""

    value_key = "saldo" if snapshot.account.kind == Account.Kind.SAVINGS else "valor"
    return {
        "fecha": snapshot.date.isoformat(),
        "cuenta_id": str(snapshot.account_id),
        value_key: number(
            snapshot.base_value if snapshot.base_value is not None else snapshot.value
        ),
        "aporte": number(
            snapshot.base_contribution
            if snapshot.base_contribution is not None
            else snapshot.contribution
        ),
        "intereses": number(
            snapshot.base_earnings if snapshot.base_earnings is not None else snapshot.earnings
        ),
    }


def _overview_calculation(request: Request) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_workspace = workspace(request)
    user = cast(User, request.user)
    included_sources, source_scope = effective_summary_sources(user, current_workspace)
    properties = real_estate_records(request)
    manual_assets = _summary_manual_assets(request, properties)
    all_savings = [
        _summary_snapshot_row(x)
        for x in AccountSnapshot.objects.select_related("account").filter(
            account__workspace=current_workspace, account__kind=Account.Kind.SAVINGS
        )
    ]
    all_investments = [
        _summary_snapshot_row(x)
        for x in AccountSnapshot.objects.select_related("account").filter(
            account__workspace=current_workspace, account__kind=Account.Kind.MANUAL_INVESTMENT
        )
    ]
    savings = all_savings if "savings" in included_sources else []
    investments = all_investments if "manual_investments" in included_sources else []
    selected_properties = properties if "crowdfunding" in included_sources else []
    source_series: dict[str, list[dict[str, Any]]] = {}
    for source_key, kind in (("funds", "fund"), ("stocks", "stock"), ("crypto", "crypto")):
        if source_key in included_sources:
            source_series[source_key] = _traded_source_history(request, kind)
    if "manual_assets" in included_sources:
        source_series["manual_assets"] = [
            {
                "fecha": item.valued_at.isoformat(),
                "cuenta_id": f"manual:{item.pk}",
                "valor": number(item.value),
                "aporte": 0,
            }
            for item in manual_assets
        ]
    history = monthly_history(
        savings,
        investments,
        selected_properties,
        source_series=source_series,
    )
    totals: dict[str, float] = {
        "savings": current_total(savings, "saldo"),
        "manual_investments": current_total(investments, "valor"),
        "crowdfunding": sum((live_capital(item) for item in selected_properties), 0.0),
        "funds": number(source_series.get("funds", [])[-1].get("valor"))
        if source_series.get("funds")
        else 0.0,
        "stocks": number(source_series.get("stocks", [])[-1].get("valor"))
        if source_series.get("stocks")
        else 0.0,
        "crypto": number(source_series.get("crypto", [])[-1].get("valor"))
        if source_series.get("crypto")
        else 0.0,
        "manual_assets": sum((number(item.value) for item in manual_assets), 0.0)
        if "manual_assets" in included_sources
        else 0.0,
    }
    totals = {key: (value if key in included_sources else 0.0) for key, value in totals.items()}
    latest_change = (
        float(history[-1]["total"]) - float(history[-2]["total"]) if len(history) > 1 else 0
    )
    total_interest = sum(number(item.get("intereses")) for item in savings + investments)
    breakdown = [
        {"key": key, "value": round(totals.get(key, 0.0), 2), "included": key in included_sources}
        for key in SUMMARY_SOURCE_KEYS
    ]
    summary_payload = {
        "total_savings": round(totals["savings"], 2),
        "total_investments": round(totals["manual_investments"], 2),
        "total_real_estate": round(totals["crowdfunding"], 2),
        "net_worth": round(sum(totals.values()), 2),
        "net_worth_change": round(latest_change, 2),
        "total_interest": round(total_interest, 2),
        "summary_sources": included_sources,
        "summary_sources_scope": source_scope,
        "source_breakdown": breakdown,
    }
    return summary_payload, history


@api_view(["GET"])
def summary(request: Request) -> Response:
    summary_payload, _history = _overview_calculation(request)
    return Response(summary_payload)


@api_view(["GET"])
def net_worth_history(request: Request) -> Response:
    _summary_payload, history = _overview_calculation(request)
    return Response(history)


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


def workspace_instruments(request: Request, kind: str) -> QuerySet[Instrument]:
    current_workspace = workspace(request)
    return (
        Instrument.objects.filter(kind=kind)
        .filter(
            Q(transactions__account__workspace=current_workspace)
            | Q(workspace_links__workspace=current_workspace)
        )
        .prefetch_related("identifiers")
        .distinct()
    )


def instruments(request: Request, kind: str) -> Response:
    queryset = workspace_instruments(request, kind)
    return Response([instrument_row(item) for item in queryset])


@api_view(["GET"])
def funds(request: Request) -> Response:
    return instruments(request, Instrument.Kind.FUND)


def _instrument_request_serializer(kind: str, data: dict[str, Any], *, update: bool) -> Any:
    """Validate a native instrument body and contextualize identifier schemes."""
    from apps.api.schemas import InstrumentRequestSerializer, InstrumentUpdateRequestSerializer

    return (InstrumentUpdateRequestSerializer if update else InstrumentRequestSerializer)(
        data=data, context={"instrument_kind": kind}
    )


def _instrument_metadata(item: Instrument, values: dict[str, Any]) -> None:
    metadata = dict(item.metadata or {})
    for field, legacy_field in (("asset_class", "tipo"), ("subtype", "subtipo")):
        if field not in values:
            continue
        value = values[field]
        metadata.pop(legacy_field, None)
        if value in (None, ""):
            metadata.pop(field, None)
        else:
            metadata[field] = str(value).strip()
    item.metadata = metadata


def _instrument_is_shared(item: Instrument, current_workspace: Workspace) -> bool:
    return bool(
        item.workspace_links.exclude(workspace=current_workspace).exists()
        or item.transactions.exclude(account__workspace=current_workspace).exists()
    )


@transaction.atomic
def create_instrument(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = _instrument_request_serializer(kind, payload(request), update=False)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    identifiers = [
        {
            **item,
            "value": normalize_instrument_identifier_value(item["scheme"], item["value"]),
        }
        for item in data["identifiers"]
    ]
    try:
        quote_currency = normalize_currency(data.get("quote_currency") or "EUR")
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    lock_keys = [
        key
        for item in identifiers
        for key in instrument_identifier_lock_keys(item["scheme"], item["value"], item["venue"])
    ]
    lock_logical_keys(lock_keys)
    identities = [
        identity
        for item in identifiers
        for identity in [
            InstrumentIdentifier.objects.select_related("instrument")
            .select_for_update()
            .filter(scheme=item["scheme"], value=item["value"], venue=item["venue"])
            .first()
        ]
        if identity is not None
    ]
    current_workspace = workspace(request)
    instruments_by_id = {identity.instrument_id: identity.instrument for identity in identities}
    if any(item.kind != kind for item in instruments_by_id.values()):
        return Response(
            {"error": _("The identifier already belongs to another asset type")}, status=400
        )
    if len(instruments_by_id) > 1:
        return Response(
            {"error": _("Instrument identifiers belong to different assets")}, status=400
        )
    item = next(iter(instruments_by_id.values()), None)
    if item is not None:
        item = Instrument.objects.select_for_update().get(pk=item.pk)
        # The identity query above used a row lock; reload the relation after
        # locking the parent so all subsequent validation sees one snapshot.
        identities = list(
            InstrumentIdentifier.objects.select_for_update().filter(instrument=item).order_by("id")
        )
        instruments_by_id = {identity.instrument_id: item for identity in identities}
    if item is not None and (
        item.workspace_links.filter(workspace=current_workspace).exists()
        or item.transactions.filter(account__workspace=current_workspace).exists()
    ):
        return Response({"error": _("The asset is already configured")}, status=400)
    shared = item is not None and _instrument_is_shared(item, current_workspace)
    if shared:
        assert item is not None
        known = set(item.identifiers.values_list("scheme", "value", "venue"))
        submitted = {(row["scheme"], row["value"], row["venue"]) for row in identifiers}
        if not submitted <= known:
            return Response({"error": _("The shared catalog asset cannot be changed")}, status=409)
    # Any new identifier must not already belong to another catalog item.  The
    # database constraint remains the final race-safe guard.
    for row in identifiers:
        owner = (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=row["scheme"], value=row["value"], venue=row["venue"])
            .exclude(instrument=item)
            .exists()
        )
        if owner:
            return Response(
                {"error": _("The identifier already belongs to another asset")}, status=400
            )
    existing_rows = list(item.identifiers.all()) if item is not None else []
    existing_keys = {(row.scheme, row.value, row.venue) for row in existing_rows}
    existing_slots = {(row.scheme, row.venue): row for row in existing_rows}
    if item is not None:
        try:
            validate_instrument_identifiers(
                {"identifiers": [_identifier_payload(row) for row in existing_rows]},
                kind=kind,
                require_identity=True,
                allow_fund_blank_yahoo=True,
            )
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=400)
    if item is not None and not shared:
        for row in identifiers:
            existing = existing_slots.get((row["scheme"], row["venue"]))
            if existing is not None and existing.value != row["value"]:
                return Response(
                    {"error": _("An existing instrument identifier cannot be changed")},
                    status=400,
                )
            if (
                row["is_primary"]
                and existing is None
                and any(
                    current.scheme == row["scheme"] and current.is_primary
                    for current in existing_rows
                )
            ):
                return Response(
                    {"error": _("Only one primary identifier per scheme is supported")},
                    status=400,
                )
    if item is None:
        item = Instrument.objects.create(
            kind=kind,
            name=data["name"].strip(),
            quote_currency=quote_currency,
            is_active=data.get("is_active", True),
        )
        _instrument_metadata(item, data)
        item.save(update_fields=("metadata", "updated_at"))
    else:
        # A catalog entry may be linked by another workspace.  Its canonical
        # fields and importer identities are intentionally immutable here.
        if not shared:
            item.name = data["name"].strip()
            item.quote_currency = quote_currency
            item.is_active = data.get("is_active", item.is_active)
            _instrument_metadata(item, data)
            item.save()
    assert item is not None
    if not shared:
        for row in identifiers:
            key = (row["scheme"], row["value"], row["venue"])
            if key not in existing_keys:
                InstrumentIdentifier.objects.create(instrument=item, **row)
    WorkspaceInstrument.objects.get_or_create(workspace=current_workspace, instrument=item)
    cache.clear()
    return Response(instrument_row(item), status=201)


@api_view(["GET", "POST"])
def stocks(request: Request) -> Response:
    if request.method == "POST":
        return create_instrument(request, Instrument.Kind.STOCK)
    return instruments(request, Instrument.Kind.STOCK)


@api_view(["GET", "POST"])
def cryptos(request: Request) -> Response:
    if request.method == "POST":
        return create_instrument(request, Instrument.Kind.CRYPTO)
    return instruments(request, Instrument.Kind.CRYPTO)


def _identifier_payload(item: InstrumentIdentifier) -> dict[str, Any]:
    return {
        "scheme": item.scheme,
        "value": item.value,
        "venue": item.venue,
        "is_primary": item.is_primary,
    }


def _effective_instrument_identifiers(
    kind: str,
    existing: list[InstrumentIdentifier],
    submitted: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]] | None, Response | None]:
    """Merge a native identifier patch and validate the complete resulting set."""

    existing_rows = [_identifier_payload(item) for item in existing]
    try:
        existing_rows = validate_instrument_identifiers(
            {"identifiers": existing_rows},
            kind=kind,
            require_identity=True,
            allow_fund_blank_yahoo=True,
        )["identifiers"]
    except serializers.ValidationError as exc:
        return None, Response(exc.detail, status=400)

    by_slot = {(row["scheme"], row["venue"]): row for row in existing_rows}
    for row in submitted:
        slot = (row["scheme"], row["venue"])
        if not row["value"]:
            # A blank Yahoo value is an explicit native clear operation for a
            # fund. It targets only this venue and never removes ISIN or other
            # importer identities.
            by_slot.pop(slot, None)
            continue
        current = by_slot.get(slot)
        if current is not None and current["value"] != row["value"]:
            if row["scheme"] != InstrumentIdentifier.Scheme.YAHOO:
                return None, Response(
                    {"error": _("The canonical instrument identifier cannot be changed")},
                    status=400,
                )
        by_slot[slot] = row

    try:
        effective = validate_instrument_identifiers(
            {"identifiers": list(by_slot.values())},
            kind=kind,
            require_identity=True,
            allow_fund_blank_yahoo=True,
        )["identifiers"]
    except serializers.ValidationError as exc:
        return None, Response(exc.detail, status=400)
    return effective, None


@transaction.atomic
def update_instrument(request: Request, instrument_id: UUID, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    current_workspace = workspace(request)
    visible_id = (
        Instrument.objects.filter(pk=instrument_id, kind=kind)
        .filter(
            Q(workspace_links__workspace=current_workspace)
            | Q(transactions__account__workspace=current_workspace)
        )
        .values_list("pk", flat=True)
        .first()
    )
    if visible_id is None:
        raise Http404
    item = get_object_or_404(Instrument.objects.get_queryset(), pk=visible_id, kind=kind)
    serializer = _instrument_request_serializer(kind, payload(request), update=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    if _instrument_is_shared(item, current_workspace):
        return Response(
            {"error": _("This catalog asset is configured in another workspace")}, status=409
        )
    identifiers = list(data.get("identifiers", []))
    existing_identifiers = list(item.identifiers.all())
    effective_identifiers, validation_error = _effective_instrument_identifiers(
        kind, existing_identifiers, identifiers
    )
    if validation_error is not None:
        return validation_error
    assert effective_identifiers is not None
    quote_currency: str | None = None
    if "quote_currency" in data:
        try:
            quote_currency = normalize_currency(data["quote_currency"])
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=400)

    lock_keys = [
        key
        for row in [
            *[_identifier_payload(item) for item in existing_identifiers],
            *identifiers,
        ]
        for key in instrument_identifier_lock_keys(row["scheme"], row["value"], row["venue"])
    ]
    lock_logical_keys(lock_keys)

    # Advisory keys are acquired before any row lock. Re-read and validate the
    # locked snapshot so a concurrent importer or editor cannot invalidate the
    # no-write validation above.
    item = Instrument.objects.select_for_update().get(pk=visible_id, kind=kind)
    locked_identifiers = list(
        InstrumentIdentifier.objects.select_for_update().filter(instrument=item).order_by("id")
    )
    if _instrument_is_shared(item, current_workspace):
        return Response(
            {"error": _("This catalog asset is configured in another workspace")}, status=409
        )
    effective_identifiers, validation_error = _effective_instrument_identifiers(
        kind, locked_identifiers, identifiers
    )
    if validation_error is not None:
        return validation_error
    assert effective_identifiers is not None
    for row in effective_identifiers:
        if (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=row["scheme"], value=row["value"], venue=row["venue"])
            .exclude(instrument=item)
            .exists()
        ):
            return Response(
                {"error": _("The identifier already belongs to another asset")}, status=400
            )

    # All checks have completed. From this point on, writes cannot fail due to
    # request validation or identity conflicts.
    existing_by_slot = {(row.scheme, row.venue): row for row in locked_identifiers}
    desired_by_slot = {(row["scheme"], row["venue"]): row for row in effective_identifiers}
    cleared_slots = {(row["scheme"], row["venue"]) for row in identifiers if not row["value"]}
    for slot, existing in existing_by_slot.items():
        desired = desired_by_slot.get(slot)
        if slot in cleared_slots:
            existing.delete()
        elif desired is not None and existing.is_primary and not desired["is_primary"]:
            existing.is_primary = False
            existing.save(update_fields=("is_primary",))
    for slot, row in desired_by_slot.items():
        existing_row = existing_by_slot.get(slot)
        if existing_row is None:
            InstrumentIdentifier.objects.create(instrument=item, **row)
        elif existing_row.value != row["value"] or existing_row.is_primary != row["is_primary"]:
            existing_row.value = row["value"]
            existing_row.is_primary = row["is_primary"]
            existing_row.save(update_fields=("value", "is_primary"))
    if "name" in data:
        item.name = str(data["name"]).strip()
    if quote_currency is not None:
        item.quote_currency = quote_currency
    if "is_active" in data:
        item.is_active = data["is_active"]
    _instrument_metadata(item, data)
    item.save()
    item.refresh_from_db()
    cache.clear()
    return Response(instrument_row(item))


@api_view(["PUT"])
def fund_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.FUND)


@api_view(["PUT"])
def stock_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.STOCK)


@api_view(["PUT"])
def crypto_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.CRYPTO)


def _selected_traded_account(request: Request, kind: str) -> Account | None | Response:
    """Validate and resolve an optional native account filter."""

    if "cuenta_id" in request.query_params:
        return Response({"error": _("Use account_id for account filtering")}, status=400)
    value = request.query_params.get("account_id")
    if not value or value == "all":
        return None
    try:
        account_uuid = UUID(value)
    except (TypeError, ValueError):
        return Response({"error": _("A valid account ID was expected")}, status=400)
    account_kind = {
        Instrument.Kind.FUND: Account.Kind.FUNDS,
        Instrument.Kind.STOCK: Account.Kind.STOCKS,
        Instrument.Kind.CRYPTO: Account.Kind.CRYPTO,
    }[Instrument.Kind(kind)]
    return find_traded_account(request, account_kind, account_uuid)


def transaction_queryset(
    request: Request, kind: str, selected_account: Account | None = None
) -> QuerySet[Transaction]:
    queryset = (
        Transaction.objects.select_related("account", "instrument")
        .prefetch_related("instrument__identifiers")
        .filter(account__workspace=workspace(request), instrument__kind=kind)
    )
    if selected_account is not None:
        queryset = queryset.filter(account=selected_account)
    return queryset


def transaction_list(request: Request, kind: str) -> Response:
    selected_account = _selected_traded_account(request, kind)
    if isinstance(selected_account, Response):
        return selected_account
    queryset = transaction_queryset(request, kind, selected_account)
    return Response([transaction_row(item) for item in queryset.order_by("trade_date")])


def _transaction_calculation_list(
    request: Request, kind: str, selected_account: Account | None = None
) -> list[dict[str, Any]]:
    """Return private legacy-shaped rows for pure position calculations."""
    queryset = transaction_queryset(request, kind, selected_account)
    return [_transaction_calculation_row(item) for item in queryset.order_by("trade_date")]


FUND_MANUAL_OPERATIONS = {
    Transaction.OperationType.BUY: (
        Transaction.OperationType.BUY,
        Transaction.CashFlowType.CONTRIBUTION,
    ),
    Transaction.OperationType.TRANSFER_IN: (
        Transaction.OperationType.TRANSFER_IN,
        Transaction.CashFlowType.INTERNAL,
    ),
    Transaction.OperationType.TRANSFER_OUT: (
        Transaction.OperationType.TRANSFER_OUT,
        Transaction.CashFlowType.INTERNAL,
    ),
    Transaction.OperationType.SELL: (
        Transaction.OperationType.SELL,
        Transaction.CashFlowType.WITHDRAWAL,
    ),
}
CRYPTO_MANUAL_OPERATIONS = {
    Transaction.OperationType.BUY: (Transaction.OperationType.BUY, Transaction.CashFlowType.NONE),
    Transaction.OperationType.SELL: (Transaction.OperationType.SELL, Transaction.CashFlowType.NONE),
}
TRANSACTION_EXTERNAL_ID_CONSTRAINT = "transaction_external_id_unique"


def _is_transaction_external_id_conflict(error: IntegrityError) -> bool:
    """Recognize only the scoped external-id uniqueness constraint."""
    cause = error.__cause__
    constraint_name = getattr(getattr(cause, "diag", None), "constraint_name", None)
    if constraint_name:
        return str(constraint_name) == TRANSACTION_EXTERNAL_ID_CONSTRAINT

    error_text = " ".join(str(part) for part in (cause, error) if part).casefold()
    if TRANSACTION_EXTERNAL_ID_CONSTRAINT.casefold() in error_text:
        return True
    if "unique constraint failed:" not in error_text:
        return False
    table = Transaction._meta.db_table.casefold()
    return f"{table}.account_id" in error_text and f"{table}.external_id" in error_text


def save_manual_transaction(
    request: Request,
    kind: str,
    item: Transaction | None = None,
) -> Response:
    raw_data = payload(request)
    if "cuenta_id" in raw_data or "cuenta_id_original" in raw_data:
        return Response({"error": _("Use account_id for account selection")}, status=400)
    data = dict(raw_data)
    for optional_field in ("settlement_date", "fx_rate_to_base", "fx_rate_date"):
        if data.get(optional_field) == "":
            data[optional_field] = None
    serializer_class = {
        Instrument.Kind.FUND: FundTransactionRequestSerializer,
        Instrument.Kind.STOCK: StockTransactionRequestSerializer,
        Instrument.Kind.CRYPTO: CryptoTransactionRequestSerializer,
    }[Instrument.Kind(kind)]
    serializer = serializer_class(data=data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    account_kind = {
        Instrument.Kind.FUND: Account.Kind.FUNDS,
        Instrument.Kind.STOCK: Account.Kind.STOCKS,
        Instrument.Kind.CRYPTO: Account.Kind.CRYPTO,
    }[Instrument.Kind(kind)]
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
        if kind == Instrument.Kind.CRYPTO
        else InstrumentIdentifier.Scheme.ISIN
    )
    asset_key = "symbol" if kind == Instrument.Kind.CRYPTO else "isin"
    operations = (
        FUND_MANUAL_OPERATIONS if kind == Instrument.Kind.FUND else CRYPTO_MANUAL_OPERATIONS
    )
    operation_label = cast(Transaction.OperationType, data.get("operation_type", ""))
    if operation_label not in operations:
        return Response({"error": _("The transaction type is not valid")}, status=400)
    try:
        account_uuid = UUID(str(data["account_id"]))
        account = find_traded_account(request, account_kind, account_uuid)
        instrument = workspace_instrument(request, scheme, str(data[asset_key]))
        if instrument.kind != kind:
            return Response({"error": _("The asset does not belong in this section")}, status=400)
        trade_date = date.fromisoformat(str(data["trade_date"])[:10])
        settlement_value = str(data.get("settlement_date") or "")[:10]
        settlement_date = date.fromisoformat(settlement_value) if settlement_value else None
        quantity = decimal(data["quantity"])
        unit_price = decimal(data["unit_price"])
        amount = decimal(data["net_amount"])
        fee = decimal(data.get("fee"))
    except (KeyError, TypeError, ValueError):
        return Response({"error": _("Check the required transaction fields")}, status=400)
    if quantity <= 0 or unit_price < 0 or amount < 0 or fee < 0:
        return Response(
            {"error": _("Quantity, price, amount, and fee must be positive")},
            status=400,
        )

    operation_type, cash_flow_type = operations[operation_label]
    creating = item is None
    previous_account_id = item.account_id if item is not None else None
    if (
        item is not None
        and item.account_id != account.id
        and item.external_id is not None
        and Transaction.objects.filter(account=account, external_id=item.external_id)
        .exclude(pk=item.pk)
        .exists()
    ):
        return Response(
            {
                "error": _(
                    "A transaction with this provider ID already exists in the target account"
                )
            },
            status=400,
        )
    if item is None:
        # Manual transactions have no provider identity.  The model UUID is
        # their sole public and persistent identity.
        item = Transaction()
    item.account = account
    if previous_account_id is not None and previous_account_id != account.id:
        item.import_batch = None
    item.instrument = instrument
    item.trade_date = trade_date
    item.settlement_date = settlement_date
    item.operation_type = operation_type
    item.cash_flow_type = cash_flow_type
    item.quantity = quantity
    item.unit_price = unit_price
    item.net_amount = amount
    item.fee = fee
    provider = provider_name(account).casefold()
    requested_saveback = data.get("is_saveback", False) in {
        True,
        "1",
        "true",
        "True",
    }
    item.is_saveback = bool(
        kind == Instrument.Kind.STOCK and "trade republic" in provider and requested_saveback
    )
    if "market" in data:
        item.market = str(data["market"])
    try:
        currency = normalize_currency(
            data.get("currency") or (item.currency if not creating else account.currency)
        )
        base_currency = normalize_currency(account.workspace.base_currency)
        provided_rate = (
            decimal(data["fx_rate_to_base"])
            if data.get("fx_rate_to_base") not in (None, "")
            else None
        )
        provided_rate_date = (
            date.fromisoformat(str(data["fx_rate_date"])[:10]) if data.get("fx_rate_date") else None
        )
        conversion = rate_to_base(
            currency,
            base_currency,
            settlement_date or trade_date,
            provided_rate=provided_rate,
            provided_date=provided_rate_date,
            provided_source=str(data.get("fx_source") or "manual"),
            workspace=account.workspace,
        )
    except (CurrencyConversionError, ValueError) as exc:
        return Response({"error": str(exc)}, status=400)
    item.currency = currency
    item.base_currency = base_currency
    item.base_unit_price = unit_price * conversion.rate
    item.base_net_amount = amount * conversion.rate
    item.base_fee = fee * conversion.rate
    item.fx_rate_to_base = conversion.rate
    item.fx_rate_date = conversion.rate_date
    item.fx_source = conversion.source
    if item.external_id is None:
        item.provider_operation_type = _calculation_operation_label(item)
        item.raw_metadata = {
            **item.raw_metadata,
            "legacy_name": instrument.name,
            "manual": True,
        }
    try:
        # The precheck avoids the common query, while this atomic save closes
        # the race with another import or edit claiming the same provider ID.
        with transaction.atomic():
            item.save()
    except IntegrityError as exc:
        if not _is_transaction_external_id_conflict(exc):
            raise
        return Response(
            {
                "error": _(
                    "A transaction with this provider ID already exists in the target account"
                )
            },
            status=400,
        )
    cache.clear()
    return Response(transaction_row(item), status=201 if creating else 200)


def transaction_collection(request: Request, kind: str) -> Response:
    if request.method == "GET":
        return transaction_list(request, kind)
    if denied := forbidden_if_readonly(request):
        return denied
    return save_manual_transaction(request, kind)


@api_view(["GET", "POST"])
def orders(request: Request) -> Response:
    return transaction_collection(request, Instrument.Kind.FUND)


@api_view(["GET", "POST"])
def stock_orders(request: Request) -> Response:
    return transaction_collection(request, Instrument.Kind.STOCK)


@api_view(["GET", "POST"])
def crypto_orders(request: Request) -> Response:
    return transaction_collection(request, Instrument.Kind.CRYPTO)


def transaction_detail(request: Request, kind: str, transaction_id: UUID) -> Response:
    """Edit or remove one transaction by UUID within the active workspace."""
    if denied := forbidden_if_readonly(request):
        return denied
    if request.method == "PUT":
        data = payload(request)
        if "cuenta_id" in data or "cuenta_id_original" in data:
            return Response({"error": _("Use account_id for account selection")}, status=400)
        queryset = Transaction.objects.filter(
            account__workspace=workspace(request),
            instrument__kind=kind,
            pk=transaction_id,
        )
        item = get_object_or_404(queryset.select_related("instrument"))
        return save_manual_transaction(request, item.instrument.kind, item)
    if "cuenta_id" in request.query_params:
        return Response({"error": _("Use account_id for account selection")}, status=400)
    item = get_object_or_404(
        Transaction.objects.filter(
            account__workspace=workspace(request),
            instrument__kind=kind,
            pk=transaction_id,
        )
    )
    item.delete()
    cache.clear()
    return Response({"ok": True})


@api_view(["PUT", "DELETE"])
def fund_transaction_detail(request: Request, transaction_id: UUID) -> Response:
    return transaction_detail(request, Instrument.Kind.FUND, transaction_id)


@api_view(["PUT", "DELETE"])
def stock_transaction_detail(request: Request, transaction_id: UUID) -> Response:
    return transaction_detail(request, Instrument.Kind.STOCK, transaction_id)


@api_view(["PUT", "DELETE"])
def crypto_transaction_detail(request: Request, transaction_id: UUID) -> Response:
    return transaction_detail(request, Instrument.Kind.CRYPTO, transaction_id)


def _selected_market_prices(
    request: Request, kind: str
) -> tuple[Workspace, list[MarketPrice | WorkspaceMarketPriceOverride]]:
    current_workspace = workspace(request)
    instruments = workspace_instruments(request, kind)
    queryset = (
        MarketPrice.objects.select_related("instrument")
        .prefetch_related("instrument__identifiers")
        .filter(
            instrument__in=instruments,
            granularity=MarketPrice.Granularity.SPOT,
        )
        .order_by("instrument_id", "-quoted_at", "-created_at")
    )
    latest_by_instrument: dict[Any, MarketPrice] = {}
    for provider_price in queryset:
        latest_by_instrument.setdefault(provider_price.instrument_id, provider_price)
    overrides = (
        WorkspaceMarketPriceOverride.objects.select_related("instrument")
        .prefetch_related("instrument__identifiers")
        .filter(
            workspace=current_workspace,
            instrument__in=instruments,
        )
    )
    selected: dict[Any, MarketPrice | WorkspaceMarketPriceOverride] = dict(latest_by_instrument)
    for override in overrides:
        existing = selected.get(override.instrument_id)
        if existing is None or override.quoted_at >= existing.quoted_at:
            selected[override.instrument_id] = override
    return current_workspace, list(selected.values())


def price_list(request: Request, kind: str) -> Response:
    current_workspace, selected_prices = _selected_market_prices(request, kind)
    base_currency = normalize_currency(current_workspace.base_currency)

    rows = []
    try:
        for selected_price in selected_prices:
            conversion = rate_to_base(
                selected_price.currency,
                base_currency,
                selected_price.quoted_at.date(),
                workspace=current_workspace,
            )
            rows.append(
                price_row(
                    selected_price,
                    converted_price=selected_price.close * conversion.rate,
                    base_currency=base_currency,
                    fx_rate=conversion.rate,
                    fx_rate_date=conversion.rate_date,
                    fx_source=conversion.source,
                )
            )
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=502)
    return Response(rows)


def _calculation_price_list(request: Request, kind: str) -> Response:
    """Return the private transitional price shape used by domain calculators."""
    current_workspace, selected_prices = _selected_market_prices(request, kind)
    base_currency = normalize_currency(current_workspace.base_currency)
    rows = []
    try:
        for selected_price in selected_prices:
            conversion = rate_to_base(
                selected_price.currency,
                base_currency,
                selected_price.quoted_at.date(),
                workspace=current_workspace,
            )
            rows.append(
                price_calculation_row(
                    selected_price,
                    converted_price=selected_price.close * conversion.rate,
                    base_currency=base_currency,
                    fx_rate=conversion.rate,
                    fx_rate_date=conversion.rate_date,
                    fx_source=conversion.source,
                )
            )
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=502)
    return Response(rows)


@api_view(["GET"])
def fund_prices(request: Request) -> Response:
    return price_list(request, "fund")


@api_view(["GET"])
def stock_prices(request: Request) -> Response:
    return price_list(request, "stock")


@api_view(["GET"])
def crypto_prices(request: Request) -> Response:
    return price_list(request, "crypto")


def update_price(request: Request, instrument_id: UUID, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    current_workspace = workspace(request)
    instrument = (
        Instrument.objects.filter(pk=instrument_id, kind=kind)
        .filter(
            Q(workspace_links__workspace=current_workspace)
            | Q(transactions__account__workspace=current_workspace)
        )
        .first()
    )
    if instrument is None:
        raise Http404
    serializer = PriceRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    try:
        value = data["close"]
        currency = normalize_currency(
            data.get("currency") or instrument.quote_currency or current_workspace.base_currency
        )
    except (ValueError, CurrencyConversionError) as exc:
        return Response({"error": str(exc)}, status=400)
    if value < 0:
        return Response({"error": _("The price cannot be negative")}, status=400)
    now = timezone.now()
    WorkspaceMarketPriceOverride.objects.update_or_create(
        workspace=workspace(request),
        instrument=instrument,
        defaults={
            "quoted_at": now,
            "close": value,
            "currency": currency,
            "source": "manual",
        },
    )
    cache.clear()
    return Response({"ok": True})


@api_view(["PUT"])
def fund_price_detail(request: Request, instrument_id: UUID) -> Response:
    return update_price(request, instrument_id, "fund")


@api_view(["PUT"])
def stock_price_detail(request: Request, instrument_id: UUID) -> Response:
    return update_price(request, instrument_id, "stock")


def analyzed_positions(
    request: Request,
    kind: str,
    rows: list[dict[str, Any]],
    *,
    account_filter: int | str | UUID | None = None,
) -> list[dict[str, Any]]:
    prices = _calculation_price_list(request, kind).data
    key = "symbol" if kind == "crypto" else "isin"
    price_map = {row[key]: row["precio"] for row in prices}
    if kind == "stock":
        if request.query_params.get("ignore_savebacks", "").casefold() == "true":
            rows = [
                {
                    **row,
                    "importe_neto": 0,
                    "importe_base": 0,
                }
                if row.get("es_saveback")
                and "trade republic" in str(row.get("plataforma", "")).casefold()
                else row
                for row in rows
            ]
        splits = [
            {
                "isin": identifier(s.instrument, InstrumentIdentifier.Scheme.ISIN),
                "fecha": s.effective_date.isoformat(),
                "ratio": number(s.ratio),
            }
            for s in StockSplit.objects.filter(workspace=workspace(request))
            .select_related("instrument")
            .prefetch_related("instrument__identifiers")
        ]
        return calculate_stock_positions(rows, price_map, splits)
    if kind == "crypto":
        return calculate_crypto_positions(rows, price_map)
    fund_map = {
        instrument_calculation_row(item)["isin"]: instrument_calculation_row(item)
        for item in workspace_instruments(request, Instrument.Kind.FUND)
    }
    return calculate_fund_positions(rows, fund_map, price_map, account_id=account_filter)


def analysis(request: Request, kind: str) -> Response:
    selected_account = _selected_traded_account(request, kind)
    if isinstance(selected_account, Response):
        return selected_account
    account_filter = selected_account.id if selected_account is not None else None
    rows = _transaction_calculation_list(request, kind, selected_account)
    positions = analyzed_positions(request, kind, rows, account_filter=account_filter)
    base_currency = normalize_currency(workspace(request).base_currency)
    instruments = workspace_instruments(request, kind)
    return Response(
        native_position_rows(
            positions,
            instruments,
            kind=kind,
            base_currency=base_currency,
        )
    )


@api_view(["GET"])
def fund_analysis(request: Request) -> Response:
    return analysis(request, "fund")


@api_view(["GET"])
def stock_analysis(request: Request) -> Response:
    return analysis(request, "stock")


@api_view(["GET"])
def crypto_analysis(request: Request) -> Response:
    return analysis(request, "crypto")


@api_view(["GET"])
def portfolio_analysis(request: Request) -> Response:
    result: list[dict[str, Any]] = []
    properties = real_estate_records(request)
    manual_assets = _summary_manual_assets(request, properties)
    for item in manual_assets:
        value = number(item.value)
        if value <= 0:
            continue
        platform = provider_name(item)
        result.append(
            {
                "id": f"manual:{item.pk}",
                "nombre": item.name,
                "identificador": "",
                "clase": item.asset_class or "Otros",
                "subtipo": item.subtype or "Posición manual",
                "cuenta": platform or "Posiciones manuales",
                "cuenta_id": f"manual:{item.pk}",
                "plataforma": platform or "Manual",
                "valor": value,
                "origen": "manual",
            }
        )

    for project in properties:
        value = live_capital(project)
        if value <= 0:
            continue
        platform = str(project.get("platform") or "Inmobiliario")
        result.append(
            {
                "id": f"real-estate:{project['id']}",
                "nombre": project["name"],
                "identificador": "",
                "clase": "Inmobiliario",
                "subtipo": "Proyecto inmobiliario",
                "cuenta": platform,
                "cuenta_id": f"real-estate:{platform}",
                "plataforma": platform,
                "valor": value,
                "origen": "real_estate",
            }
        )

    account_kinds = {
        "fund": Account.Kind.FUNDS,
        "stock": Account.Kind.STOCKS,
        "crypto": Account.Kind.CRYPTO,
    }
    default_classes = {
        "fund": "Fondos",
        "stock": "Acciones y ETF",
        "crypto": "Crypto",
    }
    default_subtypes = {
        "fund": "Fondo de inversión",
        "stock": "Acción o ETF",
        "crypto": "Criptomoneda",
    }
    for kind, account_kind in account_kinds.items():
        all_rows = _transaction_calculation_list(request, kind)
        identity_key = "symbol" if kind == "crypto" else "isin"
        for account in kind_accounts(request, account_kind):
            account_uuid = str(account.id)
            account_rows = [row for row in all_rows if str(row["cuenta_id"]) == account_uuid]
            if not account_rows:
                continue
            positions = analyzed_positions(
                request,
                kind,
                account_rows,
                account_filter=account.id if kind == "fund" else None,
            )
            for position in positions:
                value = number(position.get("valor_actual"))
                if value <= 0:
                    continue
                result.append(
                    {
                        "id": f"{kind}:{account_uuid}:{position[identity_key]}",
                        "nombre": position.get("nombre") or position[identity_key],
                        "identificador": position[identity_key],
                        "clase": position.get("tipo") or default_classes[kind],
                        "subtipo": position.get("subtipo") or default_subtypes[kind],
                        "cuenta": account.name,
                        "cuenta_id": f"{kind}:{account_uuid}",
                        "plataforma": provider_name(account),
                        "valor": value,
                        "origen": kind,
                    }
                )

    result.sort(key=lambda item: (-item["valor"], item["nombre"]))
    total = sum(item["valor"] for item in result)
    return Response(
        {
            "total": round(total, 2),
            "items": [
                {
                    **item,
                    "peso": round(item["valor"] / total, 8) if total else 0,
                }
                for item in result
            ],
        }
    )


@api_view(["GET", "POST"])
def stock_splits(request: Request) -> Response:
    current_workspace = workspace(request)
    queryset = StockSplit.objects.filter(
        workspace=current_workspace,
        instrument__kind=Instrument.Kind.STOCK,
    )
    if request.method == "GET":
        return Response([_stock_split_row(split) for split in queryset])
    if denied := forbidden_if_readonly(request):
        return denied

    serializer = StockSplitRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    instrument = (
        workspace_instruments(request, Instrument.Kind.STOCK)
        .filter(pk=data["instrument_id"])
        .first()
    )
    if instrument is None:
        return Response(
            {"error": _("The instrument is not available in this workspace")}, status=400
        )

    with transaction.atomic():
        locked_instrument = Instrument.objects.select_for_update().get(pk=instrument.pk)
        split, _created = StockSplit.objects.select_for_update().update_or_create(
            workspace=current_workspace,
            instrument=locked_instrument,
            effective_date=data["effective_date"],
            defaults={
                "ratio": data["ratio"],
                "source": data["source"],
                "confirmed_by": cast(User, request.user),
            },
        )
    cache.clear()
    return Response(_stock_split_row(split), status=200)


@api_view(["DELETE"])
def stock_split_detail(request: Request, split_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    split = get_object_or_404(
        StockSplit.objects.filter(
            workspace=workspace(request),
            instrument__kind=Instrument.Kind.STOCK,
        ),
        pk=split_id,
    )
    split.delete()
    cache.clear()
    return Response({"ok": True})


def _stock_split_row(split: StockSplit) -> dict[str, Any]:
    """Return the native public representation of a stock split."""
    return {
        "id": str(split.id),
        "instrument_id": str(split.instrument_id),
        "effective_date": split.effective_date.isoformat(),
        "ratio": number(split.ratio),
        "source": split.source,
    }


def workspace_instrument(request: Request, scheme: str, value: str) -> Instrument:
    identity = get_object_or_404(
        InstrumentIdentifier.objects.select_related("instrument"),
        scheme=scheme,
        value=value,
        venue="",
    )
    current_workspace = workspace(request)
    if not (
        identity.instrument.transactions.filter(account__workspace=current_workspace).exists()
        or identity.instrument.workspace_links.filter(workspace=current_workspace).exists()
    ):
        from django.http import Http404

        raise Http404
    return identity.instrument


def yahoo_ticker(instrument: Instrument) -> str:
    identity = select_identifier(instrument.identifiers.all(), InstrumentIdentifier.Scheme.YAHOO)
    if identity and identity.value:
        return identity.value
    isin = select_identifier(instrument.identifiers.all(), InstrumentIdentifier.Scheme.ISIN)
    if not isin:
        raise MarketDataError(_("The instrument does not have a ticker configured"))
    found = search(isin.value)
    ticker = str(found.get("ticker", "")).strip()
    if not ticker or len(ticker) > 120:
        raise MarketDataError(_("The market-data provider returned an invalid ticker"))
    with transaction.atomic():
        lock_logical_keys(
            [
                *instrument_identifier_lock_keys(InstrumentIdentifier.Scheme.ISIN, isin.value),
                *instrument_identifier_lock_keys(InstrumentIdentifier.Scheme.YAHOO, ticker),
            ]
        )
        locked_instrument = Instrument.objects.select_for_update().get(pk=instrument.pk)
        current = select_identifier(
            InstrumentIdentifier.objects.select_for_update().filter(
                instrument=locked_instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
            ),
            InstrumentIdentifier.Scheme.YAHOO,
        )
        if current and current.value:
            return current.value
        ticker_owner = (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=InstrumentIdentifier.Scheme.YAHOO, value=ticker, venue="")
            .exclude(instrument=locked_instrument)
            .first()
        )
        if ticker_owner:
            raise MarketDataError(_("The ticker already belongs to another asset"))
        InstrumentIdentifier.objects.update_or_create(
            instrument=locked_instrument,
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            defaults={"value": ticker, "venue": ""},
        )
    return ticker


def market_chart(request: Request, kind: str, instrument_id: UUID) -> Response:
    instrument = get_object_or_404(workspace_instruments(request, kind), pk=instrument_id)
    try:
        ticker = yahoo_ticker(instrument)
        interval = request.query_params.get("interval", "1d")
        meta, points = yahoo_chart(
            ticker,
            range_name=request.query_params.get("range", "1y"),
            interval=interval if interval in {"1d", "1wk", "1mo"} else "1d",
            start=request.query_params.get("start"),
            end=request.query_params.get("end"),
        )
        currency = normalize_currency(meta.get("currency") or "EUR")
        base_currency = normalize_currency(workspace(request).base_currency)
        try:
            conversions = rates_to_base(
                currency,
                base_currency,
                [date.fromisoformat(str(row["fecha"])) for row in points],
                workspace=workspace(request),
            )
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=502)
        if kind == "fund":
            data = [
                {
                    "date": row["fecha"],
                    "close": round(
                        float(row["precio"])
                        * float(conversions[date.fromisoformat(row["fecha"])].rate),
                        6,
                    ),
                }
                for row in points
            ]
        else:
            data = [
                {
                    "date": row["fecha"],
                    **{
                        key: round(
                            float(row[key])
                            * float(conversions[date.fromisoformat(row["fecha"])].rate),
                            6,
                        )
                        for key in ("open", "high", "low", "close")
                    },
                }
                for row in points
            ]
        return Response(
            {
                "instrument_id": str(instrument.id),
                "ticker": ticker,
                "currency": currency,
                "base_currency": base_currency,
                "range": request.query_params.get("range", "1y"),
                "data": data,
            }
        )
    except MarketDataError as exc:
        return Response({"error": str(exc)}, status=502)


@api_view(["GET"])
def fund_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "fund", instrument_id)


@api_view(["GET"])
def stock_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "stock", instrument_id)


@api_view(["GET"])
def crypto_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "crypto", instrument_id)


def fetch_prices(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    instruments_qs = workspace_instruments(request, kind)
    base_currency = normalize_currency(workspace(request).base_currency)
    results = []
    for instrument in instruments_qs:
        result: dict[str, Any] = {
            "instrument_id": str(instrument.id),
            "base_close": None,
            "close": None,
            "currency": None,
            "ticker": None,
            "error": None,
        }
        try:
            ticker = yahoo_ticker(instrument)
            original, raw_currency = quote_price(ticker)
            currency = normalize_currency(raw_currency)
            if instrument.quote_currency != currency:
                instrument.quote_currency = currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            conversion = rate_to_base(
                currency,
                base_currency,
                timezone.localdate(),
                workspace=workspace(request),
            )
            conversion_rate = conversion.rate
            price_base = Decimal(str(original)) * conversion_rate
            MarketPrice.objects.filter(
                instrument=instrument, granularity="spot", source="yahoo"
            ).delete()
            MarketPrice.objects.create(
                instrument=instrument,
                quoted_at=timezone.now(),
                granularity="spot",
                close=original,
                currency=currency,
                source="yahoo",
            )
            result.update(
                ticker=ticker,
                base_close=number(round(price_base, 6)),
                close=number(original),
                currency=currency,
            )
        except (MarketDataError, CurrencyConversionError) as exc:
            result["error"] = str(exc)
        results.append(result)
    cache.clear()
    return Response({"results": results})


@api_view(["POST"])
def fetch_fund_prices(request: Request) -> Response:
    return fetch_prices(request, "fund")


@api_view(["POST"])
def fetch_stock_prices(request: Request) -> Response:
    return fetch_prices(request, "stock")


@api_view(["POST"])
def fetch_crypto_prices(request: Request) -> Response:
    return fetch_prices(request, "crypto")


PERFORMANCE_KINDS = {
    "fund": (Instrument.Kind.FUND, Account.Kind.FUNDS, InstrumentIdentifier.Scheme.ISIN),
    "stock": (Instrument.Kind.STOCK, Account.Kind.STOCKS, InstrumentIdentifier.Scheme.ISIN),
    "crypto": (
        Instrument.Kind.CRYPTO,
        Account.Kind.CRYPTO,
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL,
    ),
}


def _performance_period(
    request: Request,
) -> tuple[str, str | None, str | None, date | None, date | None] | Response:
    range_name = request.query_params.get("range", "1y")
    if range_name not in {"6m", "1y", "2y"}:
        range_name = "1y"
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    if bool(start) != bool(end):
        return Response({"error": _("You must provide both a start and an end date")}, status=400)
    if not start or not end:
        return range_name, None, None, None, None
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return Response({"error": _("The period does not contain valid dates")}, status=400)
    if start_date > end_date:
        return Response({"error": _("The start date must be before the end date")}, status=400)
    return "custom", start, end, start_date, end_date


def _performance_result_range(range_name: str, start: str | None, end: str | None) -> str:
    return f"{start}_{end}" if start and end else range_name


def _named_performance_bounds(range_name: str) -> tuple[date, date]:
    """Resolve preset ranges to stable inclusive calendar boundaries."""
    end = timezone.localdate()
    months = {"6m": 6, "1y": 12, "2y": 24}[range_name]
    month_index = end.year * 12 + end.month - 1 - months
    year, month = divmod(month_index, 12)
    start = end.replace(
        year=year,
        month=month + 1,
        day=min(end.day, monthrange(year, month + 1)[1]),
    )
    return start, end


def _stock_split_rows(request: Request) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    splits = (
        StockSplit.objects.filter(workspace=workspace(request))
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )
    for split in splits:
        identity = select_identifier(
            split.instrument.identifiers.all(), InstrumentIdentifier.Scheme.ISIN
        )
        if identity:
            rows.append(
                {
                    "isin": identity.value,
                    "fecha": split.effective_date.isoformat(),
                    "ratio": number(split.ratio),
                }
            )
    return rows


def investment_performance(request: Request, kind: str) -> Response:
    """Build historical performance for a workspace-scoped investment kind."""
    config = PERFORMANCE_KINDS.get(kind)
    if config is None:
        return Response({"error": _("The investment type is not valid")}, status=400)
    instrument_kind, _account_kind, identifier_scheme = config
    selected_account = _selected_traded_account(request, kind)
    if isinstance(selected_account, Response):
        return selected_account
    account_value = str(selected_account.id) if selected_account is not None else "all"

    period = _performance_period(request)
    if isinstance(period, Response):
        return period
    range_name, start, end, start_date, end_date = period
    current_workspace = workspace(request)
    base_currency = normalize_currency(current_workspace.base_currency)
    ignore_savebacks = (
        kind == "stock" and request.query_params.get("ignore_savebacks", "").casefold() == "true"
    )
    response_range = _performance_result_range(range_name, start, end)
    if start_date and end_date:
        timeline_start, timeline_end = start, end
    else:
        named_start, named_end = _named_performance_bounds(range_name)
        timeline_start, timeline_end = named_start.isoformat(), named_end.isoformat()
    cache_key = (
        f"investment-performance:{current_workspace.pk}:{kind}:{account_value}:"
        f"{response_range}:{base_currency}:saveback={int(ignore_savebacks)}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    rows = _transaction_calculation_list(request, instrument_kind, selected_account)
    result_base: dict[str, Any] = {
        "range": response_range,
        "account_id": account_value,
        "kind": kind,
        "moneda_base": base_currency,
        "data": [],
    }
    if not rows:
        cache.set(cache_key, result_base, timeout=3600)
        return Response(result_base)

    asset_key = "symbol" if kind == "crypto" else "isin"
    assets = sorted({str(row.get(asset_key, "")) for row in rows if row.get(asset_key)})
    tickers: dict[str, str] = {}
    history_failed = False
    for asset in assets:
        try:
            instrument = workspace_instrument(request, identifier_scheme, asset)
            if getattr(instrument, "kind", instrument_kind) != instrument_kind:
                continue
            tickers[asset] = yahoo_ticker(instrument)
        except (Http404, MarketDataError):
            # Missing identifiers/tickers are isolated to that instrument.
            history_failed = True
            continue

    interval = "1wk" if range_name == "2y" else "1d"
    if start_date and end_date and (end_date - start_date).days > 540:
        interval = "1wk"

    def load_history(asset: str, ticker: str) -> tuple[str, dict[str, float], bool]:
        history_key = (
            f"investment-history:{current_workspace.pk}:{kind}:{ticker}:"
            f"{base_currency}:{response_range}:{interval}"
        )
        history = cache.get(history_key)
        if history is not None:
            return asset, history, False
        try:
            meta, points = yahoo_chart(
                ticker,
                range_name=range_name if range_name != "custom" else "1y",
                interval=interval,
                start=start,
                end=end,
            )
            currency = normalize_currency(meta.get("currency") or "EUR")
            dated_points = [
                (date.fromisoformat(str(point["fecha"])), point)
                for point in points
                if point.get("fecha") and point.get("precio", point.get("close")) not in (None, "")
            ]
            if start_date and end_date:
                dated_points = [
                    (point_date, point)
                    for point_date, point in dated_points
                    if start_date <= point_date <= end_date
                ]
            if not dated_points:
                return asset, {}, False
            conversions = rates_to_base(
                currency,
                base_currency,
                [point_date for point_date, _point in dated_points],
                workspace=current_workspace,
            )
            converted: dict[str, float] = {}
            for point_date, point in dated_points:
                raw_price = point.get("precio", point.get("close"))
                conversion = conversions.get(point_date)
                if conversion is None or raw_price in (None, ""):
                    continue
                converted[point_date.isoformat()] = round(
                    float(str(raw_price)) * float(conversion.rate), 8
                )
            cache.set(history_key, converted, timeout=3600)
            return asset, converted, False
        except (MarketDataError, CurrencyConversionError, ValueError, KeyError):
            return asset, {}, True

    histories: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(tickers)))) as executor:
        futures = {
            executor.submit(load_history, asset, ticker): asset for asset, ticker in tickers.items()
        }
        for future in as_completed(futures):
            asset, history, failed = future.result()
            histories[asset] = history
            history_failed = history_failed or failed

    split_rows = _stock_split_rows(request) if kind == "stock" else ()
    result_base["data"] = calculate_investment_performance(
        rows,
        histories,
        kind=kind,
        account_id=account_value,
        splits=split_rows,
        ignore_savebacks=ignore_savebacks,
        timeline_start=timeline_start,
        timeline_end=timeline_end,
    )
    if not history_failed:
        cache.set(cache_key, result_base, timeout=3600)
    return Response(result_base)


@api_view(["GET"])
def investment_performance_view(request: Request, kind: str) -> Response:
    return investment_performance(request, kind)
