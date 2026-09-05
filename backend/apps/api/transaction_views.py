from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.account_queries import (
    find_traded_account,
)
from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instrument
from apps.api.permissions import forbidden_if_readonly
from apps.api.projection import provider_name
from apps.api.request_data import decimal, payload
from apps.api.schemas import (
    CryptoTransactionRequestSerializer,
    FundTransactionRequestSerializer,
    StockTransactionRequestSerializer,
)
from apps.api.transaction_projection import (
    _calculation_operation_label,
    transaction_row,
)
from apps.api.transaction_queries import selected_traded_account, transaction_rows
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rate_to_base,
)
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
)
from apps.transactions.models import Transaction

CRYPTO_MANUAL_OPERATIONS = {
    Transaction.OperationType.BUY: (Transaction.OperationType.BUY, Transaction.CashFlowType.NONE),
    Transaction.OperationType.SELL: (Transaction.OperationType.SELL, Transaction.CashFlowType.NONE),
}


TRANSACTION_EXTERNAL_ID_CONSTRAINT = "transaction_external_id_unique"


def transaction_list(request: Request, kind: str) -> Response:
    try:
        selected_account = selected_traded_account(request, kind)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(transaction_rows(request, kind, selected_account))


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
