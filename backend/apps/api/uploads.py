from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.schemas import AccountUploadRequestSerializer, UploadRequestSerializer
from apps.api.views import find_traded_account, forbidden_if_readonly, workspace
from apps.imports.models import ImportBatch
from apps.imports.models import ImportIssue as StoredIssue
from apps.market_data.fx import CurrencyConversionError
from apps.market_data.locking import lock_logical_keys
from apps.market_data.models import Instrument, InstrumentIdentifier
from apps.transactions.currency import conversion_snapshot, transaction_currency
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from finanzr.importers import (
    BaseImporter,
    ImportContext,
    ImporterError,
    ImportResult,
    InputKind,
    importers,
)

MAX_IMPORT_ROWS = 20_000


def _parse_decoded_source(
    importer: BaseImporter, content: str, account_id: UUID | str
) -> ImportResult:
    if importer.input_kind == InputKind.TEXT:
        return importer.parse(content, ImportContext(account_id=account_id))
    records = list(csv.DictReader(io.StringIO(content)))
    if len(records) > MAX_IMPORT_ROWS:
        raise ImporterError(
            _("The file exceeds the limit of %(max_rows)s rows") % {"max_rows": MAX_IMPORT_ROWS}
        )
    return importer.parse(records, ImportContext(account_id=account_id))


def parse_source(slug: str, raw: bytes, account_id: UUID | str, extension: str) -> ImportResult:
    importer = importers.get(slug)
    return _parse_decoded_source(importer, importer.decode(raw, extension), account_id)


@transaction.atomic
def instrument(
    record: dict[str, Any],
    kind: str,
    currency: str = "EUR",
    current_workspace: Workspace | None = None,
) -> Instrument:
    is_crypto = kind == Instrument.Kind.CRYPTO
    scheme = "crypto_symbol" if is_crypto else "isin"
    key = "symbol" if is_crypto else "isin"
    value = str(record[key]).strip().upper()
    ticker = f"{value}-EUR" if is_crypto else None
    lock_logical_keys(
        tuple(key for key in (f"instrument:{scheme}:{value}", f"ticker:{ticker}") if key)
    )
    identity = (
        InstrumentIdentifier.objects.select_related("instrument")
        .select_for_update()
        .filter(scheme=scheme, value=value, venue="")
        .first()
    )
    if identity:
        locked_instrument = Instrument.objects.select_for_update().get(pk=identity.instrument_id)
        used_elsewhere = bool(
            current_workspace
            and (
                locked_instrument.workspace_links.exclude(workspace=current_workspace).exists()
                or locked_instrument.transactions.exclude(
                    account__workspace=current_workspace
                ).exists()
            )
        )
        if not used_elsewhere and locked_instrument.quote_currency == "EUR" and currency != "EUR":
            locked_instrument.quote_currency = currency
            locked_instrument.save(update_fields=("quote_currency", "updated_at"))
        return locked_instrument
    if (
        ticker
        and InstrumentIdentifier.objects.select_for_update()
        .filter(scheme="yahoo", value=ticker, venue="")
        .exists()
    ):
        raise ImporterError("The crypto ticker is already owned by another instrument")
    name = str(record.get("nombre_activo") or record.get("nombre_fondo") or value)
    item = Instrument.objects.create(kind=kind, name=name, quote_currency=currency)
    InstrumentIdentifier.objects.create(
        instrument=item, scheme=scheme, value=value, is_primary=True
    )
    if is_crypto:
        InstrumentIdentifier.objects.create(
            instrument=item, scheme="yahoo", value=f"{value}-EUR", is_primary=True
        )
    return item


FUND_OPERATIONS = {
    "SUSCRIPCION": ("buy", "contribution"),
    "SUSCR.POR TRASPASO I": ("transfer_in", "internal"),
    "REEMB.POR TRASPASO I": ("transfer_out", "internal"),
    "REEMBOLSO": ("sell", "withdrawal"),
}


def persist_record(record: dict[str, Any], account: Account, kind: str, batch: ImportBatch) -> bool:
    operation_label = str(record["tipo_operacion"])
    operation, cash_flow = FUND_OPERATIONS.get(
        operation_label,
        ("buy" if operation_label.casefold() == "compra" else "sell", "none"),
    )
    currency = transaction_currency(record, account)
    trade_date = date.fromisoformat(str(record["fecha_operacion"])[:10])
    settlement_date = (
        date.fromisoformat(str(record.get("fecha_liquidacion"))[:10])
        if record.get("fecha_liquidacion")
        else None
    )
    unit_price = Decimal(str(record.get("precio_neto") or record.get("precio_compra") or 0))
    net_amount = Decimal(str(record["importe_neto"]))
    fee = Decimal(str(record.get("comision") or 0))
    try:
        conversion = conversion_snapshot(
            account=account,
            currency=currency,
            trade_date=trade_date,
            settlement_date=settlement_date,
            unit_price=abs(unit_price),
            net_amount=abs(net_amount),
            fee=abs(fee),
        )
    except CurrencyConversionError as exc:
        raise ImporterError(str(exc)) from exc
    _, created = Transaction.objects.update_or_create(
        account=account,
        external_id=str(record["operacion_id"]),
        defaults={
            "instrument": instrument(record, kind, currency, account.workspace),
            "import_batch": batch,
            "trade_date": trade_date,
            "settlement_date": settlement_date,
            "operation_type": operation,
            "cash_flow_type": cash_flow,
            "quantity": Decimal(str(record["titulos"])).copy_abs(),
            "unit_price": unit_price.copy_abs(),
            "net_amount": net_amount.copy_abs(),
            "fee": fee.copy_abs(),
            "currency": currency,
            **conversion,
            "market": str(record.get("mercado") or ""),
            "is_saveback": bool(record.get("es_saveback", False)),
            "provider_operation_type": operation_label,
            "raw_metadata": {
                "legacy_name": record.get("nombre_activo") or record.get("nombre_fondo") or ""
            },
        },
    )
    return created


def upload(
    request: Request,
    slug: str,
    account_kind: str,
    instrument_kind: str,
    *,
    account_id_override: UUID | None = None,
) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    uploaded = request.FILES.get("file")
    if "cuenta_id" in request.data:
        return Response({"error": _("Use account_id for account selection")}, status=400)
    if not uploaded or (account_id_override is None and not request.data.get("account_id")):
        return Response({"error": _("A file and an account are required")}, status=400)
    serializer_class = (
        UploadRequestSerializer
        if account_id_override is not None
        else AccountUploadRequestSerializer
    )
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    uploaded = data["file"]
    raw_account_id = account_id_override or data["account_id"]
    try:
        selected_account_id = (
            raw_account_id if isinstance(raw_account_id, UUID) else UUID(str(raw_account_id))
        )
    except (TypeError, ValueError, AttributeError):
        return Response({"error": _("A valid account ID was expected")}, status=400)
    extension = Path(uploaded.name).suffix.casefold()
    allowed = importers.get(slug).accepted_extensions
    if extension not in allowed:
        return Response(
            {"error": _("Unsupported extension: %(extension)s") % {"extension": extension}},
            status=400,
        )
    raw = uploaded.read()
    importer = importers.get(slug)
    try:
        content = importer.decode(raw, extension)
    except ImporterError as exc:
        return Response({"error": str(exc)}, status=400)
    account = find_traded_account(request, account_kind, selected_account_id)
    digest = hashlib.sha256(raw).hexdigest()
    existing = ImportBatch.objects.filter(
        workspace=workspace(request),
        account=account,
        importer_slug=slug,
        content_sha256=digest,
        status__in={"completed", "partial"},
    ).first()
    if existing:
        return Response(
            {
                "imported": 0,
                "skipped": existing.source_rows,
                "total": existing.source_rows,
                "duplicate": True,
            }
        )
    try:
        # Importers expose the public account identity as a string, regardless
        # of whether the request reached us through a UUID path or form field.
        parsed = _parse_decoded_source(importer, content, str(selected_account_id))
    except ImporterError as exc:
        return Response({"error": str(exc)}, status=400)
    try:
        with transaction.atomic():
            batch = ImportBatch.objects.create(
                workspace=workspace(request),
                account=account,
                created_by=cast(User, request.user),
                importer_slug=slug,
                source_filename=f"{uuid.uuid4().hex}{extension}",
                content_sha256=digest,
                status="processing",
                source_rows=parsed.imported + parsed.skipped,
                started_at=timezone.now(),
            )
            imported = sum(
                persist_record(record, account, instrument_kind, batch) for record in parsed.records
            )
            StoredIssue.objects.bulk_create(
                [
                    StoredIssue(
                        batch=batch,
                        severity=issue.severity,
                        code=issue.code,
                        message=issue.message,
                        row_number=issue.row_number,
                        value_preview=(issue.value or "")[:120],
                    )
                    for issue in parsed.issues
                ]
            )
            batch.imported_rows = imported
            batch.skipped_rows = parsed.skipped + parsed.imported - imported
            batch.status = "partial" if parsed.issues else "completed"
            batch.completed_at = timezone.now()
            batch.save()
    except ImporterError as exc:
        return Response({"error": str(exc)}, status=400)
    response = {"imported": imported, "skipped": batch.skipped_rows, "total": batch.source_rows}
    if slug == "kraken_spot":
        response["pares_ignorados"] = parsed.metadata.get("skipped_pairs", [])
    cache.clear()
    return Response(response)


@api_view(["GET"])
def catalog(request: Request) -> Response:
    return Response(importers.catalog())


@api_view(["POST"])
def upload_funds(request: Request) -> Response:
    return upload(request, "fund_broker", Account.Kind.FUNDS, Instrument.Kind.FUND)


@api_view(["POST"])
def upload_trade_republic(request: Request) -> Response:
    return upload(request, "trade_republic", Account.Kind.STOCKS, Instrument.Kind.STOCK)


@api_view(["POST"])
def upload_kraken_pro(request: Request) -> Response:
    # The stable importer slug is kept for existing import batches. Its input
    # contract has only been validated against KrakenPro's Spot Trades export.
    return upload(request, "kraken_spot", Account.Kind.CRYPTO, Instrument.Kind.CRYPTO)


ACCOUNT_IMPORT_CONFIG = {
    Account.Kind.FUNDS: ("fund_orders", Instrument.Kind.FUND),
    Account.Kind.STOCKS: ("stock_orders", Instrument.Kind.STOCK),
    Account.Kind.CRYPTO: ("crypto_orders", Instrument.Kind.CRYPTO),
}


@api_view(["POST"])
def upload_for_account(request: Request, kind: str, account_id: UUID) -> Response:
    try:
        account_kind = Account.Kind(kind)
    except ValueError:
        return Response({"error": _("This account type does not support importers")}, status=400)
    config = ACCOUNT_IMPORT_CONFIG.get(account_kind)
    if not config:
        return Response({"error": _("This account type does not support importers")}, status=400)
    account = find_traded_account(request, account_kind, account_id)
    if not account.importer_slug:
        return Response({"error": _("The account does not have an active importer")}, status=400)
    expected_target, instrument_kind = config
    try:
        importer = importers.get(account.importer_slug)
    except KeyError:
        return Response({"error": _("The active importer is no longer available")}, status=400)
    if importer.target != expected_target:
        return Response(
            {"error": _("The active importer is not compatible with the account")}, status=400
        )

    return upload(
        request,
        account.importer_slug,
        account_kind,
        instrument_kind,
        account_id_override=account_id,
    )
