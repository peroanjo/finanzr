from typing import Any

import pytest
from apps.market_data import yahoo


@pytest.mark.parametrize(
    ("requested", "provider_range"),
    [("1m", "1mo"), ("3m", "3mo"), ("6m", "6mo"), ("1y", "1y"), ("max", "max")],
)
def test_yahoo_chart_maps_dashboard_ranges(
    monkeypatch: pytest.MonkeyPatch, requested: str, provider_range: str
) -> None:
    captured: dict[str, Any] = {}

    def fake_get(host: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        captured.update(params)
        return {
            "chart": {
                "result": [
                    {
                        "meta": {"currency": "EUR"},
                        "timestamp": [1_700_000_000],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10],
                                    "high": [12],
                                    "low": [9],
                                    "close": [11],
                                }
                            ]
                        },
                    }
                ]
            }
        }

    monkeypatch.setattr(yahoo, "_get", fake_get)

    _, points = yahoo.chart("BTC-EUR", range_name=requested)

    assert captured["range"] == provider_range
    assert points[0]["close"] == 11
