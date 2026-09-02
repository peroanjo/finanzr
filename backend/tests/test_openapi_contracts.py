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
        assert account_schema["required"] == ["name"]
        assert {"bank", "currency", "type"} <= set(account_schema["properties"])
        assert not {"nombre", "banco", "moneda", "tipo"} & set(account_schema["properties"])
        assert "required" not in self._request_schema(
            document, "/api/savings/accounts/{account_id}", "put"
        )
        account_detail_parameter = document["paths"]["/api/savings/accounts/{account_id}"]["put"][
            "parameters"
        ][0]
        assert account_detail_parameter["name"] == "account_id"
        assert account_detail_parameter["schema"] == {"type": "string", "format": "uuid"}
        account_response = document["paths"]["/api/savings/accounts"]["get"]["responses"]["200"]
        account_response_schema = self._resolve(
            document, account_response["content"]["application/json"]["schema"]["items"]
        )
        assert set(account_response_schema["properties"]) == {
            "id",
            "name",
            "bank",
            "type",
            "currency",
        }

        savings_snapshot = self._request_schema(document, "/api/savings/history", "post")
        assert set(savings_snapshot["required"]) == {"account_id", "date", "balance"}
        assert {"contribution", "interest"} <= set(savings_snapshot["properties"])
        assert not {"cuenta_id", "fecha", "saldo"} & set(savings_snapshot["properties"])
        snapshot_response = document["paths"]["/api/savings/history"]["get"]["responses"]["200"]
        snapshot_response_schema = self._resolve(
            document, snapshot_response["content"]["application/json"]["schema"]["items"]
        )
        assert {
            "id",
            "account_id",
            "date",
            "balance",
            "balance_original",
            "contribution",
            "contribution_original",
            "interest",
            "interest_original",
            "currency",
            "base_currency",
            "exchange_rate",
            "exchange_rate_date",
            "exchange_rate_source",
        } == set(snapshot_response_schema["properties"])
        history_parameters = document["paths"]["/api/savings/history"]["get"]["parameters"]
        account_filter_parameter = next(
            parameter for parameter in history_parameters if parameter["name"] == "account_id"
        )
        assert account_filter_parameter["in"] == "query"
        assert account_filter_parameter["schema"] == {"type": "string", "format": "uuid"}
        assert "parameters" not in document["paths"]["/api/savings/history"]["post"]
        delete_parameters = document["paths"]["/api/savings/history/{account_id}/{value_date}"][
            "delete"
        ]["parameters"]
        value_date_parameter = next(
            parameter for parameter in delete_parameters if parameter["name"] == "value_date"
        )
        assert value_date_parameter["schema"] == {"type": "string", "format": "date"}
        investment_account = self._request_schema(document, "/api/investments/accounts", "post")
        assert investment_account["required"] == ["name"]
        assert {"platform", "currency", "type"} <= set(investment_account["properties"])
        assert investment_account["properties"]["name"]["maxLength"] == 160
        assert investment_account["properties"]["platform"]["maxLength"] == 160
        assert investment_account["properties"]["type"]["maxLength"] == 80
        assert investment_account["properties"]["currency"]["maxLength"] == 3
        assert not {"nombre", "plataforma", "moneda", "tipo"} & set(
            investment_account["properties"]
        )
        assert "required" not in self._request_schema(
            document, "/api/investments/accounts/{account_id}", "put"
        )
        investment_account_parameter = document["paths"]["/api/investments/accounts/{account_id}"][
            "put"
        ]["parameters"][0]
        assert investment_account_parameter["name"] == "account_id"
        assert investment_account_parameter["schema"] == {"type": "string", "format": "uuid"}
        investment_account_response = document["paths"]["/api/investments/accounts"]["get"][
            "responses"
        ]["200"]
        investment_account_response_schema = self._resolve(
            document,
            investment_account_response["content"]["application/json"]["schema"]["items"],
        )
        assert set(investment_account_response_schema["properties"]) == {
            "id",
            "name",
            "platform",
            "type",
            "currency",
        }

        investment_snapshot = self._request_schema(document, "/api/investments/history", "post")
        assert set(investment_snapshot["required"]) == {"account_id", "date", "value"}
        assert {"contribution", "interest"} <= set(investment_snapshot["properties"])
        assert not {"cuenta_id", "fecha", "valor", "aporte", "intereses"} & set(
            investment_snapshot["properties"]
        )
        assert investment_snapshot["properties"]["account_id"] == {
            "type": "string",
            "format": "uuid",
        }
        assert investment_snapshot["properties"]["date"] == {
            "type": "string",
            "format": "date",
        }
        investment_snapshot_response = document["paths"]["/api/investments/history"]["get"][
            "responses"
        ]["200"]
        investment_snapshot_response_schema = self._resolve(
            document,
            investment_snapshot_response["content"]["application/json"]["schema"]["items"],
        )
        assert {
            "id",
            "account_id",
            "date",
            "value",
            "value_original",
            "contribution",
            "contribution_original",
            "interest",
            "interest_original",
            "currency",
            "base_currency",
            "exchange_rate",
            "exchange_rate_date",
            "exchange_rate_source",
        } == set(investment_snapshot_response_schema["properties"])
        investment_history_parameters = document["paths"]["/api/investments/history"]["get"][
            "parameters"
        ]
        investment_account_filter = next(
            parameter
            for parameter in investment_history_parameters
            if parameter["name"] == "account_id"
        )
        assert investment_account_filter["in"] == "query"
        assert investment_account_filter["schema"] == {"type": "string", "format": "uuid"}
        assert "parameters" not in document["paths"]["/api/investments/history"]["post"]
        investment_delete_parameters = document["paths"][
            "/api/investments/history/{account_id}/{value_date}"
        ]["delete"]["parameters"]
        investment_value_date = next(
            parameter
            for parameter in investment_delete_parameters
            if parameter["name"] == "value_date"
        )
        assert investment_value_date["schema"] == {"type": "string", "format": "date"}

        portfolio = self._request_schema(document, "/api/portfolio", "post")
        assert set(portfolio["required"]) == {"name", "asset_class", "value"}
        assert set(portfolio["properties"]) == {
            "name",
            "asset_class",
            "subtype",
            "platform",
            "value",
        }
        assert portfolio["properties"]["name"]["maxLength"] == 200
        assert portfolio["properties"]["asset_class"]["maxLength"] == 80
        assert portfolio["properties"]["subtype"]["maxLength"] == 120
        assert portfolio["properties"]["platform"]["maxLength"] == 160
        assert "required" not in self._request_schema(document, "/api/portfolio/{asset_id}", "put")
        portfolio_parameter = document["paths"]["/api/portfolio/{asset_id}"]["put"]["parameters"][0]
        assert portfolio_parameter["name"] == "asset_id"
        assert portfolio_parameter["schema"] == {"type": "string", "format": "uuid"}
        portfolio_response = document["paths"]["/api/portfolio"]["get"]["responses"]["200"]
        portfolio_response_schema = self._resolve(
            document, portfolio_response["content"]["application/json"]["schema"]["items"]
        )
        assert set(portfolio_response_schema["properties"]) == {
            "id",
            "name",
            "asset_class",
            "subtype",
            "platform",
            "value",
            "currency",
        }
        assert portfolio_response_schema["properties"]["id"] == {
            "type": "string",
            "format": "uuid",
        }

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
            "account_id",
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
        update_order = self._request_schema(document, "/api/orders/{external_id}", "put")
        assert "original_account_id" in update_order["required"]
        delete_order_parameters = document["paths"]["/api/orders/{external_id}"]["delete"][
            "parameters"
        ]
        delete_account = next(
            parameter for parameter in delete_order_parameters if parameter["name"] == "account_id"
        )
        assert delete_account["required"] is True
        assert delete_account["schema"]["format"] == "uuid"

        traded_account = self._request_schema(document, "/api/fund-accounts", "post")
        assert set(traded_account["properties"]) == {
            "name",
            "platform",
            "type",
            "currency",
            "importer_slug",
        }
        assert traded_account["required"] == ["name"]
        traded_response = document["paths"]["/api/fund-accounts"]["get"]["responses"]["200"]
        traded_response_schema = self._resolve(
            document, traded_response["content"]["application/json"]["schema"]["items"]
        )
        assert set(traded_response_schema["properties"]) == {
            "id",
            "name",
            "platform",
            "type",
            "currency",
            "importer_slug",
            "importer_name",
        }

        portfolio_analysis = document["paths"]["/api/portfolio-analysis"]["get"]["responses"]["200"]
        portfolio_analysis_schema = self._resolve(
            document, portfolio_analysis["content"]["application/json"]["schema"]
        )
        assert portfolio_analysis_schema["type"] == "object"
        assert set(portfolio_analysis_schema["properties"]) == {"total", "items"}
        assert portfolio_analysis_schema["properties"]["items"]["type"] == "array"

        performance_parameters = document["paths"]["/api/investment-performance/{kind}"]["get"][
            "parameters"
        ]
        performance_account = next(
            parameter for parameter in performance_parameters if parameter["name"] == "account_id"
        )
        assert performance_account["schema"] == {"type": "string"}
        assert "UUID" in performance_account["description"]

        path_upload_schema = self._resolve(
            document,
            document["paths"]["/api/account-imports/{kind}/{account_id}"]["post"]["requestBody"][
                "content"
            ]["multipart/form-data"]["schema"],
        )
        assert set(path_upload_schema["properties"]) == {"file"}
        assert path_upload_schema["required"] == ["file"]
        direct_upload_schema = self._resolve(
            document,
            document["paths"]["/api/fund-orders/upload"]["post"]["requestBody"]["content"][
                "multipart/form-data"
            ]["schema"],
        )
        assert set(direct_upload_schema["properties"]) == {"file", "account_id"}
        assert set(direct_upload_schema["required"]) == {"file", "account_id"}

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
        upload = document["paths"]["/api/account-imports/{kind}/{account_id}"]["post"]
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
