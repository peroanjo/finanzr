from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from django.core.management import call_command
from django.test import SimpleTestCase


class OpenApiMutationContractTests(SimpleTestCase):
    def test_financial_mutations_have_real_request_shapes(self) -> None:
        output = Path(self._temp_schema())
        try:
            document = yaml.safe_load(output.read_text())
        finally:
            output.unlink(missing_ok=True)

        stock = document["paths"]["/api/stocks"]["post"]
        stock_schema = self._resolve(
            document, stock["requestBody"]["content"]["application/json"]["schema"]
        )
        assert {"isin", "ticker", "nombre"} <= set(stock_schema["required"])
        stock_detail = document["paths"]["/api/stocks/{asset_id}"]["put"]
        stock_detail_schema = self._resolve(
            document, stock_detail["requestBody"]["content"]["application/json"]["schema"]
        )
        assert "ticker" in stock_detail_schema["properties"]
        assert "required" not in stock_detail_schema

        account_schema = self._request_schema(document, "/api/savings/accounts", "post")
        assert account_schema["required"] == ["nombre"]
        assert {"banco", "importer_slug", "moneda", "plataforma", "tipo"} <= set(
            account_schema["properties"]
        )
        assert "required" not in self._request_schema(
            document, "/api/savings/accounts/{legacy_id}", "put"
        )

        savings_snapshot = self._request_schema(document, "/api/savings/history", "post")
        assert set(savings_snapshot["required"]) == {"cuenta_id", "fecha", "saldo"}
        investment_snapshot = self._request_schema(document, "/api/investments/history", "post")
        assert set(investment_snapshot["required"]) == {"cuenta_id", "fecha", "valor"}
        assert {"aporte", "intereses"} <= set(investment_snapshot["properties"])

        calculator = document["paths"]["/api/calculator"]["post"]
        calculator_properties = self._resolve(
            document, calculator["requestBody"]["content"]["application/json"]["schema"]
        )["properties"]
        assert {"nombre", "tipo_renta", "porcentaje", "aportar"} <= set(calculator_properties)
        assert self._request_schema(document, "/api/calculator", "post")["required"] == ["nombre"]
        assert "required" not in self._request_schema(
            document, "/api/calculator/{legacy_id}", "put"
        )

        budget = document["paths"]["/api/budget"]["put"]
        budget_schema = self._resolve(
            document, budget["requestBody"]["content"]["application/json"]["schema"]
        )
        assert budget_schema["type"] == "array"
        budget_item = self._resolve(document, budget_schema["items"])
        assert {"categoria", "cantidad", "tipo"} <= set(budget_item["properties"])

        order = document["paths"]["/api/orders"]["post"]
        order_properties = self._resolve(
            document, order["requestBody"]["content"]["application/json"]["schema"]
        )["properties"]
        assert {
            "fecha_operacion",
            "tipo_operacion",
            "titulos",
            "precio_neto",
            "importe_neto",
        } <= set(order_properties)
        assert set(self._request_schema(document, "/api/orders", "post")["required"]) == {
            "cuenta_id",
            "fecha_operacion",
            "importe_neto",
            "isin",
            "precio_neto",
            "tipo_operacion",
            "titulos",
        }
        assert (
            "precio_compra"
            in self._request_schema(document, "/api/stock-orders", "post")["required"]
        )
        assert "symbol" in self._request_schema(document, "/api/crypto-orders", "post")["required"]
        assert (
            "fecha_operacion"
            in self._resolve(
                document,
                document["paths"]["/api/orders/{external_id}"]["put"]["requestBody"]["content"][
                    "application/json"
                ]["schema"],
            )["properties"]
        )

        fx = document["paths"]["/api/fx-rates"]["post"]
        fx_properties = self._resolve(
            document, fx["requestBody"]["content"]["application/json"]["schema"]
        )["properties"]
        assert {"quote_currency", "base_currency", "rate_date", "rate"} <= set(fx_properties)
        assert self._request_schema(document, "/api/fx-rates", "post")["required"] == ["rate"]
        assert (
            "rate"
            in self._resolve(
                document,
                document["paths"]["/api/fx-rates/{rate_id}"]["put"]["requestBody"]["content"][
                    "application/json"
                ]["schema"],
            )["properties"]
        )

        price = document["paths"]["/api/stock-prices/{asset_id}"]["put"]
        price_properties = self._resolve(
            document, price["requestBody"]["content"]["application/json"]["schema"]
        )["properties"]
        assert {"precio", "moneda"} <= set(price_properties)
        assert "200" in price["responses"]

        delete_account = document["paths"]["/api/account"]["delete"]
        delete_schema = self._resolve(
            document,
            delete_account["requestBody"]["content"]["application/json"]["schema"],
        )
        assert delete_schema["required"] == ["password"]
        assert set(delete_account["responses"]) == {"204", "400", "403", "409"}
        upload = document["paths"]["/api/account-imports/{kind}/{legacy_id}"]["post"]
        upload_schema = self._resolve(
            document, upload["requestBody"]["content"]["multipart/form-data"]["schema"]
        )
        assert "file" in upload_schema["required"]
        assert "200" not in document["paths"]["/api/stocks"]["post"]["responses"]
        assert "200" in document["paths"]["/api/fx-rates"]["post"]["responses"]
        assert "201" not in document["paths"]["/api/stock-splits"]["post"]["responses"]

    @staticmethod
    def _temp_schema() -> str:
        import tempfile

        handle = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
        handle.close()
        call_command("spectacular", file=handle.name, validate=True, fail_on_warn=True, verbosity=0)
        return handle.name

    @staticmethod
    def _resolve(document: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        reference = schema.get("$ref")
        if not reference:
            return schema
        name = reference.rsplit("/", 1)[-1]
        return cast(dict[str, Any], document["components"]["schemas"][name])

    @classmethod
    def _request_schema(cls, document: dict[str, Any], path: str, method: str) -> dict[str, Any]:
        schema = document["paths"][path][method]["requestBody"]["content"]["application/json"][
            "schema"
        ]
        return cls._resolve(document, schema)
