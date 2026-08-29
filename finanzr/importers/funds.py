"""Parser for MyInvestor/Inversis fund statements."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from html import escape, unescape
from html.parser import HTMLParser
from typing import Any

from .base import (
    BaseImporter,
    ImportContext,
    ImporterError,
    ImporterField,
    ImporterFormat,
    ImportIssue,
    ImportResult,
    InputKind,
)
from .i18n import gettext
from .i18n import gettext_noop as _

SUPPORTED_FUND_OPERATION_LABELS = frozenset(
    {
        "SUSCRIPCION",
        "SUSCR.POR TRASPASO I",
        "REEMB.POR TRASPASO I",
        "REEMBOLSO",
    }
)
HTML_TABLE_SECTIONS = frozenset({"thead", "tbody", "tfoot"})


def clean_date(value: str) -> str:
    """Extract YYYY-MM-DD and ignore residual broker content."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else value.strip()


def order_from_cells(cells: list[str], account_id: int) -> dict[str, Any] | None:
    """Convert the broker's 11 columns into an order."""
    if len(cells) != 11 or not cells[0] or not cells[0].lstrip()[:1].isdigit():
        return None
    try:
        return {
            "operacion_id": cells[2].strip(),
            "fecha_operacion": clean_date(cells[0]),
            "fecha_liquidacion": clean_date(cells[1]),
            "mercado": cells[3],
            "tipo_operacion": cells[4],
            "isin": cells[5],
            "nombre_fondo": cells[6],
            "titulos": float(cells[7].replace(",", ".")),
            "divisa": cells[8],
            "precio_neto": float(cells[9].replace(",", ".")),
            "importe_neto": float(cells[10].replace(",", ".")),
            "cuenta_id": account_id,
        }
    except (ValueError, IndexError):
        return None


@dataclass
class _HtmlRow:
    cells: list[str] = field(default_factory=list)
    cell_tags: list[str] = field(default_factory=list)
    cell_tag: str | None = None
    cell_text: list[str] = field(default_factory=list)
    invalid: bool = False


@dataclass
class _HtmlTable:
    rows: list[_HtmlRow] = field(default_factory=list)
    row: _HtmlRow | None = None
    section: str | None = None
    invalid: bool = False
    nested: bool = False


class _FundHtmlParser(HTMLParser):
    """Collect strictly nested table rows and cells from an HTML export."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_HtmlTable] = []
        self._stack: list[_HtmlTable] = []
        self.invalid_document = False

    @property
    def _table(self) -> _HtmlTable | None:
        return self._stack[-1] if self._stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag == "table":
            if self._table is not None:
                self.invalid_document = True
                self._table.invalid = True
                self._stack.append(_HtmlTable(nested=True, invalid=True))
            else:
                self._stack.append(_HtmlTable())
            return

        table = self._table
        if table is None:
            if tag in {"tr", "td", "th"} or tag in HTML_TABLE_SECTIONS:
                self.invalid_document = True
            return
        if tag in HTML_TABLE_SECTIONS:
            if table.section is not None or table.row is not None:
                self.invalid_document = True
                table.invalid = True
                return
            table.section = tag
            return
        if tag == "tr":
            if table.row is not None:
                self.invalid_document = True
                table.invalid = True
                table.row.invalid = True
            table.row = _HtmlRow()
            return
        if tag not in {"td", "th"}:
            return
        if table.row is None:
            self.invalid_document = True
            table.invalid = True
            return
        if table.row.cell_tag is not None:
            self.invalid_document = True
            table.invalid = True
            table.row.invalid = True
            return
        table.row.cell_tag = tag
        table.row.cell_text = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"table", "tr", "td", "th"} or tag in HTML_TABLE_SECTIONS:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        table = self._table
        if tag == "table":
            if table is None:
                self.invalid_document = True
                return
            if table.section is not None:
                self.invalid_document = True
                table.invalid = True
                table.section = None
            if table.row is not None:
                self.invalid_document = True
                table.invalid = True
                table.row.invalid = True
                table.row = None
            self.tables.append(self._stack.pop())
            return
        if table is None:
            if tag in {"tr", "td", "th"} or tag in HTML_TABLE_SECTIONS:
                self.invalid_document = True
            return
        if tag in HTML_TABLE_SECTIONS:
            if table.section != tag or table.row is not None:
                self.invalid_document = True
                table.invalid = True
                return
            table.section = None
            return
        if tag == "tr":
            if table.row is None:
                self.invalid_document = True
                table.invalid = True
                return
            if table.row.cell_tag is not None:
                self.invalid_document = True
                table.invalid = True
                table.row.invalid = True
                table.row.cell_tag = None
                table.row.cell_text = []
            table.rows.append(table.row)
            table.row = None
            return
        if tag not in {"td", "th"}:
            return
        if table.row is None or table.row.cell_tag is None:
            self.invalid_document = True
            table.invalid = True
            return
        if tag != table.row.cell_tag:
            self.invalid_document = True
            table.invalid = True
            table.row.invalid = True
        else:
            table.row.cells.append("".join(table.row.cell_text))
            table.row.cell_tags.append(table.row.cell_tag)
        table.row.cell_tag = None
        table.row.cell_text = []

    def handle_data(self, data: str) -> None:
        table = self._table
        if table is None or table.row is None:
            return
        if table.row.cell_tag is not None:
            table.row.cell_text.append(data)
        elif data.strip():
            self.invalid_document = True
            table.invalid = True
            table.row.invalid = True

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def finish(self) -> None:
        """Mark all still-open structural elements as invalid."""
        while self._stack:
            self.invalid_document = True
            table = self._stack.pop()
            table.invalid = True
            table.section = None
            if table.row is not None:
                table.row.invalid = True
            self.tables.append(table)


def _is_fund_data_row(cells: list[str]) -> bool:
    """Return whether cells have the semantic shape of an Inversis data row."""
    if (
        len(cells) != 11
        or not cells[2].strip()
        or cells[4].strip() not in SUPPORTED_FUND_OPERATION_LABELS
        or not cells[5].strip()
        or not cells[6].strip()
        or not cells[8].strip()
    ):
        return False
    isin = cells[5].strip()
    if (
        len(isin) != 12
        or not isin[:2].isascii()
        or not isin[:2].isalpha()
        or not isin[2:].isascii()
        or not isin[2:].isalnum()
        or not isin[-1].isdigit()
    ):
        return False
    order = order_from_cells(cells, 0)
    if order is None:
        return False
    try:
        date.fromisoformat(str(order["fecha_operacion"])[:10])
        date.fromisoformat(str(order["fecha_liquidacion"])[:10])
        return all(
            math.isfinite(float(order[field]))
            for field in ("titulos", "precio_neto", "importe_neto")
        )
    except (TypeError, ValueError):
        return False


def _is_fund_data_candidate(row: _HtmlRow) -> bool:
    """Return whether a non-header row must be validated as fund data."""
    return bool(row.cells) and not all(tag == "th" for tag in row.cell_tags)


def _canonical_table(rows: list[list[str]]) -> str:
    return (
        "<table>"
        + "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>"
            for cells in rows
        )
        + "</table>"
    )


class FundBrokerImporter(BaseImporter):
    slug = "fund_broker"
    display_name = _("MyInvestor/Inversis funds")
    target = "fund_orders"
    target_label = _("Funds")
    description = _("Imports subscriptions, redemptions, and transfers of index funds.")
    source_instructions = _(
        "This file can only be exported by accessing your MyInvestor account through "
        "Inversis. In Inversis, go to Investments → Funds → Operations and Queries → "
        "Operations query → Export Excel."
    )
    input_kind = InputKind.TEXT
    formats = (
        ImporterFormat(
            ".csv",
            _("Semicolon-delimited CSV"),
            _("UTF-8 text without a header; each row must contain 11 columns separated by ;."),
        ),
        ImporterFormat(
            ".html",
            _("HTML table"),
            _("The table exported by the broker; each <tr> row and its 11 cells are processed."),
        ),
        ImporterFormat(
            ".xls",
            _("HTML with an XLS extension"),
            _("Inversis HTML export saved as .xls; it is not a binary Excel workbook."),
        ),
    )
    fields = (
        ImporterField(
            "fecha_operacion",
            _("Trade date"),
            _("Effective date of the order."),
            "2026-01-15",
            position=1,
        ),
        ImporterField(
            "fecha_liquidacion",
            _("Settlement date"),
            _("Date on which the transaction settles."),
            "2026-01-17",
            position=2,
        ),
        ImporterField(
            "operacion_id",
            _("Identifier"),
            _("Unique transaction code."),
            "OP-84721",
            position=3,
        ),
        ImporterField(
            "mercado",
            _("Market"),
            _("Market or channel reported by the broker."),
            "FONDOS",
            position=4,
        ),
        ImporterField(
            "tipo_operacion",
            _("Type"),
            _("Subscription, redemption, or transfer."),
            "SUSCRIPCION",
            position=5,
        ),
        ImporterField(
            "isin", "ISIN", _("International fund identifier."), "IE00B03HCZ61", position=6
        ),
        ImporterField(
            "nombre_fondo",
            _("Fund name"),
            _("Fund's commercial name."),
            "Vanguard Global Stock Index",
            position=7,
        ),
        ImporterField(
            "titulos",
            _("Units"),
            _("Number of units, with a comma or decimal point."),
            "12,458",
            position=8,
        ),
        ImporterField("divisa", _("Currency"), _("Transaction currency code."), "EUR", position=9),
        ImporterField("precio_neto", _("Net price"), _("Price per unit."), "51,4139", position=10),
        ImporterField(
            "importe_neto",
            _("Net amount"),
            _("Total transaction amount."),
            "640,52",
            position=11,
        ),
    )
    rules = (
        _("Rows must keep the exact 11-column order shown."),
        _("Dates must use the YYYY-MM-DD format."),
        _("Subscriptions, redemptions, and inbound or outbound transfers are supported."),
    )

    @staticmethod
    def _is_binary_excel(raw: bytes) -> bool:
        return raw.startswith(
            (
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  # OLE/BIFF .xls
                b"PK\x03\x04",  # ZIP/XLSX
                b"PK\x05\x06",  # empty ZIP
                b"PK\x07\x08",  # spanned ZIP
            )
        )

    @staticmethod
    def _extract_html_table(source: str) -> str | None:
        parser = _FundHtmlParser()
        try:
            parser.feed(source)
            parser.close()
        except (AssertionError, ValueError):
            return None
        parser.finish()
        for table in parser.tables:
            candidates = [row for row in table.rows if _is_fund_data_candidate(row)]
            if (
                not parser.invalid_document
                and not table.invalid
                and not table.nested
                and candidates
                and all(_is_fund_data_row(row.cells) for row in candidates)
            ):
                return _canonical_table([row.cells for row in candidates])
        return None

    def decode(self, raw: bytes, extension: str) -> str:
        """Decode fund exports, accepting legacy Windows-1252 Inversis HTML."""
        extension = extension.casefold()
        if extension not in {".xls", ".html"}:
            return super().decode(raw, extension)

        if self._is_binary_excel(raw):
            raise ImporterError(
                gettext(
                    "Binary Excel workbooks are not supported; upload the Inversis HTML "
                    "export saved as .xls or .html"
                )
            )

        try:
            source = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                source = raw.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise ImporterError(
                    gettext("The Inversis HTML export must be encoded as UTF-8 or Windows-1252")
                ) from exc

        table = self._extract_html_table(source)
        if table is None:
            raise ImporterError(
                gettext("The uploaded %(extension)s file is not a valid Inversis HTML table export")
                % {"extension": extension}
            )
        return table

    def _parse(self, source: str, context: ImportContext) -> ImportResult:
        rows: list[list[str]] = []
        source_format = "html" if "<tr" in source.lower() else "csv"
        if source_format == "html":
            html_rows = re.findall(r"<tr\b[^>]*>(.*?)</tr\s*>", source, re.DOTALL | re.IGNORECASE)
            for html_row in html_rows:
                cells = re.findall(
                    r"<t[dh]\b[^>]*>(.*?)</t[dh]\s*>",
                    html_row,
                    re.DOTALL | re.IGNORECASE,
                )
                cleaned = [
                    unescape(re.sub(r"<[^>]+>", "", cell)).strip().replace("\xa0", "").strip()
                    for cell in cells
                ]
                rows.append(cleaned)
        else:
            rows = [
                [cell.strip().replace("\xa0", "").strip() for cell in line.split(";")]
                for line in source.splitlines()
            ]

        result = ImportResult(metadata={"source_format": source_format})
        for row_number, cells in enumerate(rows, start=1):
            order = order_from_cells(cells, int(context.account_id))
            if order:
                result.records.append(order)
            elif any(cells):
                result.skipped += 1
                result.issues.append(
                    ImportIssue(
                        code="invalid_fund_row",
                        message=gettext(
                            "The row does not contain the expected 11 columns or has invalid values"
                        ),
                        row_number=row_number,
                    )
                )
        return result


IMPORTER = FundBrokerImporter()


def parse_fund_extract(content: str, account_id: int) -> list[dict[str, Any]]:
    """Convenience adapter for callers of the function-based API."""
    return IMPORTER.parse(content, ImportContext(account_id=account_id)).records
