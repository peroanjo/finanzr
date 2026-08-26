from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.utils.translation import gettext as _


class MarketDataError(RuntimeError):
    pass


def _get(host: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://{host}{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Finanzr/0.1"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed HTTPS hosts
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return payload
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        raise MarketDataError(_("The market data provider is unavailable")) from exc


def search(isin: str) -> dict[str, str]:
    payload = _get(
        "query2.finance.yahoo.com",
        "/v1/finance/search",
        {"q": isin, "quotesCount": 3, "newsCount": 0},
    )
    quotes = payload.get("quotes", [])
    if not quotes:
        raise MarketDataError(_("Instrument not found"))
    item = next((row for row in quotes if row.get("quoteType") == "MUTUALFUND"), quotes[0])
    return {"ticker": item["symbol"], "name": item.get("longname") or item.get("shortname", "")}


def chart(
    ticker: str,
    *,
    range_name: str = "1y",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    params: dict[str, Any] = {"interval": interval}
    if start and end:
        params["period1"] = int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp())
        params["period2"] = int(datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp()) + 86400
    else:
        params["range"] = {
            "1m": "1mo",
            "3m": "3mo",
            "6m": "6mo",
            "1y": "1y",
            "2y": "2y",
            "max": "max",
        }.get(range_name, "1y")
    payload = _get(
        "query1.finance.yahoo.com", f"/v8/finance/chart/{quote(ticker, safe='')}", params
    )
    try:
        result = payload["chart"]["result"][0]
        quote_data = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise MarketDataError(_("Unrecognized market data response")) from exc
    timestamps = result.get("timestamp", [])
    points = []
    for index, timestamp in enumerate(timestamps):
        close = quote_data.get("close", [None] * len(timestamps))[index]
        if close is None:
            continue
        point = {
            "fecha": datetime.fromtimestamp(timestamp, UTC).date().isoformat(),
            "precio": float(close),
        }
        for source, target in (
            ("open", "open"),
            ("high", "high"),
            ("low", "low"),
            ("close", "close"),
        ):
            values = quote_data.get(source, [])
            point[target] = (
                float(values[index])
                if index < len(values) and values[index] is not None
                else float(close)
            )
        points.append(point)
    return result.get("meta", {}), points


def quote_price(ticker: str) -> tuple[float, str]:
    meta, points = chart(ticker, range_name="3m")
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    if price is None and points:
        price = points[-1]["close"]
    if price is None:
        raise MarketDataError(_("Price unavailable"))
    return float(price), str(meta.get("currency") or "EUR")
