"""Pruebas directas del dominio, sin importar dependencias web ni pandas."""

import math
import unittest
from uuid import UUID

from finanzr.domain.account_performance import calculate_account_performance
from finanzr.domain.crypto import calculate_crypto_positions
from finanzr.domain.funds import calculate_fund_positions
from finanzr.domain.investments import monthly_pnl
from finanzr.domain.net_worth import current_total, monthly_history
from finanzr.domain.real_estate import live_capital, live_capital_for_month, new_capital
from finanzr.domain.stocks import apply_splits, calculate_stock_positions


class TestNetWorthDomain(unittest.TestCase):
    def test_current_total_accepts_plain_records(self):
        records = [
            {"fecha": "2026-01-31", "cuenta_id": "a", "saldo": "100.10"},
            {"fecha": "2026-02-28", "cuenta_id": "a", "saldo": "120.20"},
            {"fecha": "2026-01-31", "cuenta_id": "b", "saldo": "30.30"},
        ]

        self.assertEqual(current_total(records, "saldo"), 150.5)

    def test_monthly_history_uses_decimal_input_without_float_drift(self):
        result = monthly_history(
            savings=[
                {"fecha": "2026-01-31", "cuenta_id": 1, "saldo": "0.10", "aporte": "0.10"},
                {"fecha": "2026-02-28", "cuenta_id": 1, "saldo": "0.30", "aporte": "0.20"},
            ],
            investments=[
                {"fecha": "2026-01-31", "cuenta_id": 1, "valor": "0.20", "aporte": "0.20"},
            ],
            real_estate=[],
        )

        self.assertEqual(result[-1]["ahorro"], 0.3)
        self.assertEqual(result[-1]["ahorro_intereses"], 0.0)
        self.assertEqual(result[-1]["balances"], 0.2)
        self.assertEqual(result[-1]["balance_aportes"], 0.0)
        self.assertEqual(result[-1]["inversiones"], 0.2)
        self.assertEqual(result[-1]["total"], 0.5)

    def test_monthly_investment_pnl_uses_previous_value_and_contribution(self):
        history = [
            {"fecha": "2026-01-31", "cuenta_id": 1, "valor": "1000"},
            {"fecha": "2026-02-28", "cuenta_id": 2, "valor": "9999"},
        ]

        result = monthly_pnl(
            history,
            account_id=1,
            date="2026-02-28",
            value="1250",
            contribution="100",
            explicit_pnl=None,
        )

        self.assertEqual(result, 150.0)

    def test_monthly_investment_pnl_accepts_uuid_native_account_ids(self):
        account_id = UUID("11111111-1111-1111-1111-111111111111")
        history = [
            {
                "fecha": "2026-01-31",
                "cuenta_id": str(account_id),
                "valor": "1000",
            }
        ]

        result = monthly_pnl(
            history,
            account_id=account_id,
            date="2026-02-28",
            value="1250",
            contribution="100",
            explicit_pnl=None,
        )

        self.assertEqual(result, 150.0)


class TestRealEstateDomain(unittest.TestCase):
    def test_legacy_invertido_is_used_when_new_columns_are_missing(self):
        project = {"capital_inicial": math.nan, "invertido": "750.25"}

        self.assertEqual(live_capital(project), 750.25)
        self.assertEqual(new_capital(project), 750.25)

    def test_return_date_does_not_reduce_previous_months(self):
        project = {
            "fecha_inicio": "2026-01-10",
            "fecha_devolucion": "2026-03-15",
            "capital_inicial": "1000.00",
            "capital_devuelto": "400.00",
        }

        self.assertEqual(live_capital_for_month(project, "2026-02"), 1000.0)
        self.assertEqual(live_capital_for_month(project, "2026-03"), 600.0)

    def test_multiple_returns_reduce_capital_on_each_effective_month(self):
        project = {
            "fecha_inicio": "2025-09-01",
            "capital_inicial": "1500.00",
            "capital_devuelto": "1500.00",
            "movimientos": [
                {
                    "tipo": "capital_return",
                    "fecha": "2026-06-22",
                    "importe": "970.96",
                },
                {"tipo": "profit", "fecha": "2026-06-22", "importe": "72.18"},
                {
                    "tipo": "capital_return",
                    "fecha": "2026-07-14",
                    "importe": "529.04",
                },
            ],
        }

        self.assertEqual(live_capital_for_month(project, "2026-05"), 1500.0)
        self.assertEqual(live_capital_for_month(project, "2026-06"), 529.04)
        self.assertEqual(live_capital_for_month(project, "2026-07"), 0.0)


class TestPositionDomain(unittest.TestCase):
    def test_stock_position_combines_split_and_proportional_sale(self):
        orders = [
            {
                "fecha_operacion": "2025-06-01",
                "isin": "TEST",
                "nombre_activo": "Demo",
                "titulos": "10",
                "precio_compra": "100",
                "importe_neto": "1000",
                "tipo_operacion": "Compra",
            },
            {
                "fecha_operacion": "2025-06-20",
                "isin": "TEST",
                "nombre_activo": "Demo",
                "titulos": "5",
                "precio_compra": "70",
                "importe_neto": "350",
                "tipo_operacion": "Venta",
            },
        ]

        result = calculate_stock_positions(
            orders, {"TEST": "60"}, [{"isin": "TEST", "fecha": "2025-06-10", "ratio": "2"}]
        )[0]

        self.assertEqual(result["titulos"], 15.0)
        self.assertEqual(result["coste_total"], 750.0)
        self.assertEqual(result["pnl"], 150.0)
        self.assertEqual(result["pnl_realizada"], 100.0)

    def test_splits_return_new_records_and_ignore_invalid_ratios(self):
        original = [
            {
                "fecha_operacion": "2025-01-01",
                "isin": "TEST",
                "titulos": 1,
                "precio_compra": 90,
                "importe_neto": 90,
            }
        ]

        adjusted = apply_splits(
            original,
            [
                {"isin": "TEST", "fecha": "2025-02-01", "ratio": "invalid"},
                {"isin": "TEST", "fecha": "2025-02-01", "ratio": 3},
            ],
        )

        self.assertEqual(original[0]["titulos"], 1)
        self.assertEqual(adjusted[0]["titulos"], 3.0)
        self.assertEqual(adjusted[0]["precio_compra"], 30.0)

    def test_crypto_positions_are_sorted_by_asset_id(self):
        orders = [
            {
                "symbol": "ETH",
                "nombre_activo": "Ethereum",
                "fecha_operacion": "2026-01-01",
                "titulos": 1,
                "importe_neto": 100,
                "tipo_operacion": "Compra",
            },
            {
                "symbol": "BTC",
                "nombre_activo": "Bitcoin",
                "fecha_operacion": "2026-01-01",
                "titulos": 1,
                "importe_neto": 200,
                "tipo_operacion": "Compra",
            },
        ]

        result = calculate_crypto_positions(orders, {"BTC": 250, "ETH": 120})

        self.assertEqual([position["symbol"] for position in result], ["BTC", "ETH"])

    def test_fund_position_excludes_transfer_as_new_money(self):
        orders = [
            {
                "isin": "FUND",
                "cuenta_id": 1,
                "tipo_operacion": "SUSCRIPCION",
                "titulos": "10",
                "importe_neto": "100",
            },
            {
                "isin": "FUND",
                "cuenta_id": 1,
                "tipo_operacion": "REEMBOLSO",
                "titulos": "4",
                "importe_neto": "44",
            },
            {
                "isin": "OTHER",
                "cuenta_id": 2,
                "tipo_operacion": "SUSCRIPCION",
                "titulos": "1",
                "importe_neto": "10",
            },
        ]

        result = calculate_fund_positions(
            orders,
            {"FUND": {"nombre": "Fondo", "tipo": "RV", "subtipo": "Global"}},
            {"FUND": "12"},
            account_id=1,
        )

        self.assertEqual(
            result,
            [
                {
                    "isin": "FUND",
                    "nombre": "Fondo",
                    "tipo": "RV",
                    "subtipo": "Global",
                    "total_invertido": 60.0,
                    "participaciones": 6.0,
                    "precio_medio": 10.0,
                    "precio_actual": 12.0,
                    "valor_actual": 72.0,
                    "pnl": 12.0,
                    "pnl_pct": 0.2,
                    "moneda": "EUR",
                }
            ],
        )

    def test_account_performance_does_not_keep_transfer_as_synthetic_cash(self):
        orders = [
            {
                "cuenta_id": 1,
                "isin": "A",
                "fecha_operacion": "2026-01-01",
                "tipo_operacion": "SUSCRIPCION",
                "titulos": "10",
                "importe_neto": "100",
            },
            {
                "cuenta_id": 1,
                "isin": "A",
                "fecha_operacion": "2026-01-02",
                "tipo_operacion": "REEMB.POR TRASPASO I",
                "titulos": "10",
                "importe_neto": "120",
            },
            {
                "cuenta_id": 1,
                "isin": "B",
                "fecha_operacion": "2026-01-03",
                "tipo_operacion": "SUSCR.POR TRASPASO I",
                "titulos": "12",
                "importe_neto": "120",
            },
        ]
        prices = {
            "A": {"2026-01-01": "10", "2026-01-02": "12", "2026-01-03": "12"},
            "B": {"2026-01-01": "10", "2026-01-02": "10", "2026-01-03": "10"},
        }

        result = calculate_account_performance(orders, prices, account_id=1)

        self.assertEqual(
            result[1],
            {
                "fecha": "2026-01-02",
                "valor": 0.0,
                "invertido": 0.0,
                "pnl": 20.0,
                "pnl_pct": 20.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
