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
        assert set(stock_schema["required"]) == {"name", "identifiers"}
        assert {
            "name",
            "quote_currency",
            "identifiers",
            "asset_class",
            "subtype",
            "is_active",
        } == set(stock_schema["properties"])
        assert not {"isin", "ticker", "nombre", "moneda"} & set(stock_schema["properties"])
        stock_detail = document["paths"]["/api/stocks/{instrument_id}"]["put"]
        stock_detail_schema = self._resolve(
            document, stock_detail["requestBody"]["content"]["application/json"]["schema"]
        )
        assert "identifiers" in stock_detail_schema["properties"]
        assert not {"isin", "ticker", "nombre", "moneda"} & set(stock_detail_schema["properties"])
        assert "required" not in stock_detail_schema
        stock_detail_parameter = stock_detail["parameters"][0]
        assert stock_detail_parameter["name"] == "instrument_id"
        assert stock_detail_parameter["schema"] == {"type": "string", "format": "uuid"}
        assert "post" not in document["paths"]["/api/funds"]

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

        real_estate = self._request_schema(document, "/api/real-estate", "post")
        assert set(real_estate["required"]) == {"name", "start_date", "initial_capital"}
        assert {
            "platform",
            "status",
            "maturity_date",
            "expected_profit",
            "expected_irr_percent",
            "expected_term_months",
            "origin",
            "tax_rate",
            "new_capital",
            "movements",
        } <= set(real_estate["properties"])
        assert not {
            "nombre",
            "plataforma",
            "estado",
            "fecha_inicio",
            "capital_inicial",
            "movimientos",
        } & set(real_estate["properties"])
        assert "required" not in self._request_schema(
            document, "/api/real-estate/{investment_id}", "put"
        )
        real_estate_parameter = document["paths"]["/api/real-estate/{investment_id}"]["put"][
            "parameters"
        ][0]
        assert real_estate_parameter["name"] == "investment_id"
        assert real_estate_parameter["schema"] == {"type": "string", "format": "uuid"}
        real_estate_response = document["paths"]["/api/real-estate"]["get"]["responses"]["200"]
        real_estate_response_schema = self._resolve(
            document,
            real_estate_response["content"]["application/json"]["schema"]["items"],
        )
        assert set(real_estate_response_schema["properties"]) == {
            "id",
            "name",
            "platform",
            "status",
            "initial_capital",
            "new_capital",
            "returned_capital",
            "realized_profit",
            "net_realized_profit",
            "expected_profit",
            "net_expected_profit",
            "expected_irr_percent",
            "expected_term_months",
            "start_date",
            "maturity_date",
            "return_date",
            "movements",
            "origin",
            "tax_rate",
            "currency",
        }
        assert real_estate_response_schema["properties"]["id"] == {
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
            "account_id",
            "trade_date",
            "operation_type",
            "quantity",
            "unit_price",
            "net_amount",
            "fee",
            "currency",
            "isin",
        } <= set(order_properties)
        assert not {
            "fecha_operacion",
            "tipo_operacion",
            "titulos",
            "precio_neto",
            "importe_neto",
            "external_id",
            "raw_metadata",
            "import_batch",
        } & set(order_properties)
        order_response = document["paths"]["/api/orders"]["get"]["responses"]["200"]
        order_response_schema = self._resolve(
            document,
            order_response["content"]["application/json"]["schema"]["items"],
        )
        assert {
            "id",
            "account_id",
            "asset_name",
            "trade_date",
            "operation_type",
            "cash_flow_type",
            "quantity",
            "unit_price",
            "net_amount",
            "fee",
            "currency",
            "base_currency",
            "base_unit_price",
            "base_net_amount",
            "base_fee",
            "fx_rate_to_base",
            "fx_rate_date",
            "fx_source",
            "market",
            "provider_operation_type",
            "isin",
        } <= set(order_response_schema["properties"])
        assert not {
            "operacion_id",
            "external_id",
            "raw_metadata",
            "import_batch",
            "fecha_operacion",
            "tipo_operacion",
        } & set(order_response_schema["properties"])
        transaction_response_common = {
            "id",
            "account_id",
            "account_name",
            "platform",
            "asset_name",
            "trade_date",
            "settlement_date",
            "operation_type",
            "cash_flow_type",
            "quantity",
            "unit_price",
            "net_amount",
            "fee",
            "currency",
            "base_currency",
            "base_unit_price",
            "base_net_amount",
            "base_fee",
            "fx_rate_to_base",
            "fx_rate_date",
            "fx_source",
            "market",
            "provider_operation_type",
        }
        transaction_response_specs = {
            "/api/orders": ("FundTransactionResponse", {"isin"}),
            "/api/stock-orders": ("StockTransactionResponse", {"isin", "is_saveback"}),
            "/api/crypto-orders": ("CryptoTransactionResponse", {"symbol"}),
        }
        for collection_path, (schema_name, asset_fields) in transaction_response_specs.items():
            expected_fields = transaction_response_common | asset_fields
            list_response = document["paths"][collection_path]["get"]["responses"]["200"]
            list_schema_ref = list_response["content"]["application/json"]["schema"]["items"]
            assert list_schema_ref == {"$ref": f"#/components/schemas/{schema_name}"}
            list_schema = self._resolve(document, list_schema_ref)
            assert set(list_schema["properties"]) == expected_fields
            assert set(list_schema["required"]) == expected_fields

            detail_path = f"{collection_path}/{{transaction_id}}"
            detail_response = document["paths"][detail_path]["put"]["responses"]["200"]
            detail_schema_ref = detail_response["content"]["application/json"]["schema"]
            assert detail_schema_ref == {"$ref": f"#/components/schemas/{schema_name}"}

        assert set(self._request_schema(document, "/api/orders", "post")["required"]) == {
            "account_id",
            "trade_date",
            "net_amount",
            "isin",
            "unit_price",
            "operation_type",
            "quantity",
        }
        assert (
            "unit_price" in self._request_schema(document, "/api/stock-orders", "post")["required"]
        )
        assert "symbol" in self._request_schema(document, "/api/crypto-orders", "post")["required"]
        assert (
            "trade_date"
            in self._resolve(
                document,
                document["paths"]["/api/orders/{transaction_id}"]["put"]["requestBody"]["content"][
                    "application/json"
                ]["schema"],
            )["properties"]
        )
        update_order = self._request_schema(document, "/api/orders/{transaction_id}", "put")
        assert "original_account_id" not in update_order.get("properties", {})
        delete_order_parameters = document["paths"]["/api/orders/{transaction_id}"]["delete"][
            "parameters"
        ]
        transaction_parameter = next(
            parameter
            for parameter in delete_order_parameters
            if parameter["name"] == "transaction_id"
        )
        assert transaction_parameter["required"] is True
        assert transaction_parameter["schema"]["format"] == "uuid"
        assert not any(parameter["name"] == "account_id" for parameter in delete_order_parameters)

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

        native_common = {
            "instrument_id",
            "kind",
            "name",
            "quantity",
            "cost",
            "current_price",
            "current_value",
            "unrealized_pnl",
            "realized_pnl",
            "currency",
            "base_currency",
        }
        native_paths = {
            "/api/fund-analysis": (
                native_common | {"asset_class", "subtype", "average_price", "return_percent"},
                "fund",
            ),
            "/api/stock-analysis": (native_common, "stock"),
            "/api/crypto-analysis": (native_common, "crypto"),
        }
        for path, (fields, expected_kind) in native_paths.items():
            operation = document["paths"][path]["get"]
            response_schema = self._resolve(
                document,
                operation["responses"]["200"]["content"]["application/json"]["schema"]["items"],
            )
            assert set(response_schema["properties"]) == fields
            assert response_schema["properties"]["instrument_id"] == {
                "type": "string",
                "format": "uuid",
            }
            kind_schema = self._resolve(document, response_schema["properties"]["kind"])
            assert kind_schema["type"] == "string"
            assert kind_schema["enum"] == [expected_kind]
            for nullable in ("current_price", "current_value", "unrealized_pnl", "realized_pnl"):
                nullable_schema = response_schema["properties"][nullable]
                assert nullable_schema["type"] == "number"
                assert nullable_schema.get("nullable") is True
            account_parameter = next(
                parameter
                for parameter in operation["parameters"]
                if parameter["name"] == "account_id"
            )
            assert account_parameter["schema"] == {"type": "string", "format": "uuid"}

        performance_parameters = document["paths"]["/api/investment-performance/{kind}"]["get"][
            "parameters"
        ]
        performance_account = next(
            parameter for parameter in performance_parameters if parameter["name"] == "account_id"
        )
        assert performance_account["schema"] == {"type": "string"}
        assert "UUID" in performance_account["description"]
        performance_response = self._resolve(
            document,
            document["paths"]["/api/investment-performance/{kind}"]["get"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"],
        )
        assert set(performance_response["properties"]) == {
            "range",
            "account_id",
            "base_currency",
            "data",
        }
        performance_point = self._resolve(
            document, performance_response["properties"]["data"]["items"]
        )
        assert set(performance_point["properties"]) == {
            "date",
            "value",
            "invested",
            "pnl",
            "pnl_percent",
        }
        assert performance_point["properties"]["date"] == {
            "type": "string",
            "format": "date",
        }
        assert all(
            performance_point["properties"][field]["type"] == "number"
            for field in {"value", "invested", "pnl", "pnl_percent"}
        )
        assert not {
            "kind",
            "moneda_base",
            "fecha",
            "valor",
            "invertido",
            "pnl_pct",
        } & set(performance_response["properties"])
        assert not {"fecha", "valor", "invertido", "pnl_pct"} & set(performance_point["properties"])

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

        price = document["paths"]["/api/stock-prices/{instrument_id}"]["put"]
        price_properties = self._resolve(
            document, price["requestBody"]["content"]["application/json"]["schema"]
        )["properties"]
        assert set(price_properties) == {"close", "currency"}
        assert price_properties["close"]["type"] == "string"
        assert price["parameters"][0]["name"] == "instrument_id"
        assert price["parameters"][0]["schema"] == {"type": "string", "format": "uuid"}
        assert "200" in price["responses"]

        price_response = self._resolve(
            document,
            document["paths"]["/api/stock-prices"]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["items"],
        )
        assert set(price_response["properties"]) == {
            "id",
            "instrument_id",
            "quoted_at",
            "close",
            "currency",
            "base_close",
            "base_currency",
            "fx_rate_to_base",
            "fx_rate_date",
            "fx_source",
            "source",
        }
        assert not {"isin", "symbol", "precio", "moneda"} & set(price_response["properties"])
        assert price_response["properties"]["close"]["type"] == "number"
        assert price_response["properties"]["base_close"]["type"] == "number"
        assert price_response["properties"]["fx_rate_to_base"]["type"] == "number"
        fetch = document["paths"]["/api/stock-prices/fetch"]["post"]
        assert "requestBody" not in fetch
        fetch_response = self._resolve(
            document,
            fetch["responses"]["200"]["content"]["application/json"]["schema"],
        )
        assert set(fetch_response["properties"]) == {"results"}
        fetch_item = self._resolve(document, fetch_response["properties"]["results"]["items"])
        assert fetch_item["properties"]["base_close"]["type"] == "number"
        assert fetch_item["properties"]["base_close"]["nullable"] is True
        assert fetch_item["properties"]["close"]["type"] == "number"
        assert fetch_item["properties"]["close"]["nullable"] is True

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

        stock_split = document["paths"]["/api/stock-splits"]
        split_request = self._resolve(
            document,
            stock_split["post"]["requestBody"]["content"]["application/json"]["schema"],
        )
        assert set(split_request["properties"]) == {
            "instrument_id",
            "effective_date",
            "ratio",
            "source",
        }
        assert set(split_request["required"]) == {
            "instrument_id",
            "effective_date",
            "ratio",
        }
        assert split_request["properties"]["instrument_id"] == {
            "type": "string",
            "format": "uuid",
        }
        assert split_request["properties"]["effective_date"] == {
            "type": "string",
            "format": "date",
        }
        assert split_request["properties"]["ratio"]["type"] == "string"
        split_response = self._resolve(
            document,
            stock_split["get"]["responses"]["200"]["content"]["application/json"]["schema"][
                "items"
            ],
        )
        assert set(split_response["properties"]) == {
            "id",
            "instrument_id",
            "effective_date",
            "ratio",
            "source",
        }
        assert split_response["properties"]["ratio"]["type"] == "number"
        split_delete = document["paths"]["/api/stock-splits/{split_id}"]["delete"]
        assert split_delete["parameters"] == [
            {
                "in": "path",
                "name": "split_id",
                "schema": {"type": "string", "format": "uuid"},
                "required": True,
            }
        ]
        assert self._resolve(
            document,
            split_delete["responses"]["200"]["content"]["application/json"]["schema"],
        ) == {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        assert "/api/stock-splits/{asset_id}/{value_date}" not in document["paths"]

        for chart_path in (
            "/api/fund-chart/{instrument_id}",
            "/api/stock-chart/{instrument_id}",
            "/api/crypto-chart/{instrument_id}",
        ):
            operation = document["paths"][chart_path]["get"]
            assert operation["parameters"] == [
                {
                    "in": "path",
                    "name": "instrument_id",
                    "schema": {"type": "string", "format": "uuid"},
                    "required": True,
                }
            ]
            chart_response = self._resolve(
                document,
                operation["responses"]["200"]["content"]["application/json"]["schema"],
            )
            assert set(chart_response["properties"]) == {
                "instrument_id",
                "ticker",
                "currency",
                "base_currency",
                "range",
                "data",
            }
            point = self._resolve(document, chart_response["properties"]["data"]["items"])
            expected_point_fields = (
                {"date", "close"}
                if chart_path == "/api/fund-chart/{instrument_id}"
                else {"date", "open", "high", "low", "close"}
            )
            assert set(point["properties"]) == expected_point_fields
            assert point["properties"]["date"] == {"type": "string", "format": "date"}
            assert all(
                point["properties"][field]["type"] == "number"
                for field in expected_point_fields - {"date"}
            )
        assert "/api/fund-chart/{asset_id}" not in document["paths"]
        assert "/api/stock-chart/{asset_id}" not in document["paths"]
        assert "/api/crypto-chart/{asset_id}" not in document["paths"]

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
