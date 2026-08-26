"""Pruebas directas de importadores sin dependencias web ni pandas."""

import math
import unittest

from finanzr.importers import (
    BaseImporter,
    ImportContext,
    ImporterError,
    ImportResult,
    InputKind,
    importers,
)
from finanzr.importers.funds import parse_fund_extract
from finanzr.importers.kraken import parse_kraken_trades
from finanzr.importers.registry import ImporterRegistry
from finanzr.importers.trade_republic import parse_trade_republic


class TestKrakenImporter(unittest.TestCase):
    def test_maps_fees_symbols_and_unsupported_pairs(self):
        orders, skipped = parse_kraken_trades(
            [
                {
                    "txid": "1",
                    "pair": "XBT/EUR",
                    "time": "2026-01-01 10:00",
                    "type": "buy",
                    "price": 50000,
                    "cost": 500,
                    "fee": 2,
                    "vol": 0.01,
                },
                {
                    "txid": "2",
                    "pair": "ETH/USD",
                    "time": "2026-01-02 10:00",
                    "type": "buy",
                    "price": 2000,
                    "cost": 200,
                    "fee": 1,
                    "vol": 0.1,
                },
            ],
            account_id=4,
        )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["symbol"], "BTC")
        self.assertEqual(orders[0]["importe_neto"], 502.0)
        self.assertEqual(orders[0]["cuenta_id"], 4)
        self.assertEqual(skipped, {"ETH/USD"})


class TestFundImporter(unittest.TestCase):
    def test_parses_html_table_and_removes_markup(self):
        html = """
        <table><tr>
          <td>2026-01-02</td><td>2026-01-04</td><td>op-1</td><td>Mercado</td>
          <td>SUSCRIPCION</td><td>ES0000000001</td><td>Fondo &amp; Demo</td>
          <td>12,5</td><td>EUR</td><td>10,25</td><td>128,13</td>
        </tr></table>
        """

        orders = parse_fund_extract(html, account_id=2)

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["nombre_fondo"], "Fondo & Demo")
        self.assertEqual(orders[0]["titulos"], 12.5)


class TestTradeRepublicImporter(unittest.TestCase):
    def test_detects_one_saveback_and_keeps_regular_plan_separate(self):
        rows = [
            {
                "transaction_id": "benefit",
                "date": "2026-01-01",
                "type": "BENEFITS_SAVEBACK",
                "category": "BENEFITS",
                "asset_class": "STOCK",
                "symbol": math.nan,
                "name": math.nan,
                "shares": math.nan,
                "amount": -25,
                "fee": 0,
                "price": 0,
                "tax": 0,
                "description": "Saveback",
            },
            {
                "transaction_id": "buy-1",
                "date": "2026-01-02",
                "type": "TRADE",
                "category": "TRADING",
                "asset_class": "STOCK",
                "symbol": "TEST",
                "name": "Demo",
                "shares": 2,
                "amount": -25,
                "fee": 0,
                "price": 12.5,
                "tax": 0,
                "description": "Savings plan execution",
            },
            {
                "transaction_id": "buy-2",
                "date": "2026-02-02",
                "type": "TRADE",
                "category": "TRADING",
                "asset_class": "STOCK",
                "symbol": "TEST",
                "name": "Demo",
                "shares": 2,
                "amount": -25,
                "fee": 0,
                "price": 12.5,
                "tax": 0,
                "description": "Savings plan execution",
            },
        ]

        orders = parse_trade_republic(rows, account_id=3)

        self.assertEqual(len(orders), 2)
        self.assertTrue(orders[0]["es_saveback"])
        self.assertFalse(orders[1]["es_saveback"])
        self.assertEqual(orders[0]["cuenta_id"], 3)


class TestImporterContract(unittest.TestCase):
    def test_all_builtin_importers_expose_common_metadata(self):
        self.assertEqual(
            [item["slug"] for item in importers.catalog()],
            ["fund_broker", "kraken_spot", "trade_republic"],
        )
        for importer in importers.all():
            with self.subTest(importer=importer.slug):
                self.assertIsInstance(importer, BaseImporter)
                self.assertTrue(importer.display_name)
                self.assertTrue(importer.target)
                self.assertIsInstance(importer.input_kind, InputKind)
                self.assertTrue(importer.accepted_extensions)
                self.assertTrue(importer.description)
                self.assertTrue(importer.source_instructions)
                self.assertTrue(importer.formats)
                self.assertTrue(importer.fields)
                self.assertEqual(
                    importer.required_fields,
                    frozenset(field.name for field in importer.fields if field.required),
                )

        catalog = importers.catalog()
        self.assertEqual(catalog[1]["target_label"], "Crypto")
        self.assertEqual(catalog[1]["formats"][0]["extension"], ".csv")
        self.assertIn("txid", [field["name"] for field in catalog[1]["fields"]])
        self.assertIn(
            "Investments → Funds → Operations and Queries",
            catalog[0]["source_instructions"],
        )
        self.assertIn(
            "Investments → Funds → Operations and Queries",
            importers.get("fund_broker").source_instructions,
        )

    def test_record_importers_validate_required_columns(self):
        with self.assertRaisesRegex(ImporterError, "Required columns are missing"):
            importers.parse("kraken_spot", [{"txid": "incompleta"}], ImportContext(account_id=1))

    def test_every_parser_returns_the_same_result_type(self):
        fund_result = importers.parse(
            "fund_broker", "cabecera no reconocida", ImportContext(account_id=1)
        )
        kraken_result = importers.parse("kraken_spot", [], ImportContext(account_id=1))
        tr_result = importers.parse("trade_republic", [], ImportContext(account_id=1))

        for result in (fund_result, kraken_result, tr_result):
            self.assertIsInstance(result, ImportResult)
            self.assertIsInstance(result.records, list)
            self.assertIsInstance(result.issues, list)
            self.assertIsInstance(result.metadata, dict)

    def test_registry_rejects_duplicate_slugs(self):
        registry = ImporterRegistry()
        parser = importers.get("fund_broker")
        registry.register(parser)

        with self.assertRaisesRegex(ValueError, "Duplicate importer"):
            registry.register(parser)

    def test_registry_rejects_an_importer_without_public_contract(self):
        class UndocumentedImporter(BaseImporter):
            slug = "undocumented"
            display_name = "Sin documentar"
            target = "test"
            target_label = "Pruebas"
            description = ""
            source_instructions = "Exporta un archivo"
            input_kind = InputKind.RECORDS

            def _parse(self, source, context):
                return ImportResult()

        with self.assertRaisesRegex(
            ValueError, "Every importer requires a public identity and description"
        ):
            ImporterRegistry().register(UndocumentedImporter())


if __name__ == "__main__":
    unittest.main()
