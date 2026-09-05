from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.account_queries import (
    kind_accounts,
)
from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instruments
from apps.api.market_data_projection import (
    instrument_calculation_row,
)
from apps.api.market_queries import (
    calculation_price_rows,
)
from apps.api.portfolio_queries import _summary_manual_assets
from apps.api.position_projection import native_position_rows
from apps.api.projection import identifier, number, provider_name
from apps.api.real_estate_queries import real_estate_records
from apps.api.transaction_queries import (
    selected_traded_account,
    transaction_calculation_rows,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
)
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    StockSplit,
)
from finanzr.domain.crypto import calculate_crypto_positions
from finanzr.domain.funds import calculate_fund_positions
from finanzr.domain.real_estate import live_capital
from finanzr.domain.stocks import calculate_stock_positions


def analyzed_positions(
    request: Request,
    kind: str,
    rows: list[dict[str, Any]],
    *,
    account_filter: int | str | UUID | None = None,
) -> list[dict[str, Any]]:
    prices = calculation_price_rows(request, kind)
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
    try:
        selected_account = selected_traded_account(request, kind)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    account_filter = selected_account.id if selected_account is not None else None
    rows = transaction_calculation_rows(request, kind, selected_account)
    try:
        positions = analyzed_positions(request, kind, rows, account_filter=account_filter)
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=502)
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
        all_rows = transaction_calculation_rows(request, kind)
        identity_key = "symbol" if kind == "crypto" else "isin"
        for account in kind_accounts(request, account_kind):
            account_uuid = str(account.id)
            account_rows = [row for row in all_rows if str(row["cuenta_id"]) == account_uuid]
            if not account_rows:
                continue
            try:
                positions = analyzed_positions(
                    request,
                    kind,
                    account_rows,
                    account_filter=account.id if kind == "fund" else None,
                )
            except CurrencyConversionError as exc:
                return Response({"error": str(exc)}, status=502)
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
