from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account, AccountSnapshot, FinancialProvider
from apps.api.legacy import (
    account_id,
    account_row,
    instrument_row,
    next_account_id,
    next_legacy_id,
    number,
    price_row,
    provider_name,
    real_estate_row,
    snapshot_row,
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
from apps.market_data.locking import lock_logical_keys
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
from apps.planning.models import AllocationRule, BudgetLine
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


def find_account(request: Request, kind: str, legacy_id: int) -> Account:
    return get_object_or_404(kind_accounts(request, kind), external_id=f"legacy:{kind}:{legacy_id}")


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
    except KeyError as exc:
        raise ValueError(_("The selected importer does not exist")) from exc
    if importer.target != ACCOUNT_IMPORT_TARGETS[Account.Kind(kind)]:
        raise ValueError(_("The importer is not compatible with this account type"))
    return slug


def account_collection(request: Request, kind: str, provider_field: str) -> Response:
    accounts = kind_accounts(request, kind)
    if request.method == "GET":
        return Response([account_row(item, provider_field) for item in accounts])
    if denied := forbidden_if_readonly(request):
        return denied
    data = payload(request)
    name = str(data.get("nombre", "")).strip()
    if not name:
        return Response({"error": _("The account name is required")}, status=400)
    try:
        importer_slug = account_importer(data, kind)
        account_currency = normalize_currency(
            data.get("moneda") or workspace(request).base_currency
        )
    except (ValueError, CurrencyConversionError) as exc:
        return Response({"error": str(exc)}, status=400)
    provider, provider_label = resolve_provider(str(data.get(provider_field, "")))
    legacy_id = next_account_id(accounts)
    item = Account.objects.create(
        workspace=workspace(request),
        name=name,
        kind=kind,
        subtype=str(data.get("tipo", "")).strip(),
        provider=provider,
        provider_label=provider_label,
        importer_slug=importer_slug,
        currency=account_currency,
        external_id=f"legacy:{kind}:{legacy_id}",
    )
    cache.clear()
    return Response(account_row(item, provider_field), status=201)


def account_detail(request: Request, kind: str, legacy_id: int, provider_field: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = find_account(request, kind, legacy_id)
    if request.method == "DELETE":
        item.transactions.all().delete()
        item.snapshots.all().delete()
        item.delete()
        cache.clear()
        return Response({"ok": True})
    data = payload(request)
    try:
        item.importer_slug = account_importer(data, kind, item.importer_slug)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    item.name = str(data.get("nombre", item.name)).strip()
    item.subtype = str(data.get("tipo", item.subtype)).strip()
    if "moneda" in data:
        try:
            item.currency = normalize_currency(data.get("moneda") or item.currency)
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=400)
    provider, provider_label = resolve_provider(str(data.get(provider_field, provider_name(item))))
    item.provider = provider
    item.provider_label = provider_label
    item.save()
    cache.clear()
    return Response(account_row(item, provider_field))


@api_view(["GET", "POST"])
def savings_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.SAVINGS, "banco")


@api_view(["PUT", "DELETE"])
def savings_account(request: Request, legacy_id: int) -> Response:
    return account_detail(request, Account.Kind.SAVINGS, legacy_id, "banco")


@api_view(["GET", "POST"])
def investment_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.MANUAL_INVESTMENT, "plataforma")


@api_view(["PUT", "DELETE"])
def investment_account(request: Request, legacy_id: int) -> Response:
    return account_detail(request, Account.Kind.MANUAL_INVESTMENT, legacy_id, "plataforma")


@api_view(["GET", "POST"])
def fund_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.FUNDS, "plataforma")


@api_view(["PUT", "DELETE"])
def fund_account(request: Request, legacy_id: int) -> Response:
    return account_detail(request, Account.Kind.FUNDS, legacy_id, "plataforma")


@api_view(["GET", "POST"])
def stock_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.STOCKS, "plataforma")


@api_view(["PUT", "DELETE"])
def stock_account(request: Request, legacy_id: int) -> Response:
    return account_detail(request, Account.Kind.STOCKS, legacy_id, "plataforma")


@api_view(["GET", "POST"])
def crypto_accounts(request: Request) -> Response:
    return account_collection(request, Account.Kind.CRYPTO, "plataforma")


@api_view(["PUT", "DELETE"])
def crypto_account(request: Request, legacy_id: int) -> Response:
    return account_detail(request, Account.Kind.CRYPTO, legacy_id, "plataforma")


def snapshots(request: Request, kind: str) -> Response:
    queryset = AccountSnapshot.objects.select_related("account").filter(
        account__workspace=workspace(request), account__kind=kind
    )
    account_filter = request.query_params.get("cuenta_id")
    if account_filter:
        queryset = queryset.filter(account=find_account(request, kind, int(account_filter)))
    if request.method == "GET":
        return Response([snapshot_row(item) for item in queryset.order_by("date")])
    if denied := forbidden_if_readonly(request):
        return denied
    data = payload(request)
    account = find_account(request, kind, int(data["cuenta_id"]))
    value_key = "saldo" if kind == Account.Kind.SAVINGS else "valor"
    value = decimal(data[value_key])
    contribution = decimal(data.get("aporte"))
    earnings = data.get("intereses")
    snapshot_date = date.fromisoformat(str(data["fecha"])[:10])
    if kind in {Account.Kind.SAVINGS, Account.Kind.MANUAL_INVESTMENT}:
        snapshot_date = snapshot_date.replace(
            day=monthrange(snapshot_date.year, snapshot_date.month)[1]
        )
    if kind == Account.Kind.MANUAL_INVESTMENT and earnings in (None, ""):
        records = [
            {
                "fecha": item.date.isoformat(),
                "cuenta_id": account_id(item.account),
                "valor": number(item.value),
                "aporte": number(item.contribution),
                "intereses": number(item.earnings),
            }
            for item in queryset.filter(account=account)
        ]
        earnings = monthly_pnl(
            records,
            account_id=account_id(account),
            date=snapshot_date.isoformat(),
            value=float(value),
            contribution=float(contribution),
            explicit_pnl=None,
        )
    try:
        conversion = rate_to_base(
            account.currency,
            account.workspace.base_currency,
            snapshot_date,
            workspace=account.workspace,
        )
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    base_value = value * conversion.rate
    base_contribution = contribution * conversion.rate
    base_earnings = decimal(earnings) * conversion.rate
    item, _ = AccountSnapshot.objects.update_or_create(
        account=account,
        date=snapshot_date,
        defaults={
            "value": value,
            "contribution": contribution,
            "earnings": decimal(earnings),
            "currency": normalize_currency(account.currency),
            "base_currency": normalize_currency(account.workspace.base_currency),
            "base_value": base_value,
            "base_contribution": base_contribution,
            "base_earnings": base_earnings,
            "fx_rate_to_base": conversion.rate,
            "fx_rate_date": conversion.rate_date,
            "fx_source": conversion.source,
        },
    )
    return Response(snapshot_row(item), status=201)


@api_view(["GET", "POST"])
def savings_history(request: Request) -> Response:
    return snapshots(request, Account.Kind.SAVINGS)


@api_view(["GET", "POST"])
def investment_history(request: Request) -> Response:
    return snapshots(request, Account.Kind.MANUAL_INVESTMENT)


@api_view(["DELETE"])
def snapshot_detail(request: Request, kind: str, legacy_id: int, value_date: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    AccountSnapshot.objects.filter(
        account=find_account(request, kind, legacy_id), date=value_date
    ).delete()
    return Response({"ok": True})


def real_estate_records(request: Request) -> list[dict[str, Any]]:
    items = (
        RealEstateInvestment.objects.filter(workspace=workspace(request), archived_at__isnull=True)
        .prefetch_related("cash_flows", "provider")
        .order_by("legacy_id")
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
        if item_name != _normalized_match_text(project.get("nombre")):
            continue
        project_provider = _normalized_match_text(project.get("plataforma"))
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
    identity_by_instrument = {
        item.id: next(
            (
                identifier.value
                for identifier in item.identifiers.all()
                if identifier.scheme == identity_scheme
            ),
            "",
        )
        for item in instruments
    }
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
        row = transaction_row(item)
        row["importe_base"] = number(base_amounts[item.pk])
        transaction_rows.append(row)
    months = set(prices_by_month)
    months.update(effective_date(item).isoformat()[:7] for item in valid_transactions)
    if not months:
        return []

    fund_map = (
        {instrument_row(item)["isin"]: instrument_row(item) for item in instruments}
        if kind == "fund"
        else {}
    )
    split_rows: list[dict[str, Any]] = (
        [
            {
                "isin": split.instrument.identifiers.get(
                    scheme=InstrumentIdentifier.Scheme.ISIN
                ).value,
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


def _overview_calculation(request: Request) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_workspace = workspace(request)
    user = cast(User, request.user)
    included_sources, source_scope = effective_summary_sources(user, current_workspace)
    properties = real_estate_records(request)
    manual_assets = _summary_manual_assets(request, properties)
    all_savings = [
        snapshot_row(x)
        for x in AccountSnapshot.objects.select_related("account").filter(
            account__workspace=current_workspace, account__kind=Account.Kind.SAVINGS
        )
    ]
    all_investments = [
        snapshot_row(x)
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
    items = ManualAsset.objects.filter(workspace=current_workspace, archived_at__isnull=True)
    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        data = payload(request)
        item = ManualAsset.objects.create(
            workspace=current_workspace,
            legacy_id=next_legacy_id(items),
            name=str(data["nombre"]),
            asset_class=str(data.get("tipo_renta", "")),
            subtype=str(data.get("subtipo", "")),
            provider_label=str(data.get("plataforma", "")),
            value=decimal(data["efectivo"]),
            currency=normalize_currency(current_workspace.base_currency),
            valued_at=date.today(),
        )
        return Response(manual_asset_row(item), status=201)
    return Response([manual_asset_row(item) for item in items.order_by("legacy_id")])


def manual_asset_row(item: ManualAsset) -> dict[str, Any]:
    return {
        "id": item.legacy_id,
        "nombre": item.name,
        "tipo_renta": item.asset_class,
        "subtipo": item.subtype,
        "plataforma": provider_name(item),
        "efectivo": number(item.value),
        "moneda": item.currency,
    }


@api_view(["PUT", "DELETE"])
def portfolio_detail(request: Request, legacy_id: int) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(ManualAsset, workspace=workspace(request), legacy_id=legacy_id)
    if request.method == "DELETE":
        item.delete()
        return Response({"ok": True})
    data = payload(request)
    for source, target in (
        ("nombre", "name"),
        ("tipo_renta", "asset_class"),
        ("subtipo", "subtype"),
        ("plataforma", "provider_label"),
    ):
        if source in data:
            setattr(item, target, str(data[source]))
    if "efectivo" in data:
        item.value = decimal(data["efectivo"])
    item.save()
    return Response(manual_asset_row(item))


STATUS_IN = {
    "Activo": "active",
    "Completado": "completed",
    "Completada": "completed",
    "Impagado": "defaulted",
    "Cancelado": "cancelled",
}


def save_real_estate(item: RealEstateInvestment, data: dict[str, Any]) -> None:
    item.name = str(data.get("nombre", item.name))
    item.provider = None
    item.provider_label = str(data.get("plataforma", item.provider_label))
    item.status = STATUS_IN.get(str(data.get("estado", "Activo")), item.status)
    item.start_date = date.fromisoformat(str(data.get("fecha_inicio") or item.start_date)[:10])
    item.maturity_date = (
        date.fromisoformat(str(data["fecha_vencimiento"])[:10])
        if data.get("fecha_vencimiento")
        else None
    )
    item.expected_profit = (
        None
        if data.get("beneficio_estimado") in (None, "")
        else decimal(data["beneficio_estimado"])
    )
    item.expected_irr = decimal(data.get("tir")) / 100
    item.expected_term_months = int(data.get("meses") or 0) or None
    item.origin = str(data.get("origen", ""))
    item.tax_rate = (
        None
        if data.get("retencion_irpf") in (None, "")
        else percentage_rate(data["retencion_irpf"])
    )
    item.currency = normalize_currency(item.workspace.base_currency)
    item.save()
    initial = decimal(data.get("capital_inicial"))
    new = decimal(data.get("capital_nuevo"), str(initial))
    movements = data.get("movimientos")
    existing_flows = {str(flow.id): flow for flow in item.cash_flows.all()}
    if not isinstance(movements, list):
        return_date = (
            date.fromisoformat(str(data["fecha_devolucion"])[:10])
            if data.get("fecha_devolucion")
            else None
        )
        existing_return = next(
            (
                flow
                for flow in existing_flows.values()
                if flow.flow_type == RealEstateCashFlow.FlowType.CAPITAL_RETURN
            ),
            None,
        )
        existing_profit = next(
            (
                flow
                for flow in existing_flows.values()
                if flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
            ),
            None,
        )
        movements = [
            {
                "id": str(existing_return.id) if existing_return else "",
                "tipo": RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                "importe": decimal(data.get("capital_devuelto")),
                "fecha": return_date,
                "nota": "",
            },
            {
                "id": str(existing_profit.id) if existing_profit else "",
                "tipo": RealEstateCashFlow.FlowType.PROFIT,
                "importe": decimal(data.get("beneficio_obtenido")),
                "fecha": return_date,
                "nota": "",
            },
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
        flow_type = str(movement.get("tipo", ""))
        if flow_type not in allowed_types:
            raise ValueError(_("An invalid real-estate movement type was received"))
        amount = decimal(movement.get("importe"))
        if amount <= 0:
            continue
        flow_date: date | None = (
            date.fromisoformat(str(movement["fecha"])[:10]) if movement.get("fecha") else None
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
            source_note=str(movement.get("nota", ""))[:240],
        )


@api_view(["GET", "POST"])
def real_estate(request: Request) -> Response:
    if request.method == "GET":
        return Response(real_estate_records(request))
    if denied := forbidden_if_readonly(request):
        return denied
    data = payload(request)
    items = RealEstateInvestment.objects.filter(workspace=workspace(request))
    item = RealEstateInvestment(
        workspace=workspace(request),
        legacy_id=next_legacy_id(items),
        name=str(data["nombre"]),
        start_date=date.today(),
    )
    try:
        with transaction.atomic():
            save_real_estate(item, data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    item.refresh_from_db()
    return Response(real_estate_row(item), status=201)


@api_view(["PUT", "DELETE"])
def real_estate_detail(request: Request, legacy_id: int) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(
        RealEstateInvestment, workspace=workspace(request), legacy_id=legacy_id
    )
    if request.method == "DELETE":
        item.cash_flows.all().delete()
        item.delete()
        return Response({"ok": True})
    try:
        with transaction.atomic():
            save_real_estate(item, payload(request))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(real_estate_row(item))


def allocation_row(item: AllocationRule) -> dict[str, Any]:
    return {
        "id": item.legacy_id,
        "nombre": item.name,
        "plataforma": provider_name(item),
        "tipo_renta": item.asset_class,
        "subtipo": item.subtype,
        "porcentaje": number(item.target_weight) * 100,
        "aportar": item.enabled,
    }


@api_view(["GET", "POST"])
def calculator(request: Request) -> Response:
    items = AllocationRule.objects.filter(workspace=workspace(request))
    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        data = payload(request)
        item = AllocationRule.objects.create(
            workspace=workspace(request),
            legacy_id=next_legacy_id(items),
            name=str(data["nombre"]),
            provider_label=str(data.get("plataforma", "")),
            asset_class=str(data.get("tipo_renta", "")),
            subtype=str(data.get("subtipo", "")),
            target_weight=decimal(data.get("porcentaje")) / 100,
            enabled=bool(data.get("aportar", False)),
            sort_order=items.count(),
        )
        return Response(allocation_row(item), status=201)
    return Response([allocation_row(item) for item in items])


@api_view(["PUT", "DELETE"])
def calculator_detail(request: Request, legacy_id: int) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(AllocationRule, workspace=workspace(request), legacy_id=legacy_id)
    if request.method == "DELETE":
        item.delete()
        return Response({"ok": True})
    data = payload(request)
    mapping = {
        "nombre": "name",
        "plataforma": "provider_label",
        "tipo_renta": "asset_class",
        "subtipo": "subtype",
    }
    for source, target in mapping.items():
        if source in data:
            setattr(item, target, str(data[source]))
    if "porcentaje" in data:
        item.target_weight = decimal(data["porcentaje"]) / 100
    if "aportar" in data:
        item.enabled = bool(data["aportar"])
    item.save()
    return Response(allocation_row(item))


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


@transaction.atomic
def create_instrument(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    data = payload(request)
    is_crypto = kind == Instrument.Kind.CRYPTO
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL if is_crypto else InstrumentIdentifier.Scheme.ISIN
    )
    key = "symbol" if is_crypto else "isin"
    identifier_value = str(data.get(key, "")).strip().upper()
    name = str(data.get("nombre", "")).strip()
    ticker = str(data.get("ticker", "")).strip()
    try:
        quote_currency = normalize_currency(data.get("moneda") or "EUR")
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    if not identifier_value or not name or not ticker:
        return Response(
            {"error": _("Name, identifier, and ticker are required")},
            status=400,
        )
    lock_logical_keys((f"instrument:{scheme}:{identifier_value}", f"ticker:{ticker}"))
    identity = (
        InstrumentIdentifier.objects.select_related("instrument")
        .select_for_update()
        .filter(scheme=scheme, value=identifier_value, venue="")
        .first()
    )
    if identity and identity.instrument.kind != kind:
        return Response(
            {"error": _("The identifier already belongs to another asset type")},
            status=400,
        )
    current_workspace = workspace(request)
    shared_identity = bool(
        identity
        and (
            identity.instrument.workspace_links.exclude(workspace=current_workspace).exists()
            or identity.instrument.transactions.exclude(
                account__workspace=current_workspace
            ).exists()
        )
    )
    if shared_identity and identity is not None:
        existing_ticker = (
            InstrumentIdentifier.objects.filter(
                instrument=identity.instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                venue="",
            )
            .values_list("value", flat=True)
            .first()
        )
        if existing_ticker != ticker:
            return Response({"error": _("The shared catalog ticker cannot be changed")}, status=409)
    if identity and (
        identity.instrument.transactions.filter(account__workspace=current_workspace).exists()
        or identity.instrument.workspace_links.filter(workspace=current_workspace).exists()
    ):
        return Response({"error": _("The asset is already configured")}, status=400)
    ticker_owner = (
        InstrumentIdentifier.objects.select_for_update()
        .filter(
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            value=ticker,
            venue="",
        )
        .exclude(instrument=identity.instrument if identity else None)
        .exists()
    )
    if ticker_owner:
        return Response({"error": _("The ticker already belongs to another asset")}, status=400)
    with transaction.atomic():
        item = (
            identity.instrument
            if identity
            else Instrument.objects.create(
                kind=kind,
                name=name,
                quote_currency=quote_currency,
            )
        )
        if not identity:
            InstrumentIdentifier.objects.create(
                instrument=item,
                scheme=scheme,
                value=identifier_value,
                venue="",
                is_primary=True,
            )
        if not identity:
            item.name = name
            item.quote_currency = quote_currency
            item.save(update_fields=("name", "quote_currency", "updated_at"))
            InstrumentIdentifier.objects.update_or_create(
                instrument=item,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                defaults={"value": ticker, "venue": "", "is_primary": True},
            )
        WorkspaceInstrument.objects.create(
            workspace=current_workspace,
            instrument=item,
        )
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


@transaction.atomic
def update_instrument(request: Request, scheme: str, value: str, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    data = payload(request)
    name_value = data.get("nombre")
    name = str(name_value).strip() if name_value is not None else None
    ticker = None
    if "ticker" in data:
        raw_ticker = data["ticker"]
        if not isinstance(raw_ticker, str):
            return Response({"error": _("The ticker is invalid")}, status=400)
        ticker = raw_ticker.strip()
        if len(ticker) > 120:
            return Response({"error": _("The ticker is invalid")}, status=400)
        if ticker == "" and kind != Instrument.Kind.FUND:
            return Response({"error": _("The ticker is required")}, status=400)
    normalized_value = str(value).strip()
    if scheme != InstrumentIdentifier.Scheme.YAHOO:
        normalized_value = normalized_value.upper()
    logical_keys = [f"instrument:{scheme}:{normalized_value}"]
    if ticker is not None:
        logical_keys.append(f"ticker:{ticker}")
    lock_logical_keys(logical_keys)
    identity = get_object_or_404(
        InstrumentIdentifier.objects.select_related("instrument").select_for_update(),
        scheme=scheme,
        value=normalized_value,
    )
    item = Instrument.objects.select_for_update().get(pk=identity.instrument_id)
    current_workspace = workspace(request)
    if (
        item.workspace_links.exclude(workspace=current_workspace).exists()
        or item.transactions.exclude(account__workspace=current_workspace).exists()
    ):
        return Response(
            {"error": _("This catalog asset is configured in another workspace")},
            status=409,
        )
    if not (
        item.transactions.filter(account__workspace=current_workspace).exists()
        or item.workspace_links.filter(workspace=current_workspace).exists()
    ):
        return Response(status=404)
    if name is None:
        name = item.name
    if not name:
        return Response({"error": _("The name is required")}, status=400)
    if ticker and (
        InstrumentIdentifier.objects.select_for_update()
        .filter(
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            value=ticker,
            venue="",
        )
        .exclude(instrument=item)
        .exists()
    ):
        return Response({"error": _("The ticker already belongs to another asset")}, status=400)
    item.name = name
    if "moneda" in data:
        try:
            item.quote_currency = normalize_currency(data.get("moneda") or item.quote_currency)
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=400)
    if kind == Instrument.Kind.FUND:
        item.metadata = {**item.metadata, **{k: data[k] for k in ("tipo", "subtipo") if k in data}}
    item.save()
    if ticker is not None:
        InstrumentIdentifier.objects.update_or_create(
            instrument=item,
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            defaults={"value": ticker, "venue": ""},
        )
    cache.clear()
    return Response(instrument_row(item))


@api_view(["PUT"])
def fund_detail(request: Request, asset_id: str) -> Response:
    return update_instrument(request, "isin", asset_id, "fund")


@api_view(["PUT"])
def stock_detail(request: Request, asset_id: str) -> Response:
    return update_instrument(request, "isin", asset_id, "stock")


@api_view(["PUT"])
def crypto_detail(request: Request, asset_id: str) -> Response:
    return update_instrument(request, "crypto_symbol", asset_id, "crypto")


def transaction_queryset(request: Request, kind: str) -> QuerySet[Transaction]:
    queryset = (
        Transaction.objects.select_related("account", "instrument")
        .prefetch_related("instrument__identifiers")
        .filter(account__workspace=workspace(request), instrument__kind=kind)
    )
    account_filter = request.query_params.get("cuenta_id")
    if account_filter and account_filter != "all":
        account_kind = {
            Instrument.Kind.FUND: Account.Kind.FUNDS,
            Instrument.Kind.STOCK: Account.Kind.STOCKS,
            Instrument.Kind.CRYPTO: Account.Kind.CRYPTO,
        }[Instrument.Kind(kind)]
        queryset = queryset.filter(account=find_account(request, account_kind, int(account_filter)))
    return queryset


def transaction_list(request: Request, kind: str) -> Response:
    queryset = transaction_queryset(request, kind)
    return Response([transaction_row(item) for item in queryset.order_by("trade_date")])


FUND_MANUAL_OPERATIONS = {
    "SUSCRIPCION": (Transaction.OperationType.BUY, Transaction.CashFlowType.CONTRIBUTION),
    "SUSCR.POR TRASPASO I": (
        Transaction.OperationType.TRANSFER_IN,
        Transaction.CashFlowType.INTERNAL,
    ),
    "REEMB.POR TRASPASO I": (
        Transaction.OperationType.TRANSFER_OUT,
        Transaction.CashFlowType.INTERNAL,
    ),
    "REEMBOLSO": (Transaction.OperationType.SELL, Transaction.CashFlowType.WITHDRAWAL),
}
CRYPTO_MANUAL_OPERATIONS = {
    "Compra": (Transaction.OperationType.BUY, Transaction.CashFlowType.NONE),
    "Venta": (Transaction.OperationType.SELL, Transaction.CashFlowType.NONE),
}


def save_manual_transaction(
    request: Request,
    kind: str,
    item: Transaction | None = None,
) -> Response:
    data = payload(request)
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
    operation_label = str(data.get("tipo_operacion", ""))
    if operation_label not in operations:
        return Response({"error": _("The transaction type is not valid")}, status=400)
    try:
        account = find_account(request, account_kind, int(data["cuenta_id"]))
        instrument = workspace_instrument(request, scheme, str(data[asset_key]))
        if instrument.kind != kind:
            return Response({"error": _("The asset does not belong in this section")}, status=400)
        trade_date = date.fromisoformat(str(data["fecha_operacion"])[:10])
        settlement_value = str(data.get("fecha_liquidacion") or "")[:10]
        settlement_date = date.fromisoformat(settlement_value) if settlement_value else None
        quantity = decimal(data["titulos"])
        price_key = "precio_neto" if kind == Instrument.Kind.FUND else "precio_compra"
        unit_price = decimal(data[price_key])
        amount = decimal(data["importe_neto"])
        fee = decimal(data.get("comision"))
    except (KeyError, TypeError, ValueError):
        return Response({"error": _("Check the required transaction fields")}, status=400)
    if quantity <= 0 or unit_price < 0 or amount < 0 or fee < 0:
        return Response(
            {"error": _("Quantity, price, amount, and fee must be positive")},
            status=400,
        )

    operation_type, cash_flow_type = operations[operation_label]
    creating = item is None
    if item is None:
        item = Transaction(external_id=f"manual:{uuid4()}")
    item.account = account
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
    requested_saveback = data.get("es_saveback", False) in {
        True,
        "1",
        "true",
        "True",
    }
    item.is_saveback = bool(
        kind == Instrument.Kind.STOCK and "trade republic" in provider and requested_saveback
    )
    try:
        currency = normalize_currency(
            data.get("divisa")
            or data.get("moneda")
            or (item.currency if not creating else account.currency)
        )
        base_currency = normalize_currency(account.workspace.base_currency)
        provided_rate = (
            decimal(data["tipo_cambio"]) if data.get("tipo_cambio") not in (None, "") else None
        )
        provided_rate_date = (
            date.fromisoformat(str(data["fecha_tipo_cambio"])[:10])
            if data.get("fecha_tipo_cambio")
            else None
        )
        conversion = rate_to_base(
            currency,
            base_currency,
            settlement_date or trade_date,
            provided_rate=provided_rate,
            provided_date=provided_rate_date,
            provided_source=str(data.get("fuente_tipo_cambio") or "manual"),
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
    item.provider_operation_type = operation_label
    item.raw_metadata = {
        **item.raw_metadata,
        "legacy_name": instrument.name,
        "manual": True,
    }
    item.save()
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


@api_view(["PUT", "DELETE"])
def transaction_detail(request: Request, external_id: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    if request.method == "PUT":
        data = payload(request)
        queryset = Transaction.objects.filter(
            account__workspace=workspace(request),
            external_id=external_id,
        )
        original_account = data.get("cuenta_id_original")
        if original_account not in (None, ""):
            queryset = queryset.filter(
                account__external_id__in=[
                    f"legacy:funds:{original_account}",
                    f"legacy:crypto:{original_account}",
                    f"legacy:stocks:{original_account}",
                ]
            )
        item = get_object_or_404(queryset.select_related("instrument").order_by("created_at"))
        if item.instrument.kind not in {
            Instrument.Kind.FUND,
            Instrument.Kind.STOCK,
            Instrument.Kind.CRYPTO,
        }:
            return Response({"error": _("This transaction cannot be edited manually")}, status=400)
        return save_manual_transaction(request, item.instrument.kind, item)
    Transaction.objects.filter(
        account__workspace=workspace(request), external_id=external_id
    ).delete()
    cache.clear()
    return Response({"ok": True})


def price_list(request: Request, kind: str) -> Response:
    current_workspace = workspace(request)
    base_currency = normalize_currency(current_workspace.base_currency)
    queryset = (
        MarketPrice.objects.select_related("instrument")
        .prefetch_related("instrument__identifiers")
        .filter(
            instrument__in=workspace_instruments(request, kind),
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
            instrument__in=workspace_instruments(request, kind),
        )
    )
    selected: dict[Any, MarketPrice | WorkspaceMarketPriceOverride] = dict(latest_by_instrument)
    for override in overrides:
        existing = selected.get(override.instrument_id)
        if existing is None or override.quoted_at >= existing.quoted_at:
            selected[override.instrument_id] = override

    rows = []
    try:
        for selected_price in selected.values():
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


@api_view(["GET"])
def fund_prices(request: Request) -> Response:
    return price_list(request, "fund")


@api_view(["GET"])
def stock_prices(request: Request) -> Response:
    return price_list(request, "stock")


@api_view(["GET"])
def crypto_prices(request: Request) -> Response:
    return price_list(request, "crypto")


def update_price(request: Request, asset_id: str, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    instrument = workspace_instrument(request, InstrumentIdentifier.Scheme.ISIN, asset_id)
    if instrument.kind != kind:
        return Response({"error": _("The asset does not belong in this section")}, status=400)
    data = payload(request)
    if data.get("precio") in (None, ""):
        return Response({"error": _("The price is required")}, status=400)
    try:
        value = decimal(data["precio"])
        currency = normalize_currency(
            data.get("moneda") or instrument.quote_currency or workspace(request).base_currency
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
def fund_price_detail(request: Request, asset_id: str) -> Response:
    return update_price(request, asset_id, "fund")


@api_view(["PUT"])
def stock_price_detail(request: Request, asset_id: str) -> Response:
    return update_price(request, asset_id, "stock")


def analyzed_positions(
    request: Request,
    kind: str,
    rows: list[dict[str, Any]],
    *,
    account_filter: int | None = None,
) -> list[dict[str, Any]]:
    prices = price_list(request, kind).data
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
                "isin": s.instrument.identifiers.get(scheme="isin").value,
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
    fund_map = {row["isin"]: row for row in instruments(request, "fund").data}
    return calculate_fund_positions(rows, fund_map, price_map, account_id=account_filter)


def analysis(request: Request, kind: str) -> Response:
    rows = list(transaction_list(request, kind).data)
    account_filter = (
        int(request.query_params["cuenta_id"]) if request.query_params.get("cuenta_id") else None
    )
    return Response(analyzed_positions(request, kind, rows, account_filter=account_filter))


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
                "id": f"manual:{item.legacy_id}",
                "nombre": item.name,
                "identificador": "",
                "clase": item.asset_class or "Otros",
                "subtipo": item.subtype or "Posición manual",
                "cuenta": platform or "Posiciones manuales",
                "cuenta_id": f"manual:{item.legacy_id}",
                "plataforma": platform or "Manual",
                "valor": value,
                "origen": "manual",
            }
        )

    for project in properties:
        value = live_capital(project)
        if value <= 0:
            continue
        platform = str(project.get("plataforma") or "Inmobiliario")
        result.append(
            {
                "id": f"real-estate:{project['id']}",
                "nombre": project["nombre"],
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
        all_rows = list(transaction_list(request, kind).data)
        identity_key = "symbol" if kind == "crypto" else "isin"
        for account in kind_accounts(request, account_kind):
            legacy_account_id = account_id(account)
            account_rows = [row for row in all_rows if int(row["cuenta_id"]) == legacy_account_id]
            if not account_rows:
                continue
            positions = analyzed_positions(
                request,
                kind,
                account_rows,
                account_filter=legacy_account_id if kind == "fund" else None,
            )
            for position in positions:
                value = number(position.get("valor_actual"))
                if value <= 0:
                    continue
                result.append(
                    {
                        "id": f"{kind}:{legacy_account_id}:{position[identity_key]}",
                        "nombre": position.get("nombre") or position[identity_key],
                        "identificador": position[identity_key],
                        "clase": position.get("tipo") or default_classes[kind],
                        "subtipo": position.get("subtipo") or default_subtypes[kind],
                        "cuenta": account.name,
                        "cuenta_id": f"{kind}:{legacy_account_id}",
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
    queryset = (
        StockSplit.objects.filter(workspace=workspace(request))
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )
    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        data = payload(request)
        identity = get_object_or_404(InstrumentIdentifier, scheme="isin", value=data["isin"])
        StockSplit.objects.update_or_create(
            workspace=workspace(request),
            instrument=identity.instrument,
            effective_date=str(data["fecha"])[:10],
            defaults={
                "ratio": decimal(data["ratio"]),
                "source": data.get("fuente", "manual"),
                "confirmed_by": cast(User, request.user),
            },
        )
        cache.clear()
        return Response({"ok": True})
    return Response(
        [
            {
                "isin": s.instrument.identifiers.get(scheme="isin").value,
                "fecha": s.effective_date.isoformat(),
                "ratio": number(s.ratio),
                "fuente": s.source,
            }
            for s in queryset
        ]
    )


@api_view(["DELETE"])
def stock_split_detail(request: Request, asset_id: str, value_date: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    StockSplit.objects.filter(
        workspace=workspace(request),
        instrument__identifiers__scheme="isin",
        instrument__identifiers__value=asset_id,
        effective_date=value_date,
    ).delete()
    cache.clear()
    return Response({"ok": True})


def workspace_instrument(request: Request, scheme: str, value: str) -> Instrument:
    identity = get_object_or_404(
        InstrumentIdentifier.objects.select_related("instrument"), scheme=scheme, value=value
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
    identity = instrument.identifiers.filter(scheme=InstrumentIdentifier.Scheme.YAHOO).first()
    if identity and identity.value:
        return identity.value
    isin = instrument.identifiers.filter(scheme=InstrumentIdentifier.Scheme.ISIN).first()
    if not isin:
        raise MarketDataError(_("The instrument does not have a ticker configured"))
    found = search(isin.value)
    ticker = str(found.get("ticker", "")).strip()
    if not ticker or len(ticker) > 120:
        raise MarketDataError(_("The market-data provider returned an invalid ticker"))
    with transaction.atomic():
        lock_logical_keys(
            (f"instrument:{InstrumentIdentifier.Scheme.ISIN}:{isin.value}", f"ticker:{ticker}")
        )
        locked_instrument = Instrument.objects.select_for_update().get(pk=instrument.pk)
        current = (
            InstrumentIdentifier.objects.select_for_update()
            .filter(
                instrument=locked_instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                venue="",
            )
            .first()
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


def market_chart(request: Request, kind: str, asset_id: str) -> Response:
    scheme = "crypto_symbol" if kind == "crypto" else "isin"
    instrument = workspace_instrument(request, scheme, asset_id)
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
                    "fecha": row["fecha"],
                    "precio": round(
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
                    **row,
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
        key = "symbol" if kind == "crypto" else "isin"
        return Response(
            {
                key: asset_id,
                "ticker": ticker,
                "moneda": currency,
                "moneda_base": base_currency,
                "range": request.query_params.get("range", "1y"),
                "data": data,
            }
        )
    except MarketDataError as exc:
        return Response({"error": str(exc)}, status=502)


@api_view(["GET"])
def fund_chart(request: Request, asset_id: str) -> Response:
    return market_chart(request, "fund", asset_id)


@api_view(["GET"])
def stock_chart(request: Request, asset_id: str) -> Response:
    return market_chart(request, "stock", asset_id)


@api_view(["GET"])
def crypto_chart(request: Request, asset_id: str) -> Response:
    return market_chart(request, "crypto", asset_id)


def fetch_prices(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    instruments_qs = workspace_instruments(request, kind)
    base_currency = normalize_currency(workspace(request).base_currency)
    results = []
    for instrument in instruments_qs:
        asset_scheme = "crypto_symbol" if kind == "crypto" else "isin"
        asset_id = (
            instrument.identifiers.filter(scheme=asset_scheme)
            .values_list("value", flat=True)
            .first()
        )
        result: dict[str, Any] = {
            "symbol" if kind == "crypto" else "isin": asset_id,
            "precio": None,
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
                precio=round(price_base, 6),
                precio_orig=original,
                moneda=currency,
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
        identity = split.instrument.identifiers.filter(
            scheme=InstrumentIdentifier.Scheme.ISIN
        ).first()
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
    instrument_kind, account_kind, identifier_scheme = config
    account_value = request.query_params.get("cuenta_id", "all")
    if account_value != "all":
        try:
            account_number = int(account_value)
        except (TypeError, ValueError):
            return Response({"error": _("The account does not exist")}, status=404)
        try:
            find_account(request, account_kind, account_number)
        except Http404:
            return Response({"error": _("The account does not exist")}, status=404)
        account_value = str(account_number)

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

    rows = list(transaction_list(request, instrument_kind).data)
    result_base: dict[str, Any] = {
        "range": response_range,
        "cuenta_id": account_value,
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


@api_view(["GET"])
def account_performance(request: Request) -> Response:
    """Temporarily compatible alias for the shared Funds performance route."""
    response = investment_performance(request, "fund")
    if response.status_code != 200:
        return response
    # Keep the historical three-key payload for strict legacy clients.  The
    # canonical route exposes the additional kind/base-currency metadata.
    return Response(
        {key: response.data[key] for key in ("range", "cuenta_id", "data") if key in response.data}
    )
