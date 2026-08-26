from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Account, AccountSnapshot, FinancialProvider
from apps.common.models import InstallationSettings
from apps.imports.legacy import (
    LegacyDataSource,
    LegacyImportError,
    LegacyImportReport,
    ReconciliationCheck,
    at_midnight,
    decimal_text,
    parse_bool,
    parse_date,
    parse_decimal,
)
from apps.imports.models import ImportBatch, ImportIssue
from apps.market_data.fx import normalize_currency
from apps.market_data.models import Instrument, InstrumentIdentifier, MarketPrice, StockSplit
from apps.planning.models import AllocationRule, BudgetLine
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate
from apps.transactions.currency import conversion_snapshot
from apps.transactions.models import Transaction
from apps.workspaces.models import Workspace, WorkspaceMembership

ZERO = Decimal("0")
ModelT = TypeVar("ModelT", bound=models.Model)


def quantize_decimal(value: Decimal, decimal_places: int) -> Decimal:
    quantum = Decimal("1").scaleb(-decimal_places)
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


ACCOUNT_FILES = (
    ("savings_accounts.csv", Account.Kind.SAVINGS, "banco"),
    ("investment_accounts.csv", Account.Kind.MANUAL_INVESTMENT, "plataforma"),
    ("fund_accounts.csv", Account.Kind.FUNDS, "plataforma"),
    ("stock_accounts.csv", Account.Kind.STOCKS, "plataforma"),
    ("crypto_accounts.csv", Account.Kind.CRYPTO, "plataforma"),
)

FUND_OPERATIONS = {
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


def normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def legacy_account_importer(kind: str, provider: str) -> str:
    normalized = normalized_text(provider)
    if kind == Account.Kind.FUNDS and ("myinvestor" in normalized or "inversis" in normalized):
        return "fund_broker"
    if kind == Account.Kind.STOCKS and "trade republic" in normalized:
        return "trade_republic"
    if kind == Account.Kind.CRYPTO and "kraken" in normalized:
        return "kraken_spot"
    return ""


class LegacyImportService:
    def __init__(
        self,
        *,
        data_dir: Path,
        workspace_slug: str,
        workspace_name: str | None = None,
        owner_email: str | None = None,
        dry_run: bool = False,
        validate: bool = False,
    ) -> None:
        self.source = LegacyDataSource(data_dir)
        self.workspace_slug = workspace_slug
        self.workspace_name = workspace_name or workspace_slug.replace("-", " ").title()
        self.owner_email = owner_email.strip().lower() if owner_email else None
        self.dry_run = dry_run
        self.validate = validate
        self.report = LegacyImportReport(workspace=workspace_slug, dry_run=dry_run)
        self.workspace: Workspace
        self.accounts: dict[tuple[str, str], Account] = {}
        self.fund_instruments: dict[str, Instrument] = {}
        self.stock_instruments: dict[str, Instrument] = {}
        self.crypto_instruments: dict[str, Instrument] = {}
        self.batches: dict[str, ImportBatch] = {}
        self._unknown_providers: set[tuple[str, str]] = set()
        self.valuation_date = date.today()

    def run(self) -> LegacyImportReport:
        self.source.validate_all()
        self.valuation_date = self.source.latest_date()
        try:
            with transaction.atomic():
                self.workspace = self._get_or_create_workspace()
                self._import_accounts()
                self._import_instruments()
                self._import_snapshots()
                self._import_transactions()
                self._import_prices_and_splits()
                self._import_real_estate()
                self._import_manual_assets()
                self._import_budget()
                self._import_allocations()
                self._reconcile()
                if self.validate and not self.report.valid:
                    failed = [check.name for check in self.report.checks if not check.matches]
                    raise LegacyImportError(
                        f"reconciliation failed: {', '.join(failed)}",
                        code="reconciliation_failed",
                    )
                if self.dry_run:
                    transaction.set_rollback(True)
        except LegacyImportError as exc:
            self.report.issues.append(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "severity": "error",
                    "filename": exc.filename,
                    "row_number": exc.row_number,
                    "value": exc.value,
                }
            )
            if exc.filename:
                self.report.file(exc.filename).errors += 1
            raise
        return self.report

    def _get_or_create_workspace(self) -> Workspace:
        workspace = Workspace.objects.filter(slug=self.workspace_slug).first()
        if workspace is None:
            if not self.owner_email:
                raise LegacyImportError(
                    "--owner-email is required when creating a workspace",
                    code="missing_owner_email",
                )
            workspace = Workspace.objects.create(name=self.workspace_name, slug=self.workspace_slug)
        if self.owner_email:
            user_model = get_user_model()
            user, created = user_model.objects.get_or_create(email=self.owner_email)
            update_fields = []
            if not user_model.objects.filter(role=user_model.Role.ADMIN).exists():
                user.role = user_model.Role.ADMIN
                update_fields.append("role")
            if created or not user.password or not user.has_usable_password():
                user.set_unusable_password()
                update_fields.append("password")
            if update_fields:
                user.save(update_fields=update_fields)
            WorkspaceMembership.objects.update_or_create(
                workspace=workspace,
                user=user,
                defaults={"role": WorkspaceMembership.Role.OWNER},
            )
        elif not workspace.memberships.filter(role=WorkspaceMembership.Role.OWNER).exists():
            raise LegacyImportError(
                "the existing workspace has no owner; provide --owner-email",
                code="workspace_without_owner",
            )
        return workspace

    def _begin_file(self, filename: str) -> tuple[list[dict[str, str]], ImportBatch]:
        rows = self.source.rows(filename)
        self.report.file(filename, len(rows))
        batch, _ = ImportBatch.objects.get_or_create(
            workspace=self.workspace,
            account=None,
            importer_slug=f"legacy:{Path(filename).stem}",
            content_sha256=self.source.sha256(filename),
            defaults={
                "source_filename": filename,
                "status": ImportBatch.Status.PROCESSING,
                "source_rows": len(rows),
                "started_at": timezone.now(),
            },
        )
        batch.source_filename = filename
        batch.status = ImportBatch.Status.PROCESSING
        batch.source_rows = len(rows)
        batch.started_at = timezone.now()
        batch.completed_at = None
        batch.save(
            update_fields=(
                "source_filename",
                "status",
                "source_rows",
                "started_at",
                "completed_at",
            )
        )
        batch.issues.all().delete()
        self.batches[filename] = batch
        return rows, batch

    def _finish_file(self, filename: str) -> None:
        report = self.report.file(filename)
        batch = self.batches[filename]
        batch.status = (
            ImportBatch.Status.PARTIAL
            if report.warnings or report.skipped
            else (ImportBatch.Status.COMPLETED)
        )
        batch.imported_rows = report.created + report.updated
        batch.skipped_rows = report.skipped + report.unchanged
        batch.completed_at = timezone.now()
        batch.save(
            update_fields=(
                "status",
                "imported_rows",
                "skipped_rows",
                "completed_at",
            )
        )

    def _issue(
        self,
        filename: str,
        *,
        code: str,
        message: str,
        row_number: int | None = None,
        value: str | None = None,
        severity: str = ImportIssue.Severity.WARNING,
    ) -> None:
        payload = {
            "code": code,
            "message": message,
            "severity": severity,
            "filename": filename,
            "row_number": row_number,
            "value": value,
        }
        self.report.issues.append(payload)
        report = self.report.file(filename)
        if severity == ImportIssue.Severity.ERROR:
            report.errors += 1
        else:
            report.warnings += 1
        ImportIssue.objects.create(
            batch=self.batches[filename],
            severity=severity,
            code=code,
            message=message[:500],
            row_number=row_number,
            value_preview=(value or "")[:120],
        )

    def _provider(self, filename: str, row_number: int, label: str) -> tuple[Any, str]:
        label = label.strip()
        if not label or label in {"-", "—", "–"}:
            return None, ""
        provider = FinancialProvider.objects.filter(name__iexact=label).first()
        if provider:
            return provider, ""
        marker = (filename, label.casefold())
        if marker not in self._unknown_providers:
            self._unknown_providers.add(marker)
            self._issue(
                filename,
                code="unknown_provider",
                message=f"Uncatalogued provider; preserved as a private label: {label}",
                row_number=row_number,
                value=label,
            )
        return None, label

    def _upsert(
        self,
        model: type[ModelT],
        *,
        lookup: dict[str, Any],
        defaults: dict[str, Any],
        filename: str,
    ) -> ModelT:
        report = self.report.file(filename)
        obj = model._default_manager.filter(**lookup).first()
        if obj is None:
            obj = model._default_manager.create(**lookup, **defaults)
            report.created += 1
            return obj
        changed: list[str] = []
        for field_name, value in defaults.items():
            if getattr(obj, field_name) != value:
                setattr(obj, field_name, value)
                changed.append(field_name)
        if changed:
            obj.save(update_fields=changed)
            report.updated += 1
        else:
            report.unchanged += 1
        return obj

    def _import_accounts(self) -> None:
        for filename, kind, provider_field in ACCOUNT_FILES:
            rows, _ = self._begin_file(filename)
            for row_number, row in enumerate(rows, start=2):
                legacy_id = row["id"]
                provider, provider_label = self._provider(
                    filename, row_number, row.get(provider_field, "")
                )
                account = self._upsert(
                    Account,
                    lookup={
                        "workspace": self.workspace,
                        "kind": kind,
                        "external_id": f"legacy:{kind}:{legacy_id}",
                    },
                    defaults={
                        "name": row["nombre"],
                        "subtype": row.get("tipo", ""),
                        "currency": "EUR",
                        "provider": provider,
                        "provider_label": provider_label,
                        "importer_slug": legacy_account_importer(
                            kind,
                            provider.name if provider else provider_label,
                        ),
                    },
                    filename=filename,
                )
                self.accounts[(kind, legacy_id)] = account
            self._finish_file(filename)

    def _instrument_for_identifier(
        self,
        *,
        filename: str,
        row_number: int,
        scheme: str,
        value: str,
        kind: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Instrument, bool, bool]:
        value = (
            value.strip().upper() if scheme != InstrumentIdentifier.Scheme.YAHOO else value.strip()
        )
        identifier = (
            InstrumentIdentifier.objects.select_related("instrument")
            .filter(scheme=scheme, value=value, venue="")
            .first()
        )
        created = False
        updated = False
        if identifier:
            instrument = identifier.instrument
            values = {"name": name, "metadata": metadata or instrument.metadata}
            for field_name, field_value in values.items():
                if getattr(instrument, field_name) != field_value:
                    setattr(instrument, field_name, field_value)
                    updated = True
            if updated:
                instrument.save(update_fields=("name", "metadata", "updated_at"))
            return instrument, created, updated
        instrument = Instrument.objects.create(
            kind=kind,
            name=name,
            metadata=metadata or {},
        )
        InstrumentIdentifier.objects.create(
            instrument=instrument,
            scheme=scheme,
            value=value,
            venue="",
            is_primary=True,
        )
        return instrument, True, False

    def _secondary_identifier(
        self, instrument: Instrument, scheme: str, value: str, *, filename: str, row_number: int
    ) -> None:
        value = value.strip()
        if not value:
            return
        existing = InstrumentIdentifier.objects.filter(scheme=scheme, value=value, venue="").first()
        if existing and existing.instrument_id != instrument.id:
            raise LegacyImportError(
                f"identifier {scheme}:{value} belongs to another instrument",
                code="duplicate_instrument_identifier",
                filename=filename,
                row_number=row_number,
                value=value,
            )
        InstrumentIdentifier.objects.get_or_create(
            instrument=instrument,
            scheme=scheme,
            value=value,
            venue="",
            defaults={"is_primary": False},
        )

    def _import_instruments(self) -> None:
        configurations = (
            (
                "funds.csv",
                "isin",
                InstrumentIdentifier.Scheme.ISIN,
                Instrument.Kind.FUND,
                self.fund_instruments,
            ),
            (
                "stocks.csv",
                "isin",
                InstrumentIdentifier.Scheme.ISIN,
                Instrument.Kind.STOCK,
                self.stock_instruments,
            ),
            (
                "cryptos.csv",
                "symbol",
                InstrumentIdentifier.Scheme.CRYPTO_SYMBOL,
                Instrument.Kind.CRYPTO,
                self.crypto_instruments,
            ),
        )
        for filename, key, scheme, kind, target in configurations:
            rows, _ = self._begin_file(filename)
            report = self.report.file(filename)
            for row_number, row in enumerate(rows, start=2):
                metadata = (
                    {"asset_class": row["tipo"], "subtype": row["subtipo"]}
                    if filename == "funds.csv"
                    else {}
                )
                instrument, created, updated = self._instrument_for_identifier(
                    filename=filename,
                    row_number=row_number,
                    scheme=scheme,
                    value=row[key],
                    kind=kind,
                    name=row["nombre"],
                    metadata=metadata,
                )
                if created:
                    report.created += 1
                elif updated:
                    report.updated += 1
                else:
                    report.unchanged += 1
                self._secondary_identifier(
                    instrument,
                    InstrumentIdentifier.Scheme.YAHOO,
                    row.get("ticker", ""),
                    filename=filename,
                    row_number=row_number,
                )
                identifier_value = row[key].strip().upper()
                target[identifier_value] = instrument
                if filename == "stocks.csv":
                    self._issue(
                        filename,
                        code="stock_kind_assumed",
                        message=(
                            "Classified as stock because ETF metadata is unavailable: "
                            f"{row['nombre']}"
                        ),
                        row_number=row_number,
                        value=identifier_value,
                    )
            self._finish_file(filename)

    def _account(self, kind: str, legacy_id: str, *, filename: str, row_number: int) -> Account:
        try:
            return self.accounts[(kind, legacy_id)]
        except KeyError as exc:
            raise LegacyImportError(
                f"unknown account: {legacy_id}",
                code="unknown_account",
                filename=filename,
                row_number=row_number,
                value=legacy_id,
            ) from exc

    def _instrument(
        self,
        mapping: dict[str, Instrument],
        identifier: str,
        *,
        filename: str,
        row_number: int,
    ) -> Instrument:
        key = identifier.strip().upper()
        try:
            return mapping[key]
        except KeyError as exc:
            raise LegacyImportError(
                f"unknown instrument: {identifier}",
                code="unknown_instrument",
                filename=filename,
                row_number=row_number,
                value=identifier,
            ) from exc

    def _import_snapshots(self) -> None:
        configurations = (
            (
                "savings_history.csv",
                Account.Kind.SAVINGS,
                "saldo",
                False,
            ),
            (
                "investment_history.csv",
                Account.Kind.MANUAL_INVESTMENT,
                "valor",
                True,
            ),
        )
        for filename, kind, value_field, check_pnl in configurations:
            rows, _ = self._begin_file(filename)
            previous: dict[str, Decimal] = {}
            ordered_rows = sorted(
                enumerate(rows, start=2), key=lambda item: (item[1]["cuenta_id"], item[1]["fecha"])
            )
            for row_number, row in ordered_rows:
                account = self._account(
                    kind, row["cuenta_id"], filename=filename, row_number=row_number
                )
                snapshot_date = parse_date(
                    row["fecha"],
                    filename=filename,
                    row_number=row_number,
                    field_name="fecha",
                )
                value = parse_decimal(
                    row[value_field],
                    filename=filename,
                    row_number=row_number,
                    field_name=value_field,
                )
                value = quantize_decimal(value, 8)
                contribution = parse_decimal(
                    row.get("aporte"),
                    filename=filename,
                    row_number=row_number,
                    field_name="aporte",
                    default=ZERO,
                )
                contribution = quantize_decimal(contribution, 8)
                earnings = parse_decimal(
                    row.get("intereses"),
                    filename=filename,
                    row_number=row_number,
                    field_name="intereses",
                    default=ZERO,
                )
                earnings = quantize_decimal(earnings, 8)
                previous_value = previous.get(row["cuenta_id"])
                if check_pnl and previous_value is not None:
                    expected = value - previous_value - contribution
                    if expected != earnings:
                        self._issue(
                            filename,
                            code="investment_pnl_mismatch",
                            message=(
                                f"Stored P&L {earnings} differs from expected value {expected}; "
                                "the stored value is preserved"
                            ),
                            row_number=row_number,
                            value=row["cuenta_id"],
                        )
                previous[row["cuenta_id"]] = value
                self._upsert(
                    AccountSnapshot,
                    lookup={"account": account, "date": snapshot_date},
                    defaults={
                        "value": value,
                        "contribution": contribution,
                        "earnings": earnings,
                    },
                    filename=filename,
                )
            self._finish_file(filename)

    def _import_transactions(self) -> None:
        self._import_fund_transactions()
        self._import_traded_transactions(
            filename="stock_orders.csv",
            kind=Account.Kind.STOCKS,
            identifier_field="isin",
            instruments=self.stock_instruments,
            saveback=True,
        )
        self._import_traded_transactions(
            filename="crypto_orders.csv",
            kind=Account.Kind.CRYPTO,
            identifier_field="symbol",
            instruments=self.crypto_instruments,
            saveback=False,
        )

    def _import_fund_transactions(self) -> None:
        filename = "orders.csv"
        rows, batch = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            try:
                operation_type, cash_flow_type = FUND_OPERATIONS[row["tipo_operacion"]]
            except KeyError as exc:
                raise LegacyImportError(
                    f"unknown transaction type: {row['tipo_operacion']}",
                    code="unknown_operation_type",
                    filename=filename,
                    row_number=row_number,
                    value=row["tipo_operacion"],
                ) from exc
            account = self._account(
                Account.Kind.FUNDS,
                row["cuenta_id"],
                filename=filename,
                row_number=row_number,
            )
            instrument = self._instrument(
                self.fund_instruments,
                row["isin"],
                filename=filename,
                row_number=row_number,
            )
            trade_date = parse_date(
                row["fecha_operacion"],
                filename=filename,
                row_number=row_number,
                field_name="fecha_operacion",
            )
            assert trade_date is not None
            settlement_date = parse_date(
                row.get("fecha_liquidacion"),
                filename=filename,
                row_number=row_number,
                field_name="fecha_liquidacion",
                optional=True,
            )
            currency = normalize_currency(row.get("divisa") or account.currency)
            unit_price = parse_decimal(
                row["precio_neto"],
                filename=filename,
                row_number=row_number,
                field_name="precio_neto",
            )
            net_amount = abs(
                parse_decimal(
                    row["importe_neto"],
                    filename=filename,
                    row_number=row_number,
                    field_name="importe_neto",
                )
            )
            conversion = conversion_snapshot(
                account=account,
                currency=currency,
                trade_date=trade_date,
                settlement_date=settlement_date,
                unit_price=unit_price,
                net_amount=net_amount,
                fee=ZERO,
                allow_pending=True,
                skip_external=True,
            )
            if instrument.quote_currency != currency:
                instrument.quote_currency = currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            self._upsert(
                Transaction,
                lookup={"account": account, "external_id": row["operacion_id"]},
                defaults={
                    "instrument": instrument,
                    "import_batch": batch,
                    "trade_date": trade_date,
                    "settlement_date": settlement_date,
                    "operation_type": operation_type,
                    "cash_flow_type": cash_flow_type,
                    "quantity": parse_decimal(
                        row["titulos"],
                        filename=filename,
                        row_number=row_number,
                        field_name="titulos",
                    ),
                    "unit_price": unit_price,
                    "net_amount": net_amount,
                    "fee": ZERO,
                    "currency": currency,
                    **conversion,
                    "market": row.get("mercado", ""),
                    "is_saveback": False,
                    "provider_operation_type": row["tipo_operacion"],
                    "raw_metadata": {"legacy_name": row.get("nombre_fondo", "")},
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_traded_transactions(
        self,
        *,
        filename: str,
        kind: str,
        identifier_field: str,
        instruments: dict[str, Instrument],
        saveback: bool,
    ) -> None:
        rows, batch = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            normalized_operation = normalized_text(row["tipo_operacion"])
            if normalized_operation == "compra":
                operation_type = Transaction.OperationType.BUY
            elif normalized_operation == "venta":
                operation_type = Transaction.OperationType.SELL
            else:
                raise LegacyImportError(
                    f"unknown transaction type: {row['tipo_operacion']}",
                    code="unknown_operation_type",
                    filename=filename,
                    row_number=row_number,
                    value=row["tipo_operacion"],
                )
            account = self._account(
                kind, row["cuenta_id"], filename=filename, row_number=row_number
            )
            instrument = self._instrument(
                instruments,
                row[identifier_field],
                filename=filename,
                row_number=row_number,
            )
            is_saveback = (
                parse_bool(
                    row.get("es_saveback"),
                    filename=filename,
                    row_number=row_number,
                    field_name="es_saveback",
                )
                if saveback
                else False
            )
            trade_date = parse_date(
                row["fecha_operacion"],
                filename=filename,
                row_number=row_number,
                field_name="fecha_operacion",
            )
            assert trade_date is not None
            unit_price = parse_decimal(
                row["precio_compra"],
                filename=filename,
                row_number=row_number,
                field_name="precio_compra",
            )
            net_amount = abs(
                parse_decimal(
                    row["importe_neto"],
                    filename=filename,
                    row_number=row_number,
                    field_name="importe_neto",
                )
            )
            fee = abs(
                parse_decimal(
                    row.get("comision"),
                    filename=filename,
                    row_number=row_number,
                    field_name="comision",
                    default=ZERO,
                )
            )
            currency = normalize_currency(account.currency)
            conversion = conversion_snapshot(
                account=account,
                currency=currency,
                trade_date=trade_date,
                settlement_date=None,
                unit_price=unit_price,
                net_amount=net_amount,
                fee=fee,
                allow_pending=True,
                skip_external=True,
            )
            if instrument.quote_currency != currency:
                instrument.quote_currency = currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            self._upsert(
                Transaction,
                lookup={"account": account, "external_id": row["operacion_id"]},
                defaults={
                    "instrument": instrument,
                    "import_batch": batch,
                    "trade_date": trade_date,
                    "settlement_date": None,
                    "operation_type": operation_type,
                    "cash_flow_type": Transaction.CashFlowType.NONE,
                    "quantity": parse_decimal(
                        row["titulos"],
                        filename=filename,
                        row_number=row_number,
                        field_name="titulos",
                    ),
                    "unit_price": unit_price,
                    "net_amount": net_amount,
                    "fee": fee,
                    "currency": currency,
                    **conversion,
                    "market": "",
                    "is_saveback": is_saveback,
                    "provider_operation_type": row["tipo_operacion"],
                    "raw_metadata": {"legacy_name": row.get("nombre_activo", "")},
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_prices_and_splits(self) -> None:
        self._import_fund_prices()
        self._import_stock_prices()
        self._import_crypto_prices()
        self._import_stock_splits()

    def _timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.workspace.timezone)
        except Exception as exc:
            raise LegacyImportError(
                f"invalid workspace timezone: {self.workspace.timezone}",
                code="invalid_workspace_timezone",
            ) from exc

    def _import_fund_prices(self) -> None:
        filename = "fund_prices.csv"
        rows, _ = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            if not row.get("precio"):
                self.report.file(filename).skipped += 1
                self._issue(
                    filename,
                    code="missing_price",
                    message="Empty price; row skipped",
                    row_number=row_number,
                    value=row.get("isin"),
                )
                continue
            instrument = self._instrument(
                self.fund_instruments,
                row["isin"],
                filename=filename,
                row_number=row_number,
            )
            quote_date = parse_date(
                row["updated"],
                filename=filename,
                row_number=row_number,
                field_name="updated",
            )
            assert quote_date is not None
            price = parse_decimal(
                row["precio"],
                filename=filename,
                row_number=row_number,
                field_name="precio",
            )
            self._upsert(
                MarketPrice,
                lookup={
                    "instrument": instrument,
                    "granularity": MarketPrice.Granularity.SPOT,
                    "source": "legacy_fund_prices",
                },
                defaults={
                    "quoted_at": at_midnight(quote_date, self._timezone()),
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": price,
                    "currency": "EUR",
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_stock_prices(self) -> None:
        filename = "stock_prices.csv"
        rows, _ = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            instrument = self._instrument(
                self.stock_instruments,
                row["isin"],
                filename=filename,
                row_number=row_number,
            )
            raw_date = row.get("fecha") or row.get("updated")
            if not raw_date:
                raise LegacyImportError(
                    "price has neither date nor updated timestamp",
                    code="missing_price_date",
                    filename=filename,
                    row_number=row_number,
                    value=row["isin"],
                )
            quote_date = parse_date(
                raw_date,
                filename=filename,
                row_number=row_number,
                field_name="fecha/updated",
            )
            assert quote_date is not None
            original_price = parse_decimal(
                row.get("precio_orig") or row["precio"],
                filename=filename,
                row_number=row_number,
                field_name="precio_orig",
            )
            quote_currency = normalize_currency(row.get("moneda") or "EUR")
            if instrument.quote_currency != quote_currency:
                instrument.quote_currency = quote_currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            self._upsert(
                MarketPrice,
                lookup={
                    "instrument": instrument,
                    "granularity": MarketPrice.Granularity.SPOT,
                    "source": "legacy_stock_prices",
                },
                defaults={
                    "quoted_at": at_midnight(quote_date, self._timezone()),
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": original_price,
                    "currency": quote_currency,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_crypto_prices(self) -> None:
        filename = "crypto_prices.csv"
        rows, _ = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            instrument = self._instrument(
                self.crypto_instruments,
                row["symbol"],
                filename=filename,
                row_number=row_number,
            )
            quote_date = parse_date(
                row["updated"],
                filename=filename,
                row_number=row_number,
                field_name="updated",
            )
            assert quote_date is not None
            original_price = parse_decimal(
                row.get("precio_orig") or row["precio"],
                filename=filename,
                row_number=row_number,
                field_name="precio_orig",
            )
            quote_currency = normalize_currency(row.get("moneda") or "EUR")
            if instrument.quote_currency != quote_currency:
                instrument.quote_currency = quote_currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            self._upsert(
                MarketPrice,
                lookup={
                    "instrument": instrument,
                    "granularity": MarketPrice.Granularity.SPOT,
                    "source": "legacy_crypto_prices",
                },
                defaults={
                    "quoted_at": at_midnight(quote_date, self._timezone()),
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": original_price,
                    "currency": quote_currency,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_stock_splits(self) -> None:
        filename = "stock_splits.csv"
        rows, _ = self._begin_file(filename)
        for row_number, row in enumerate(rows, start=2):
            instrument = self._instrument(
                self.stock_instruments,
                row["isin"],
                filename=filename,
                row_number=row_number,
            )
            self._upsert(
                StockSplit,
                lookup={
                    "workspace": self.workspace,
                    "instrument": instrument,
                    "effective_date": parse_date(
                        row["fecha"],
                        filename=filename,
                        row_number=row_number,
                        field_name="fecha",
                    ),
                },
                defaults={
                    "ratio": parse_decimal(
                        row["ratio"],
                        filename=filename,
                        row_number=row_number,
                        field_name="ratio",
                    ),
                    "source": row.get("fuente") or "legacy",
                    "confirmed_by": None,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _optional_decimal(
        self, row: dict[str, str], field_name: str, *, filename: str, row_number: int
    ) -> Decimal | None:
        if not row.get(field_name):
            return None
        return parse_decimal(
            row[field_name],
            filename=filename,
            row_number=row_number,
            field_name=field_name,
        )

    def _import_real_estate(self) -> None:
        filename = "real_estate.csv"
        rows, _ = self._begin_file(filename)
        movement_filename = "real_estate_movements.csv"
        movement_rows, _ = self._begin_file(movement_filename)
        investments_with_movements = {int(row["investment_id"]) for row in movement_rows}
        default_tax_rate = InstallationSettings.load().default_crowdfunding_tax_rate
        status_map = {
            "activo": RealEstateInvestment.Status.ACTIVE,
            "completado": RealEstateInvestment.Status.COMPLETED,
            "completada": RealEstateInvestment.Status.COMPLETED,
            "impagado": RealEstateInvestment.Status.DEFAULTED,
            "impagada": RealEstateInvestment.Status.DEFAULTED,
            "cancelado": RealEstateInvestment.Status.CANCELLED,
            "cancelada": RealEstateInvestment.Status.CANCELLED,
        }
        for row_number, row in enumerate(rows, start=2):
            status_key = normalized_text(row["estado"])
            if status_key not in status_map:
                raise LegacyImportError(
                    f"unknown real-estate status: {row['estado']}",
                    code="unknown_real_estate_status",
                    filename=filename,
                    row_number=row_number,
                    value=row["estado"],
                )
            provider, provider_label = self._provider(
                filename, row_number, row.get("plataforma", "")
            )
            start_date = parse_date(
                row["fecha_inicio"],
                filename=filename,
                row_number=row_number,
                field_name="fecha_inicio",
            )
            raw_irr = self._optional_decimal(row, "tir", filename=filename, row_number=row_number)
            expected_irr = raw_irr
            if raw_irr is not None and raw_irr > 1:
                expected_irr = raw_irr / Decimal("100")
                self._issue(
                    filename,
                    code="normalized_percentage_scale",
                    message=f"IRR {raw_irr} normalized to fraction {expected_irr}",
                    row_number=row_number,
                    value=row["tir"],
                )
            raw_months = self._optional_decimal(
                row, "meses", filename=filename, row_number=row_number
            )
            if raw_months is not None and raw_months != raw_months.to_integral_value():
                raise LegacyImportError(
                    "months must be an integer",
                    code="invalid_integer",
                    filename=filename,
                    row_number=row_number,
                    value=row["meses"],
                )
            investment = self._upsert(
                RealEstateInvestment,
                lookup={
                    "workspace": self.workspace,
                    "name": row["nombre"],
                    "start_date": start_date,
                },
                defaults={
                    "legacy_id": int(row["id"]),
                    "provider": provider,
                    "provider_label": provider_label,
                    "status": status_map[status_key],
                    "maturity_date": parse_date(
                        row.get("fecha_vencimiento"),
                        filename=filename,
                        row_number=row_number,
                        field_name="fecha_vencimiento",
                        optional=True,
                    ),
                    "expected_profit": self._optional_decimal(
                        row, "beneficio_estimado", filename=filename, row_number=row_number
                    ),
                    "expected_irr": expected_irr,
                    "expected_term_months": int(raw_months) if raw_months is not None else None,
                    "origin": row.get("origen", ""),
                    "currency": normalize_currency(self.workspace.base_currency),
                    "archived_at": None,
                },
                filename=filename,
            )
            if int(row["id"]) in investments_with_movements:
                investment.cash_flows.filter(
                    flow_type__in=(
                        RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                        RealEstateCashFlow.FlowType.PROFIT,
                    ),
                    source_note="legacy:real_estate.csv",
                ).delete()
            initial = parse_decimal(
                row["capital_inicial"],
                filename=filename,
                row_number=row_number,
                field_name="capital_inicial",
            )
            new_capital = parse_decimal(
                row.get("capital_nuevo"),
                filename=filename,
                row_number=row_number,
                field_name="capital_nuevo",
                default=initial,
            )
            returned = parse_decimal(
                row.get("capital_devuelto"),
                filename=filename,
                row_number=row_number,
                field_name="capital_devuelto",
                default=ZERO,
            )
            profit = parse_decimal(
                row.get("beneficio_obtenido"),
                filename=filename,
                row_number=row_number,
                field_name="beneficio_obtenido",
                default=ZERO,
            )
            if new_capital > initial:
                self._issue(
                    filename,
                    code="real_estate_new_capital_exceeds_initial",
                    message="capital_nuevo supera capital_inicial",
                    row_number=row_number,
                    value=row["nombre"],
                )
            return_date = parse_date(
                row.get("fecha_devolucion"),
                filename=filename,
                row_number=row_number,
                field_name="fecha_devolucion",
                optional=True,
            )
            if returned > ZERO and return_date is None:
                self._issue(
                    filename,
                    code="real_estate_return_without_date",
                    message="Returned capital has no effective date",
                    row_number=row_number,
                    value=row["nombre"],
                )
            flows = [
                (RealEstateCashFlow.FlowType.CONTRIBUTION, new_capital, start_date, True),
                (
                    RealEstateCashFlow.FlowType.REINVESTMENT,
                    max(ZERO, initial - new_capital),
                    start_date,
                    False,
                ),
            ]
            if int(row["id"]) not in investments_with_movements:
                flows.extend(
                    (
                        (RealEstateCashFlow.FlowType.CAPITAL_RETURN, returned, return_date, False),
                        (RealEstateCashFlow.FlowType.PROFIT, profit, return_date, False),
                    )
                )
            for flow_type, amount, effective_date, is_external in flows:
                if amount <= ZERO:
                    continue
                if flow_type == RealEstateCashFlow.FlowType.PROFIT and effective_date is None:
                    self._issue(
                        filename,
                        code="real_estate_profit_without_date",
                        message="Realized profit has no effective date",
                        row_number=row_number,
                        value=row["nombre"],
                    )
                flow = self._upsert(
                    RealEstateCashFlow,
                    lookup={
                        "investment": investment,
                        "flow_type": flow_type,
                        "effective_date": effective_date,
                    },
                    defaults={
                        "amount": amount,
                        "is_external": is_external,
                        "source_note": "legacy:real_estate.csv",
                    },
                    filename=filename,
                )
                if (
                    flow_type == RealEstateCashFlow.FlowType.PROFIT
                    and flow.withholding_rate is None
                ):
                    flow.withholding_rate = effective_withholding_rate(investment, default_tax_rate)
                    flow.save(update_fields=("withholding_rate",))
        self._finish_file(filename)

        type_map = {
            "capital_return": RealEstateCashFlow.FlowType.CAPITAL_RETURN,
            "profit": RealEstateCashFlow.FlowType.PROFIT,
        }
        for row_number, row in enumerate(movement_rows, start=2):
            movement_flow_type = type_map.get(row["tipo"])
            if movement_flow_type is None:
                raise LegacyImportError(
                    f"unknown real-estate movement type: {row['tipo']}",
                    code="unknown_real_estate_movement_type",
                    filename=movement_filename,
                    row_number=row_number,
                    value=row["tipo"],
                )
            assert movement_flow_type is not None
            investment = RealEstateInvestment.objects.get(
                workspace=self.workspace,
                legacy_id=int(row["investment_id"]),
            )
            note = row.get("nota", "")
            flow = self._upsert(
                RealEstateCashFlow,
                lookup={
                    "investment": investment,
                    "flow_type": movement_flow_type,
                    "effective_date": parse_date(
                        row["fecha"],
                        filename=movement_filename,
                        row_number=row_number,
                        field_name="fecha",
                    ),
                    "source_note": note,
                },
                defaults={
                    "amount": parse_decimal(
                        row["importe"],
                        filename=movement_filename,
                        row_number=row_number,
                        field_name="importe",
                    ),
                    "is_external": False,
                },
                filename=movement_filename,
            )
            if (
                movement_flow_type == RealEstateCashFlow.FlowType.PROFIT
                and flow.withholding_rate is None
            ):
                flow.withholding_rate = effective_withholding_rate(investment, default_tax_rate)
                flow.save(update_fields=("withholding_rate",))
        self._finish_file(movement_filename)

    def _import_manual_assets(self) -> None:
        filename = "portfolio_items.csv"
        rows, _ = self._begin_file(filename)
        known_names = {
            normalized_text(value)
            for value in (
                list(self.workspace.accounts.values_list("name", flat=True))
                + list(self.workspace.real_estate_investments.values_list("name", flat=True))
            )
        }
        for row_number, row in enumerate(rows, start=2):
            if normalized_text(row["nombre"]) in known_names:
                self._issue(
                    filename,
                    code="possible_portfolio_duplicate",
                    message=f"Possible duplicate of a canonical source: {row['nombre']}",
                    row_number=row_number,
                    value=row["nombre"],
                )
            provider, provider_label = self._provider(
                filename, row_number, row.get("plataforma", "")
            )
            self._upsert(
                ManualAsset,
                lookup={"workspace": self.workspace, "name": row["nombre"]},
                defaults={
                    "legacy_id": int(row["id"]),
                    "provider": provider,
                    "provider_label": provider_label,
                    "asset_class": row["tipo_renta"],
                    "subtype": row.get("subtipo", ""),
                    "value": parse_decimal(
                        row["efectivo"],
                        filename=filename,
                        row_number=row_number,
                        field_name="efectivo",
                    ),
                    "currency": normalize_currency(self.workspace.base_currency),
                    "valued_at": self.valuation_date,
                    "archived_at": None,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_budget(self) -> None:
        filename = "budget.csv"
        rows, _ = self._begin_file(filename)
        for index, row in enumerate(rows):
            row_number = index + 2
            self._upsert(
                BudgetLine,
                lookup={"workspace": self.workspace, "category": row["categoria"]},
                defaults={
                    "amount": parse_decimal(
                        row["cantidad"],
                        filename=filename,
                        row_number=row_number,
                        field_name="cantidad",
                    ),
                    "line_type": row["tipo"],
                    "currency": normalize_currency(self.workspace.base_currency),
                    "sort_order": index,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _import_allocations(self) -> None:
        filename = "calculadora_instrumentos.csv"
        rows, _ = self._begin_file(filename)
        for index, row in enumerate(rows):
            row_number = index + 2
            provider, provider_label = self._provider(
                filename, row_number, row.get("plataforma", "")
            )
            weight = parse_decimal(
                row["porcentaje"],
                filename=filename,
                row_number=row_number,
                field_name="porcentaje",
            )
            if weight > 1:
                weight /= Decimal("100")
                self._issue(
                    filename,
                    code="normalized_percentage_scale",
                    message=f"Weight normalized from integer percentage to fraction: {weight}",
                    row_number=row_number,
                    value=row["porcentaje"],
                )
            self._upsert(
                AllocationRule,
                lookup={"workspace": self.workspace, "name": row["nombre"]},
                defaults={
                    "legacy_id": int(row["id"]),
                    "account": None,
                    "provider": provider,
                    "provider_label": provider_label,
                    "asset_class": row["tipo_renta"],
                    "subtype": row.get("subtipo", ""),
                    "target_weight": weight,
                    "enabled": parse_bool(
                        row["aportar"],
                        filename=filename,
                        row_number=row_number,
                        field_name="aportar",
                    ),
                    "sort_order": index,
                },
                filename=filename,
            )
        self._finish_file(filename)

    def _check(self, name: str, source: Any, database: Any) -> None:
        self.report.checks.append(
            ReconciliationCheck(
                name=name,
                source=source,
                database=database,
                matches=source == database,
            )
        )

    def _source_latest_snapshots(self) -> dict[str, str]:
        result: dict[str, tuple[str, Decimal]] = {}
        for filename, kind, value_field in (
            ("savings_history.csv", Account.Kind.SAVINGS, "saldo"),
            ("investment_history.csv", Account.Kind.MANUAL_INVESTMENT, "valor"),
        ):
            for row_number, row in enumerate(self.source.rows(filename), start=2):
                key = f"{kind}:{row['cuenta_id']}"
                value = parse_decimal(
                    row[value_field],
                    filename=filename,
                    row_number=row_number,
                    field_name=value_field,
                )
                current = result.get(key)
                if current is None or row["fecha"] > current[0]:
                    result[key] = (row["fecha"], value)
        return {key: decimal_text(value) for key, (_, value) in sorted(result.items())}

    def _database_latest_snapshots(self) -> dict[str, str]:
        result: dict[str, str] = {}
        accounts = self.workspace.accounts.filter(
            kind__in=(Account.Kind.SAVINGS, Account.Kind.MANUAL_INVESTMENT)
        )
        for account in accounts:
            snapshot = account.snapshots.order_by("-date").first()
            if snapshot and account.external_id:
                _, kind, legacy_id = account.external_id.split(":", 2)
                result[f"{kind}:{legacy_id}"] = decimal_text(snapshot.value)
        return dict(sorted(result.items()))

    def _source_position_quantities(self) -> dict[str, str]:
        quantities: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
        configurations = (
            ("orders.csv", Account.Kind.FUNDS, "isin"),
            ("stock_orders.csv", Account.Kind.STOCKS, "isin"),
            ("crypto_orders.csv", Account.Kind.CRYPTO, "symbol"),
        )
        for filename, kind, identifier_field in configurations:
            for row_number, row in enumerate(self.source.rows(filename), start=2):
                quantity = parse_decimal(
                    row["titulos"],
                    filename=filename,
                    row_number=row_number,
                    field_name="titulos",
                )
                if filename == "orders.csv":
                    positive = row["tipo_operacion"] in {
                        "SUSCRIPCION",
                        "SUSCR.POR TRASPASO I",
                    }
                else:
                    positive = normalized_text(row["tipo_operacion"]) == "compra"
                key = f"{kind}:{row['cuenta_id']}:{row[identifier_field].upper()}"
                quantities[key] += quantity if positive else -quantity
        return {key: decimal_text(value) for key, value in sorted(quantities.items())}

    def _database_position_quantities(self) -> dict[str, str]:
        account_keys: dict[Any, str] = {}
        for account in self.workspace.accounts.exclude(external_id__isnull=True):
            assert account.external_id is not None
            account_keys[account.id] = f"{account.kind}:{account.external_id.rsplit(':', 1)[-1]}"
        instrument_keys = {
            instrument.id: identifier
            for mapping in (
                self.fund_instruments,
                self.stock_instruments,
                self.crypto_instruments,
            )
            for identifier, instrument in mapping.items()
        }
        quantities: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
        transactions = Transaction.objects.filter(account__workspace=self.workspace)
        positive_types = {Transaction.OperationType.BUY, Transaction.OperationType.TRANSFER_IN}
        for item in transactions:
            key = f"{account_keys[item.account_id]}:{instrument_keys[item.instrument_id]}"
            quantities[key] += (
                item.quantity if item.operation_type in positive_types else -item.quantity
            )
        return {key: decimal_text(value) for key, value in sorted(quantities.items())}

    def _calculate_position_states(
        self,
        events: list[dict[str, Any]],
        splits: dict[str, list[tuple[date, Decimal]]],
    ) -> dict[str, dict[str, str]]:
        grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            grouped[event["key"]].append(event)
        result: dict[str, dict[str, str]] = {}
        for key, items in sorted(grouped.items()):
            quantity = ZERO
            cost = ZERO
            realized = ZERO
            for item in sorted(items, key=lambda value: (value["date"], value["order"])):
                item_quantity = item["quantity"]
                for split_date, ratio in splits.get(item["instrument"], []):
                    if item["date"] < split_date:
                        item_quantity *= ratio
                if item["operation"] in {
                    Transaction.OperationType.BUY,
                    Transaction.OperationType.TRANSFER_IN,
                }:
                    quantity += item_quantity
                    cost += item["amount"]
                    continue
                sold_cost = cost * (item_quantity / quantity) if quantity > ZERO else ZERO
                if item["operation"] == Transaction.OperationType.SELL:
                    realized += item["amount"] - sold_cost
                quantity -= item_quantity
                cost -= sold_cost
            result[key] = {
                "quantity": decimal_text(max(ZERO, quantity)),
                "cost": decimal_text(max(ZERO, cost)),
                "realized": decimal_text(realized),
            }
        return result

    def _source_position_states(self) -> dict[str, dict[str, str]]:
        events: list[dict[str, Any]] = []
        sequence = 0
        for filename, kind, identifier_field in (
            ("orders.csv", Account.Kind.FUNDS, "isin"),
            ("stock_orders.csv", Account.Kind.STOCKS, "isin"),
            ("crypto_orders.csv", Account.Kind.CRYPTO, "symbol"),
        ):
            for row_number, row in enumerate(self.source.rows(filename), start=2):
                sequence += 1
                if filename == "orders.csv":
                    operation = FUND_OPERATIONS[row["tipo_operacion"]][0]
                else:
                    operation = (
                        Transaction.OperationType.BUY
                        if normalized_text(row["tipo_operacion"]) == "compra"
                        else Transaction.OperationType.SELL
                    )
                instrument = row[identifier_field].upper()
                events.append(
                    {
                        "key": f"{kind}:{row['cuenta_id']}:{instrument}",
                        "instrument": instrument,
                        "date": parse_date(
                            row["fecha_operacion"],
                            filename=filename,
                            row_number=row_number,
                            field_name="fecha_operacion",
                        ),
                        "order": sequence,
                        "operation": operation,
                        "quantity": parse_decimal(
                            row["titulos"],
                            filename=filename,
                            row_number=row_number,
                            field_name="titulos",
                        ),
                        "amount": abs(
                            parse_decimal(
                                row["importe_neto"],
                                filename=filename,
                                row_number=row_number,
                                field_name="importe_neto",
                            )
                        ),
                    }
                )
        source_splits: defaultdict[str, list[tuple[date, Decimal]]] = defaultdict(list)
        filename = "stock_splits.csv"
        for row_number, row in enumerate(self.source.rows(filename), start=2):
            split_date = parse_date(
                row["fecha"],
                filename=filename,
                row_number=row_number,
                field_name="fecha",
            )
            assert split_date is not None
            source_splits[row["isin"].upper()].append(
                (
                    split_date,
                    parse_decimal(
                        row["ratio"],
                        filename=filename,
                        row_number=row_number,
                        field_name="ratio",
                    ),
                )
            )
        return self._calculate_position_states(events, source_splits)

    def _database_position_states(self) -> dict[str, dict[str, str]]:
        account_keys: dict[Any, str] = {}
        for account in self.workspace.accounts.exclude(external_id__isnull=True):
            assert account.external_id is not None
            account_keys[account.id] = f"{account.kind}:{account.external_id.rsplit(':', 1)[-1]}"
        instrument_keys = {
            instrument.id: identifier
            for mapping in (
                self.fund_instruments,
                self.stock_instruments,
                self.crypto_instruments,
            )
            for identifier, instrument in mapping.items()
        }
        events = []
        transactions = Transaction.objects.filter(account__workspace=self.workspace).order_by(
            "trade_date", "created_at"
        )
        for sequence, item in enumerate(transactions):
            instrument = instrument_keys[item.instrument_id]
            events.append(
                {
                    "key": f"{account_keys[item.account_id]}:{instrument}",
                    "instrument": instrument,
                    "date": item.trade_date,
                    "order": sequence,
                    "operation": item.operation_type,
                    "quantity": item.quantity,
                    "amount": item.net_amount,
                }
            )
        database_splits: defaultdict[str, list[tuple[date, Decimal]]] = defaultdict(list)
        for split in StockSplit.objects.filter(workspace=self.workspace):
            database_splits[instrument_keys[split.instrument_id]].append(
                (split.effective_date, split.ratio)
            )
        return self._calculate_position_states(events, database_splits)

    def _source_latest_prices(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for filename, prefix, identifier_field in (
            ("fund_prices.csv", "fund", "isin"),
            ("stock_prices.csv", "stock", "isin"),
            ("crypto_prices.csv", "crypto", "symbol"),
        ):
            for row_number, row in enumerate(self.source.rows(filename), start=2):
                if not row.get("precio"):
                    continue
                result[f"{prefix}:{row[identifier_field].upper()}"] = decimal_text(
                    parse_decimal(
                        row.get("precio_orig") or row["precio"],
                        filename=filename,
                        row_number=row_number,
                        field_name="precio_orig/precio",
                    )
                )
        return dict(sorted(result.items()))

    def _database_latest_prices(self) -> dict[str, str]:
        result: dict[str, str] = {}
        configurations = (
            ("fund", self.fund_instruments, "legacy_fund_prices"),
            ("stock", self.stock_instruments, "legacy_stock_prices"),
            ("crypto", self.crypto_instruments, "legacy_crypto_prices"),
        )
        for prefix, mapping, source in configurations:
            for identifier, instrument in mapping.items():
                price = instrument.prices.filter(source=source).order_by("-quoted_at").first()
                if price:
                    result[f"{prefix}:{identifier}"] = decimal_text(price.close)
        return dict(sorted(result.items()))

    def _source_real_estate_capital(self) -> str:
        total = ZERO
        filename = "real_estate.csv"
        for row_number, row in enumerate(self.source.rows(filename), start=2):
            total += parse_decimal(
                row["capital_inicial"],
                filename=filename,
                row_number=row_number,
                field_name="capital_inicial",
            )
            total -= parse_decimal(
                row.get("capital_devuelto"),
                filename=filename,
                row_number=row_number,
                field_name="capital_devuelto",
                default=ZERO,
            )
        return decimal_text(total)

    def _database_real_estate_capital(self) -> str:
        total = ZERO
        flows = RealEstateCashFlow.objects.filter(investment__workspace=self.workspace)
        for flow in flows:
            if flow.flow_type in {
                RealEstateCashFlow.FlowType.CONTRIBUTION,
                RealEstateCashFlow.FlowType.REINVESTMENT,
            }:
                total += flow.amount
            elif flow.flow_type == RealEstateCashFlow.FlowType.CAPITAL_RETURN:
                total -= flow.amount
        return decimal_text(total)

    def _reconcile(self) -> None:
        expected_accounts = {
            kind: len(self.source.rows(filename)) for filename, kind, _ in ACCOUNT_FILES
        }
        actual_accounts = {
            kind: self.workspace.accounts.filter(kind=kind).count() for kind in expected_accounts
        }
        self._check("accounts_by_kind", expected_accounts, actual_accounts)

        expected_snapshots = len(self.source.rows("savings_history.csv")) + len(
            self.source.rows("investment_history.csv")
        )
        actual_snapshots = AccountSnapshot.objects.filter(account__workspace=self.workspace).count()
        self._check("snapshot_count", expected_snapshots, actual_snapshots)
        self._check(
            "latest_balances",
            self._source_latest_snapshots(),
            self._database_latest_snapshots(),
        )
        source_contributions = sum(
            (
                parse_decimal(
                    row.get("aporte"),
                    filename=filename,
                    row_number=row_number,
                    field_name="aporte",
                    default=ZERO,
                )
                for filename in ("savings_history.csv", "investment_history.csv")
                for row_number, row in enumerate(self.source.rows(filename), start=2)
            ),
            ZERO,
        )
        database_contributions = (
            AccountSnapshot.objects.filter(account__workspace=self.workspace).aggregate(
                total=Sum("contribution")
            )["total"]
            or ZERO
        )
        self._check(
            "snapshot_contribution_total",
            decimal_text(source_contributions),
            decimal_text(database_contributions),
        )

        expected_transactions = sum(
            len(self.source.rows(filename))
            for filename in ("orders.csv", "stock_orders.csv", "crypto_orders.csv")
        )
        actual_transactions = Transaction.objects.filter(account__workspace=self.workspace).count()
        self._check("transaction_count", expected_transactions, actual_transactions)
        self._check(
            "position_quantities",
            self._source_position_quantities(),
            self._database_position_quantities(),
        )
        self._check(
            "position_cost_and_realized_pnl",
            self._source_position_states(),
            self._database_position_states(),
        )

        expected_instruments = sum(
            len(self.source.rows(filename))
            for filename in ("funds.csv", "stocks.csv", "cryptos.csv")
        )
        imported_instrument_ids = {
            instrument.id
            for mapping in (
                self.fund_instruments,
                self.stock_instruments,
                self.crypto_instruments,
            )
            for instrument in mapping.values()
        }
        self._check("instrument_count", expected_instruments, len(imported_instrument_ids))

        expected_prices = (
            sum(1 for row in self.source.rows("fund_prices.csv") if row.get("precio"))
            + len(self.source.rows("stock_prices.csv"))
            + len(self.source.rows("crypto_prices.csv"))
        )
        actual_prices = MarketPrice.objects.filter(
            instrument_id__in=imported_instrument_ids,
            source__in=(
                "legacy_fund_prices",
                "legacy_stock_prices",
                "legacy_crypto_prices",
            ),
        ).count()
        self._check("price_count", expected_prices, actual_prices)
        self._check(
            "latest_prices",
            self._source_latest_prices(),
            self._database_latest_prices(),
        )
        self._check(
            "split_count",
            len(self.source.rows("stock_splits.csv")),
            StockSplit.objects.filter(workspace=self.workspace).count(),
        )
        self._check(
            "real_estate_count",
            len(self.source.rows("real_estate.csv")),
            RealEstateInvestment.objects.filter(workspace=self.workspace).count(),
        )
        self._check(
            "real_estate_live_capital",
            self._source_real_estate_capital(),
            self._database_real_estate_capital(),
        )
        self._check(
            "manual_asset_count",
            len(self.source.rows("portfolio_items.csv")),
            ManualAsset.objects.filter(workspace=self.workspace).count(),
        )
        self._check(
            "budget_count",
            len(self.source.rows("budget.csv")),
            BudgetLine.objects.filter(workspace=self.workspace).count(),
        )
        source_budget = sum(
            (
                parse_decimal(
                    row["cantidad"],
                    filename="budget.csv",
                    row_number=index,
                    field_name="cantidad",
                )
                for index, row in enumerate(self.source.rows("budget.csv"), start=2)
            ),
            ZERO,
        )
        database_budget = (
            BudgetLine.objects.filter(workspace=self.workspace).aggregate(total=Sum("amount"))[
                "total"
            ]
            or ZERO
        )
        self._check("budget_total", decimal_text(source_budget), decimal_text(database_budget))
        self._check(
            "allocation_count",
            len(self.source.rows("calculadora_instrumentos.csv")),
            AllocationRule.objects.filter(workspace=self.workspace).count(),
        )
        source_weight = sum(
            (
                parse_decimal(
                    row["porcentaje"],
                    filename="calculadora_instrumentos.csv",
                    row_number=index,
                    field_name="porcentaje",
                )
                for index, row in enumerate(
                    self.source.rows("calculadora_instrumentos.csv"), start=2
                )
            ),
            ZERO,
        )
        database_weight = (
            AllocationRule.objects.filter(workspace=self.workspace).aggregate(
                total=Sum("target_weight")
            )["total"]
            or ZERO
        )
        self._check(
            "allocation_weight_total",
            decimal_text(source_weight),
            decimal_text(database_weight),
        )
