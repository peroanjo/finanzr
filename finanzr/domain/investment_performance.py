"""Shared historical performance calculations for traded investments.

The API deliberately supplies plain records and already converted market
histories.  Keeping the calculation here independent of Django makes the
transfer, split, saveback, and account-filter rules reusable and testable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from .money import ZERO, decimal
from .positions import base_amount

Record = Mapping[str, Any]

_FUND_BUYS = frozenset({"SUSCRIPCION", "SUSCR.POR TRASPASO I", "buy", "BUY"})
_FUND_SELLS = frozenset({"REEMBOLSO", "REEMB.POR TRASPASO I", "sell", "SELL"})
_FUND_TRANSFER_IN = "SUSCR.POR TRASPASO I"
_FUND_TRANSFER_OUT = "REEMB.POR TRASPASO I"
_TRADED_BUYS = frozenset({"Compra", "BUY", "buy", "Buy", "compra"})
_TRADED_SELLS = frozenset({"Venta", "SELL", "sell", "Sell", "venta"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _record_date(record: Record) -> str:
    return _text(record.get("fecha_operacion") or record.get("trade_date"))[:10]


def _operation(record: Record) -> str:
    return _text(record.get("tipo_operacion") or record.get("operation_type"))


def _asset(record: Record, kind: str) -> str:
    key = "symbol" if kind == "crypto" else "isin"
    return _text(record.get(key) or record.get("asset_id"))


def _account(record: Record) -> str:
    return _text(record.get("cuenta_id") or record.get("account_id"))


def _quantity(record: Record) -> Decimal:
    return decimal(record.get("titulos") if "titulos" in record else record.get("quantity"))


def _amount(record: Record) -> Decimal:
    """Use the one stored net/base amount; fees must not be added twice."""
    return (
        base_amount(record)
        if "importe_neto" in record or "importe_base" in record
        else decimal(
            record.get("base_net_amount")
            if record.get("base_net_amount") not in (None, "")
            else record.get("net_amount")
        )
    )


def _is_saveback(record: Record) -> bool:
    if not bool(record.get("es_saveback") or record.get("is_saveback")):
        return False
    provider = _text(
        record.get("plataforma") or record.get("provider") or record.get("provider_label")
    )
    # Match the existing position-analysis policy exactly: only explicit Trade
    # Republic saveback rows qualify; a missing or unrelated provider is a
    # normal-cost purchase even when its flag is set.
    return "trade republic" in provider.casefold()


def _split_factor(
    asset: str, order_date: str, as_of: str, splits: Mapping[str, Iterable[Record]]
) -> Decimal:
    factor = Decimal("1")
    for split in splits.get(asset, ()):
        split_date = _text(split.get("fecha") or split.get("effective_date"))[:10]
        if not split_date or not (order_date < split_date <= as_of):
            continue
        try:
            ratio = decimal(split.get("ratio"))
        except (ArithmeticError, ValueError):
            continue
        if ratio > ZERO:
            factor *= ratio
    return factor


def _normalise_splits(splits: Iterable[Record]) -> dict[str, list[Record]]:
    grouped: dict[str, list[Record]] = {}
    for split in splits:
        asset = _text(split.get("isin") or split.get("asset_id"))
        if asset:
            grouped.setdefault(asset, []).append(split)
    return grouped


def calculate_investment_performance(
    records: Iterable[Record],
    histories: Mapping[str, Mapping[str, Any]],
    *,
    kind: str = "fund",
    account_id: int | str = "all",
    splits: Iterable[Record] = (),
    ignore_savebacks: bool = False,
    timeline_start: str | None = None,
    timeline_end: str | None = None,
) -> list[dict[str, Any]]:
    """Return dated value/invested/P&L points for one investment kind.

    ``histories`` contains prices already converted into the workspace base
    currency.  Missing history for an instrument is intentionally ignored so
    one unavailable ticker cannot hide the rest of a portfolio.
    """
    if kind not in {"fund", "stock", "crypto"}:
        raise ValueError(f"Unsupported investment kind: {kind}")
    selected_account = _text(account_id)
    selected = [
        dict(record)
        for record in records
        if (selected_account in {"", "all"} or _account(record) == selected_account)
        and (not timeline_end or _record_date(record) <= timeline_end)
    ]
    operations = {
        "buys": _FUND_BUYS if kind == "fund" else _TRADED_BUYS,
        "sells": _FUND_SELLS if kind == "fund" else _TRADED_SELLS,
        # Fund transfer legs change holdings but are never external capital.
        "external_buys": {"SUSCRIPCION", "buy", "BUY"} if kind == "fund" else _TRADED_BUYS,
        "external_sells": {"REEMBOLSO", "sell", "SELL"} if kind == "fund" else _TRADED_SELLS,
    }
    # Preserve source order only as a deterministic tie breaker for same-day
    # transactions.  The series itself is driven by available market dates.
    selected.sort(key=lambda record: (_record_date(record), _text(record.get("operacion_id"))))
    usable_assets = {
        _asset(record, kind)
        for record in selected
        if (
            _asset(record, kind)
            and _asset(record, kind) in histories
            and histories[_asset(record, kind)]
        )
    }
    if not usable_assets:
        return []
    all_dates_set = {
        _text(value)[:10]
        for asset in usable_assets
        for value in histories.get(asset, {})
        if _text(value)[:10]
        and (not timeline_start or _text(value)[:10] >= timeline_start)
        and (not timeline_end or _text(value)[:10] <= timeline_end)
    }
    # Include transaction dates so a sale after the last quote still produces
    # a terminal realized-P&L point.  The API filters the supplied records to
    # its requested custom period before calling this calculation.
    all_dates_set.update(
        _record_date(record)
        for record in selected
        if _record_date(record)
        and (not timeline_start or _record_date(record) >= timeline_start)
        and (not timeline_end or _record_date(record) <= timeline_end)
    )
    all_dates = sorted(all_dates_set)
    if not all_dates:
        return []
    grouped_splits = _normalise_splits(splits) if kind == "stock" else {}
    buys = operations["buys"]
    sells = operations["sells"]
    external_buys = operations["external_buys"]
    external_sells = operations["external_sells"]

    def amount_for(record: Record) -> Decimal:
        if ignore_savebacks and kind == "stock" and _is_saveback(record):
            return ZERO
        return _amount(record)

    def external_flows_on(as_of: str) -> tuple[Decimal, Decimal]:
        contributions = sum(
            (
                amount_for(record)
                for record in selected
                if _operation(record) in external_buys and _record_date(record) <= as_of
            ),
            ZERO,
        )
        withdrawals = sum(
            (
                amount_for(record)
                for record in selected
                if _operation(record) in external_sells and _record_date(record) <= as_of
            ),
            ZERO,
        )
        if kind == "fund" and selected_account not in {"", "all"}:
            contributions += sum(
                (
                    _amount(record)
                    for record in selected
                    if _operation(record) == _FUND_TRANSFER_IN and _record_date(record) <= as_of
                ),
                ZERO,
            )
            withdrawals += sum(
                (
                    _amount(record)
                    for record in selected
                    if _operation(record) == _FUND_TRANSFER_OUT and _record_date(record) <= as_of
                ),
                ZERO,
            )
        return contributions, withdrawals

    def transfer_cash_on(as_of: str) -> Decimal:
        if kind != "fund" or selected_account not in {"", "all"}:
            return ZERO
        outgoing = sum(
            (
                _amount(record)
                for record in selected
                if _operation(record) == _FUND_TRANSFER_OUT and _record_date(record) <= as_of
            ),
            ZERO,
        )
        incoming = sum(
            (
                _amount(record)
                for record in selected
                if _operation(record) == _FUND_TRANSFER_IN and _record_date(record) <= as_of
            ),
            ZERO,
        )
        # For the household series this bridges an unmatched transfer-out
        # until the corresponding transfer-in appears; account-scoped series
        # model each transfer as an account-level flow instead.
        return max(ZERO, outgoing - incoming)

    data: list[dict[str, Any]] = []
    for as_of in all_dates:
        total_value = transfer_cash_on(as_of)
        priced_asset = False
        for asset in sorted(usable_assets):
            # Market feeds omit weekends and can begin on different dates.
            # Use the latest known close, never a future quote, for each point.
            available_prices = {
                _text(value)[:10]: price
                for value, price in histories.get(asset, {}).items()
                if _text(value)[:10] <= as_of and price not in (None, "")
            }
            raw_price = available_prices.get(max(available_prices)) if available_prices else None
            if raw_price in (None, ""):
                continue
            priced_asset = True
            quantity = ZERO
            for record in selected:
                if _asset(record, kind) != asset or _record_date(record) > as_of:
                    continue
                operation = _operation(record)
                sign = (
                    Decimal("1")
                    if operation in buys
                    else Decimal("-1")
                    if operation in sells
                    else ZERO
                )
                if sign:
                    quantity += (
                        sign
                        * _quantity(record)
                        * _split_factor(asset, _record_date(record), as_of, grouped_splits)
                    )
            if quantity > ZERO:
                total_value += quantity * decimal(raw_price)
        contributions, withdrawals = external_flows_on(as_of)
        # ``invertido`` remains net contributed capital for Funds-compatible
        # consumers; realized proceeds live in P&L rather than disappearing
        # when this net basis reaches zero.
        invested = max(ZERO, contributions - withdrawals)
        # Total P&L includes proceeds that have left the portfolio, so a full
        # liquidation retains its realized gain/loss instead of disappearing.
        pnl = total_value + withdrawals - contributions
        if not priced_asset or (
            total_value <= ZERO and contributions <= ZERO and withdrawals <= ZERO
        ):
            continue
        # Returns are measured against gross contributed capital.  Using the
        # net post-withdrawal balance would turn a profitable/losing full sale
        # into an undefined or ±100% return.
        percentage_basis = contributions
        pnl_pct = (pnl / percentage_basis * Decimal("100")) if percentage_basis > ZERO else ZERO
        data.append(
            {
                "fecha": as_of,
                "valor": round(float(total_value), 2),
                "invertido": round(float(invested), 2),
                "pnl": round(float(pnl), 2),
                "pnl_pct": round(float(pnl_pct), 3),
            }
        )
    return data


# A concise alias is useful to callers that do not need to know the API's
# historical name for this calculation.
calculate_performance = calculate_investment_performance
