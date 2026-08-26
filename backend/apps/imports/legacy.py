from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, tzinfo
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FILE_SCHEMAS: dict[str, frozenset[str]] = {
    "savings_accounts.csv": frozenset({"id", "nombre", "banco", "tipo"}),
    "savings_history.csv": frozenset({"fecha", "cuenta_id", "saldo", "aporte", "intereses"}),
    "investment_accounts.csv": frozenset({"id", "nombre", "plataforma", "tipo"}),
    "investment_history.csv": frozenset({"fecha", "cuenta_id", "valor", "aporte", "intereses"}),
    "fund_accounts.csv": frozenset({"id", "nombre", "tipo", "plataforma"}),
    "funds.csv": frozenset({"isin", "nombre", "tipo", "subtipo", "ticker"}),
    "orders.csv": frozenset(
        {
            "operacion_id",
            "fecha_operacion",
            "fecha_liquidacion",
            "mercado",
            "tipo_operacion",
            "isin",
            "nombre_fondo",
            "titulos",
            "divisa",
            "precio_neto",
            "importe_neto",
            "cuenta_id",
        }
    ),
    "fund_prices.csv": frozenset({"isin", "precio", "updated"}),
    "stock_accounts.csv": frozenset({"id", "nombre", "tipo", "plataforma"}),
    "stocks.csv": frozenset({"isin", "ticker", "nombre"}),
    "stock_orders.csv": frozenset(
        {
            "operacion_id",
            "fecha_operacion",
            "isin",
            "nombre_activo",
            "titulos",
            "precio_compra",
            "importe_neto",
            "comision",
            "cuenta_id",
            "tipo_operacion",
            "es_saveback",
        }
    ),
    "stock_prices.csv": frozenset({"isin", "fecha", "precio", "updated", "moneda", "precio_orig"}),
    "stock_splits.csv": frozenset({"isin", "fecha", "ratio", "fuente"}),
    "crypto_accounts.csv": frozenset({"id", "nombre", "plataforma"}),
    "cryptos.csv": frozenset({"symbol", "ticker", "nombre"}),
    "crypto_orders.csv": frozenset(
        {
            "operacion_id",
            "fecha_operacion",
            "symbol",
            "nombre_activo",
            "titulos",
            "precio_compra",
            "importe_neto",
            "comision",
            "cuenta_id",
            "tipo_operacion",
        }
    ),
    "crypto_prices.csv": frozenset({"moneda", "precio_orig", "symbol", "precio", "updated"}),
    "real_estate.csv": frozenset(
        {
            "id",
            "nombre",
            "plataforma",
            "estado",
            "capital_inicial",
            "capital_devuelto",
            "beneficio_obtenido",
            "beneficio_estimado",
            "fecha_inicio",
            "fecha_vencimiento",
            "tir",
            "meses",
            "origen",
            "fecha_devolucion",
            "capital_nuevo",
        }
    ),
    "real_estate_movements.csv": frozenset({"investment_id", "fecha", "tipo", "importe", "nota"}),
    "portfolio_items.csv": frozenset(
        {"id", "nombre", "tipo_renta", "subtipo", "plataforma", "efectivo"}
    ),
    "budget.csv": frozenset({"categoria", "cantidad", "tipo"}),
    "calculadora_instrumentos.csv": frozenset(
        {"id", "nombre", "plataforma", "tipo_renta", "subtipo", "porcentaje", "aportar"}
    ),
}


class LegacyImportError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_legacy_data",
        filename: str | None = None,
        row_number: int | None = None,
        value: str | None = None,
    ) -> None:
        self.code = code
        self.filename = filename
        self.row_number = row_number
        self.value = value
        location = filename or "legacy data"
        if row_number is not None:
            location += f":row {row_number}"
        super().__init__(f"{location}: {message}")


@dataclass
class FileReport:
    filename: str
    read: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0


@dataclass
class ReconciliationCheck:
    name: str
    source: Any
    database: Any
    matches: bool


@dataclass
class LegacyImportReport:
    workspace: str
    dry_run: bool
    files: dict[str, FileReport] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    checks: list[ReconciliationCheck] = field(default_factory=list)

    def file(self, filename: str, read: int | None = None) -> FileReport:
        report = self.files.setdefault(filename, FileReport(filename=filename))
        if read is not None:
            report.read = read
        return report

    @property
    def valid(self) -> bool:
        return not any(not check.matches for check in self.checks) and not any(
            issue["severity"] == "error" for issue in self.issues
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "dry_run": self.dry_run,
            "valid": self.valid,
            "files": {name: asdict(value) for name, value in self.files.items()},
            "issues": self.issues,
            "checks": [asdict(check) for check in self.checks],
        }


class LegacyDataSource:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        if not self.data_dir.is_dir():
            raise LegacyImportError(
                "the directory does not exist", code="missing_data_directory", value=str(data_dir)
            )
        self._rows: dict[str, list[dict[str, str]]] = {}

    def path(self, filename: str) -> Path:
        if filename not in FILE_SCHEMAS:
            raise LegacyImportError(f"unregistered file: {filename}")
        path = self.data_dir / filename
        if not path.is_file():
            raise LegacyImportError(
                "required file is missing", code="missing_file", filename=filename
            )
        return path

    def rows(self, filename: str) -> list[dict[str, str]]:
        if filename in self._rows:
            return self._rows[filename]
        path = self.path(filename)
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                actual = set(reader.fieldnames or ())
                missing = FILE_SCHEMAS[filename] - actual
                if missing:
                    raise LegacyImportError(
                        f"missing columns: {', '.join(sorted(missing))}",
                        code="missing_columns",
                        filename=filename,
                    )
                rows = [
                    {key: (value or "").strip() for key, value in row.items() if key is not None}
                    for row in reader
                ]
        except UnicodeDecodeError as exc:
            raise LegacyImportError(
                "the file is not UTF-8 encoded",
                code="invalid_encoding",
                filename=filename,
            ) from exc
        self._rows[filename] = rows
        return rows

    def sha256(self, filename: str) -> str:
        return hashlib.sha256(self.path(filename).read_bytes()).hexdigest()

    def validate_all(self) -> None:
        for filename in FILE_SCHEMAS:
            self.rows(filename)

    def latest_date(self) -> date:
        result = date.min
        for filename in FILE_SCHEMAS:
            for row in self.rows(filename):
                for key in (
                    "fecha",
                    "updated",
                    "fecha_operacion",
                    "fecha_inicio",
                    "fecha_vencimiento",
                    "fecha_devolucion",
                ):
                    raw = row.get(key, "")
                    if not raw:
                        continue
                    try:
                        result = max(result, date.fromisoformat(raw[:10]))
                    except ValueError:
                        continue
        return result if result != date.min else date.today()


def parse_decimal(
    raw: Any,
    *,
    filename: str,
    row_number: int,
    field_name: str,
    default: Decimal | None = None,
) -> Decimal:
    text = str(raw or "").strip().replace("\u00a0", "")
    if not text:
        if default is not None:
            return default
        raise LegacyImportError(
            f"{field_name} is empty",
            code="invalid_decimal",
            filename=filename,
            row_number=row_number,
        )
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise LegacyImportError(
            f"{field_name} is not a decimal number",
            code="invalid_decimal",
            filename=filename,
            row_number=row_number,
            value=text[:120],
        ) from exc
    if not value.is_finite():
        raise LegacyImportError(
            f"{field_name} is not finite",
            code="invalid_decimal",
            filename=filename,
            row_number=row_number,
            value=text[:120],
        )
    return value


def parse_date(
    raw: Any,
    *,
    filename: str,
    row_number: int,
    field_name: str,
    optional: bool = False,
) -> date | None:
    text = str(raw or "").strip()
    if not text and optional:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise LegacyImportError(
            f"{field_name} is not a valid ISO date",
            code="invalid_date",
            filename=filename,
            row_number=row_number,
            value=text[:120],
        ) from exc


def parse_bool(raw: Any, *, filename: str, row_number: int, field_name: str) -> bool:
    text = str(raw or "").strip().lower()
    if text in {"true", "1", "yes", "sí", "si"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise LegacyImportError(
        f"{field_name} is not a boolean",
        code="invalid_boolean",
        filename=filename,
        row_number=row_number,
        value=text[:120],
    )


def at_midnight(value: date, timezone: tzinfo) -> datetime:
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone)


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
