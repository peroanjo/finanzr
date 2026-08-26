from __future__ import annotations

import csv
from pathlib import Path

from apps.imports.legacy import FILE_SCHEMAS

ROWS: dict[str, list[dict[str, object]]] = {
    "savings_accounts.csv": [
        {"id": 1, "nombre": "Synthetic savings", "banco": "Demo Bank", "tipo": "Ahorro"}
    ],
    "savings_history.csv": [
        {"fecha": "2026-01-31", "cuenta_id": 1, "saldo": 1000, "aporte": 1000, "intereses": 0}
    ],
    "investment_accounts.csv": [
        {"id": 1, "nombre": "Synthetic investment", "plataforma": "Demo Broker", "tipo": "Manual"}
    ],
    "investment_history.csv": [
        {"fecha": "2026-01-31", "cuenta_id": 1, "valor": 500, "aporte": 500, "intereses": 0}
    ],
    "fund_accounts.csv": [
        {"id": 1, "nombre": "Synthetic funds", "tipo": "Renta Variable", "plataforma": "MyInvestor"}
    ],
    "funds.csv": [
        {
            "isin": "SYNTH-FUND-001",
            "nombre": "Synthetic Fund",
            "tipo": "Renta variable",
            "subtipo": "Global",
            "ticker": "SYNTH-FUND-EUR",
        }
    ],
    "orders.csv": [
        {
            "operacion_id": "SYNTH-FUND-BUY-001",
            "fecha_operacion": "2026-01-15",
            "fecha_liquidacion": "2026-01-17",
            "mercado": "DEMO",
            "tipo_operacion": "SUSCRIPCION",
            "isin": "SYNTH-FUND-001",
            "nombre_fondo": "Synthetic Fund",
            "titulos": 10,
            "divisa": "EUR",
            "precio_neto": 10,
            "importe_neto": 100,
            "cuenta_id": 1,
        }
    ],
    "fund_prices.csv": [{"isin": "SYNTH-FUND-001", "precio": 11, "updated": "2026-01-31"}],
    "stock_accounts.csv": [
        {"id": 1, "nombre": "Synthetic stocks", "tipo": "Broker", "plataforma": "Trade Republic"}
    ],
    "stocks.csv": [{"isin": "SYNTH-STOCK-001", "ticker": "", "nombre": "Synthetic Stock"}],
    "stock_orders.csv": [
        {
            "operacion_id": "SYNTH-STOCK-BUY-001",
            "fecha_operacion": "2026-01-15",
            "isin": "SYNTH-STOCK-001",
            "nombre_activo": "Synthetic Stock",
            "titulos": 2,
            "precio_compra": 50,
            "importe_neto": 100,
            "comision": 0,
            "cuenta_id": 1,
            "tipo_operacion": "Compra",
            "es_saveback": "False",
        }
    ],
    "stock_prices.csv": [
        {
            "isin": "SYNTH-STOCK-001",
            "fecha": "2026-01-31",
            "precio": 55,
            "updated": "2026-01-31",
            "moneda": "EUR",
            "precio_orig": 55,
        }
    ],
    "stock_splits.csv": [
        {
            "isin": "SYNTH-STOCK-001",
            "fecha": "2025-01-01",
            "ratio": 2,
            "fuente": "Synthetic fixture",
        }
    ],
    "crypto_accounts.csv": [{"id": 1, "nombre": "Synthetic crypto", "plataforma": "KrakenPro"}],
    "cryptos.csv": [{"symbol": "BTC", "ticker": "BTC-EUR", "nombre": "Synthetic Bitcoin"}],
    "crypto_orders.csv": [
        {
            "operacion_id": "SYNTH-CRYPTO-BUY-001",
            "fecha_operacion": "2026-01-15",
            "symbol": "BTC",
            "nombre_activo": "Synthetic Bitcoin",
            "titulos": 5,
            "precio_compra": 20,
            "importe_neto": 100,
            "comision": 0,
            "cuenta_id": 1,
            "tipo_operacion": "Compra",
        }
    ],
    "crypto_prices.csv": [
        {"moneda": "EUR", "precio_orig": 22, "symbol": "BTC", "precio": 22, "updated": "2026-01-31"}
    ],
    "real_estate.csv": [
        {
            "id": 1,
            "nombre": "Synthetic project",
            "plataforma": "Demo Platform",
            "estado": "Activo",
            "capital_inicial": 1000,
            "capital_devuelto": 0,
            "beneficio_obtenido": 0,
            "beneficio_estimado": "",
            "fecha_inicio": "2026-01-01",
            "fecha_vencimiento": "2027-01-01",
            "tir": 8,
            "meses": 12,
            "origen": "Ahorro",
            "fecha_devolucion": "",
            "capital_nuevo": 1000,
        }
    ],
    "real_estate_movements.csv": [],
    "portfolio_items.csv": [
        {
            "id": 1,
            "nombre": "Synthetic cash",
            "tipo_renta": "Efectivo",
            "subtipo": "Demo",
            "plataforma": "Manual",
            "efectivo": 100,
        }
    ],
    "budget.csv": [{"categoria": "Synthetic needs", "cantidad": 100, "tipo": "Necesidad"}],
    "calculadora_instrumentos.csv": [
        {
            "id": 1,
            "nombre": "Synthetic allocation",
            "plataforma": "Manual",
            "tipo_renta": "Variable",
            "subtipo": "Global",
            "porcentaje": 1,
            "aportar": "True",
        }
    ],
}


def write_legacy_fixture(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for filename, schema in FILE_SCHEMAS.items():
        fieldnames = sorted(schema)
        with (root / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in ROWS.get(filename, []):
                writer.writerow({field: row.get(field, "") for field in fieldnames})
    return root
