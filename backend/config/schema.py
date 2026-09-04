"""Explicit OpenAPI mapping for function-based API views."""

from __future__ import annotations

from typing import Any, cast

from apps.api.schemas import (
    AccountRequestSerializer,
    AccountResponseSerializer,
    AccountUploadRequestSerializer,
    AdminUserRequestSerializer,
    AdminUserSerializer,
    AdminUserUpdateRequestSerializer,
    ApiErrorSerializer,
    ApiListSerializer,
    ApiObjectSerializer,
    ApiPayloadSerializer,
    BudgetRequestSerializer,
    BudgetRowSerializer,
    CryptoInstrumentRequestSerializer,
    CryptoTransactionRequestSerializer,
    CryptoTransactionResponseSerializer,
    CryptoTransactionUpdateRequestSerializer,
    CsrfSerializer,
    DeleteAccountRequestSerializer,
    FinancialObjectSerializer,
    FundChartResponseSerializer,
    FundTransactionRequestSerializer,
    FundTransactionResponseSerializer,
    FundTransactionUpdateRequestSerializer,
    FxRateRequestSerializer,
    FxRateResponseSerializer,
    FxRateUpdateRequestSerializer,
    InstallationPreferencesSerializer,
    InstrumentSerializer,
    InstrumentUpdateRequestSerializer,
    InvestmentAccountRequestSerializer,
    InvestmentAccountUpdateRequestSerializer,
    InvestmentPerformanceResponseSerializer,
    InvitationAcceptRequestSerializer,
    InvitationRequestSerializer,
    InvitationSerializer,
    IsinInstrumentRequestSerializer,
    LoginRequestSerializer,
    ManualAssetRequestSerializer,
    ManualAssetResponseSerializer,
    ManualAssetUpdateRequestSerializer,
    MarketChartResponseSerializer,
    NativeCryptoPositionResponseSerializer,
    NativeFundPositionResponseSerializer,
    NativeInvestmentAccountResponseSerializer,
    NativeInvestmentSnapshotRequestSerializer,
    NativeInvestmentSnapshotResponseSerializer,
    NativeSavingsAccountResponseSerializer,
    NativeSavingsSnapshotRequestSerializer,
    NativeSavingsSnapshotResponseSerializer,
    NativeStockPositionResponseSerializer,
    OkSerializer,
    PasswordRequestSerializer,
    PasswordResetConfirmRequestSerializer,
    PasswordResetRequestSerializer,
    PortfolioAnalysisResponseSerializer,
    PreferencesRequestSerializer,
    PriceFetchResponseSerializer,
    PriceRequestSerializer,
    PriceResponseSerializer,
    RealEstateRequestSerializer,
    RealEstateResponseSerializer,
    RealEstateUpdateRequestSerializer,
    SavingsAccountRequestSerializer,
    SavingsAccountUpdateRequestSerializer,
    StockSplitRequestSerializer,
    StockSplitResponseSerializer,
    StockTransactionRequestSerializer,
    StockTransactionResponseSerializer,
    StockTransactionUpdateRequestSerializer,
    TradedAccountRequestSerializer,
    TradedAccountUpdateRequestSerializer,
    UploadRequestSerializer,
    UserSessionSerializer,
    WorkspaceRequestSerializer,
)
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

LIST_PATHS = frozenset(
    {
        "/api/audit-events",
        "/api/crypto-accounts",
        "/api/crypto-orders",
        "/api/crypto-prices",
        "/api/cryptos",
        "/api/fund-accounts",
        "/api/fund-prices",
        "/api/funds",
        "/api/fund-analysis",
        "/api/importers",
        "/api/investments/accounts",
        "/api/investments/history",
        "/api/net-worth-history",
        "/api/orders",
        "/api/portfolio",
        "/api/real-estate",
        "/api/savings/accounts",
        "/api/savings/history",
        "/api/stock-accounts",
        "/api/stock-orders",
        "/api/stock-prices",
        "/api/stock-splits",
        "/api/stocks",
        "/api/stock-analysis",
        "/api/crypto-analysis",
    }
)

CREATED_POST_PATHS = frozenset(
    {
        "/api/administration/users",
        "/api/crypto-accounts",
        "/api/crypto-orders",
        "/api/cryptos",
        "/api/fund-accounts",
        "/api/fx-rates",
        "/api/investments/accounts",
        "/api/investments/history",
        "/api/orders",
        "/api/portfolio",
        "/api/real-estate",
        "/api/savings/accounts",
        "/api/savings/history",
        "/api/stock-accounts",
        "/api/stock-orders",
        "/api/stocks",
        "/api/workspaces/invitations",
    }
)

USER_SESSION_PATHS = frozenset(
    {
        "/api/auth/account",
        "/api/auth/login",
        "/api/auth/me",
        "/api/auth/preferences",
        "/api/workspaces/current",
        "/api/workspaces/invitations/accept",
    }
)


class PublicAutoSchema(AutoSchema):
    """Describe every function-based endpoint with explicit typed serializers."""

    def get_override_parameters(self) -> list[Any]:
        parameters = list(super().get_override_parameters())
        path = self.path.rstrip("/")
        if path == "/api/savings/history" and self.method == "GET":
            parameters.append(
                OpenApiParameter(
                    name="account_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.QUERY,
                    required=False,
                )
            )
        elif path == "/api/savings/history/{account_id}/{value_date}":
            parameters.append(
                OpenApiParameter(
                    name="value_date",
                    type=OpenApiTypes.DATE,
                    location=OpenApiParameter.PATH,
                    required=True,
                )
            )
        elif path == "/api/investments/history" and self.method == "GET":
            parameters.append(
                OpenApiParameter(
                    name="account_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.QUERY,
                    required=False,
                )
            )
        elif path == "/api/investments/history/{account_id}/{value_date}":
            parameters.append(
                OpenApiParameter(
                    name="value_date",
                    type=OpenApiTypes.DATE,
                    location=OpenApiParameter.PATH,
                    required=True,
                )
            )
        elif (
            path
            in {
                "/api/orders",
                "/api/stock-orders",
                "/api/crypto-orders",
                "/api/fund-analysis",
                "/api/stock-analysis",
                "/api/crypto-analysis",
            }
            and self.method == "GET"
        ):
            parameters.append(
                OpenApiParameter(
                    name="account_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.QUERY,
                    required=False,
                )
            )
        elif path == "/api/investment-performance/{kind}" and self.method == "GET":
            parameters.append(
                OpenApiParameter(
                    name="account_id",
                    type=OpenApiTypes.STR,
                    location=OpenApiParameter.QUERY,
                    required=False,
                    description="Account UUID or the literal 'all'.",
                )
            )
        elif (
            path
            in {
                "/api/fund-chart/{instrument_id}",
                "/api/stock-chart/{instrument_id}",
                "/api/crypto-chart/{instrument_id}",
            }
            and self.method == "GET"
        ):
            parameters.append(
                OpenApiParameter(
                    name="instrument_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.PATH,
                    required=True,
                )
            )
        elif (
            path
            in {
                "/api/orders/{transaction_id}",
                "/api/stock-orders/{transaction_id}",
                "/api/crypto-orders/{transaction_id}",
            }
            and self.method == "DELETE"
        ):
            parameters.append(
                OpenApiParameter(
                    name="transaction_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.PATH,
                    required=True,
                )
            )
        elif (
            path
            in {
                "/api/orders/{transaction_id}",
                "/api/stock-orders/{transaction_id}",
                "/api/crypto-orders/{transaction_id}",
            }
            and self.method == "PUT"
        ):
            parameters.append(
                OpenApiParameter(
                    name="transaction_id",
                    type=OpenApiTypes.UUID,
                    location=OpenApiParameter.PATH,
                    required=True,
                )
            )
        return parameters

    def _base_serializer(self) -> Any:
        view = self.view
        if isinstance(view, GenericAPIView):
            base_get_serializer: Any = super()._get_serializer
            return base_get_serializer()
        if isinstance(view, APIView):
            return ApiObjectSerializer()
        return ApiObjectSerializer()

    def _get_request_body(self, direction: str = "request") -> Any:
        if self.method == "DELETE" and self.path.rstrip("/") == "/api/account":
            original_method = self.method
            self.method = "POST"
            try:
                return cast(Any, super()._get_request_body)(direction)
            finally:
                self.method = original_method
        return cast(Any, super()._get_request_body)(direction)

    def get_request_serializer(self) -> Any:
        if self.method == "DELETE" and self.path.rstrip("/") == "/api/account":
            return DeleteAccountRequestSerializer()
        if self.method not in {"POST", "PUT", "PATCH"}:
            return None
        path = self.path.rstrip("/")
        family_path = path.split("/{", 1)[0]
        if path == "/api/auth/login":
            return LoginRequestSerializer()
        if path == "/api/account":
            return DeleteAccountRequestSerializer()
        if path == "/api/auth/preferences":
            return PreferencesRequestSerializer()
        if path == "/api/installation/preferences":
            return InstallationPreferencesSerializer()
        if path == "/api/auth/account":
            return AccountRequestSerializer()
        if path == "/api/auth/password":
            return PasswordRequestSerializer()
        if path == "/api/auth/password-reset":
            return PasswordResetRequestSerializer()
        if path == "/api/auth/password-reset/confirm":
            return PasswordResetConfirmRequestSerializer()
        if path == "/api/workspaces/current":
            return WorkspaceRequestSerializer()
        if path == "/api/workspaces/invitations":
            return InvitationRequestSerializer()
        if path == "/api/workspaces/invitations/accept":
            return InvitationAcceptRequestSerializer()
        if path == "/api/administration/users":
            return AdminUserRequestSerializer()
        if path == "/api/administration/users/{user_id}":
            return AdminUserUpdateRequestSerializer()
        if "account-imports/" in self.path:
            return UploadRequestSerializer()
        if "/upload" in self.path:
            return AccountUploadRequestSerializer()
        if path in {
            "/api/fund-prices/fetch",
            "/api/stock-prices/fetch",
            "/api/crypto-prices/fetch",
        }:
            return None
        if family_path in {"/api/orders", "/api/stock-orders", "/api/crypto-orders"}:
            if family_path == "/api/orders":
                return (
                    FundTransactionUpdateRequestSerializer()
                    if "{" in path
                    else FundTransactionRequestSerializer()
                )
            if family_path == "/api/stock-orders":
                return (
                    StockTransactionUpdateRequestSerializer()
                    if "{" in path
                    else StockTransactionRequestSerializer()
                )
            return (
                CryptoTransactionUpdateRequestSerializer()
                if "{" in path
                else CryptoTransactionRequestSerializer()
            )
        if family_path in {"/api/funds", "/api/stocks", "/api/cryptos"}:
            if "{" in path:
                return InstrumentUpdateRequestSerializer()
            return (
                CryptoInstrumentRequestSerializer()
                if family_path == "/api/cryptos"
                else IsinInstrumentRequestSerializer()
            )
        if family_path == "/api/savings/accounts":
            return (
                SavingsAccountUpdateRequestSerializer()
                if "{" in path
                else SavingsAccountRequestSerializer()
            )
        if family_path == "/api/savings/history":
            return NativeSavingsSnapshotRequestSerializer()
        if family_path == "/api/investments/accounts":
            return (
                InvestmentAccountUpdateRequestSerializer()
                if "{" in path
                else InvestmentAccountRequestSerializer()
            )
        if family_path == "/api/investments/history":
            return NativeInvestmentSnapshotRequestSerializer()
        if family_path in {
            "/api/fund-accounts",
            "/api/stock-accounts",
            "/api/crypto-accounts",
        }:
            if "{" in path:
                return TradedAccountUpdateRequestSerializer()
            return TradedAccountRequestSerializer()
        if family_path == "/api/portfolio":
            return (
                ManualAssetUpdateRequestSerializer()
                if "{" in path
                else ManualAssetRequestSerializer()
            )
        if family_path == "/api/real-estate":
            return (
                RealEstateUpdateRequestSerializer()
                if "{" in path
                else RealEstateRequestSerializer()
            )
        if path == "/api/budget":
            return BudgetRequestSerializer(many=True)
        if family_path in {"/api/orders", "/api/stock-orders", "/api/crypto-orders"}:
            if family_path == "/api/stock-orders":
                return StockTransactionRequestSerializer()
            if family_path == "/api/crypto-orders":
                return CryptoTransactionRequestSerializer()
            return FundTransactionRequestSerializer()
        if family_path == "/api/stock-splits":
            return StockSplitRequestSerializer()
        if family_path in {"/api/fund-prices", "/api/stock-prices", "/api/crypto-prices"}:
            return PriceRequestSerializer()
        if family_path == "/api/fx-rates":
            return FxRateUpdateRequestSerializer() if "{" in path else FxRateRequestSerializer()
        return ApiPayloadSerializer()

    def get_response_serializers(self) -> Any:
        path = self.path.rstrip("/")
        family_path = path.split("/{", 1)[0]
        response = self._base_serializer()
        if path in USER_SESSION_PATHS:
            response = UserSessionSerializer
        elif path == "/api/auth/csrf":
            response = CsrfSerializer
        elif path in {
            "/api/auth/logout",
            "/api/auth/password",
            "/api/auth/password-reset",
            "/api/auth/password-reset/confirm",
        }:
            response = OkSerializer
        elif path == "/api/installation/preferences":
            response = InstallationPreferencesSerializer
        elif path == "/api/workspaces/invitations":
            response = InvitationSerializer
        elif path == "/api/administration/users":
            response = AdminUserSerializer(many=self.method == "GET")
        elif path == "/api/administration/users/{user_id}":
            response = AdminUserSerializer
        elif family_path in {"/api/funds", "/api/stocks", "/api/cryptos"}:
            response = InstrumentSerializer(many=self.method == "GET")
        elif family_path == "/api/savings/accounts":
            response = NativeSavingsAccountResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/savings/history":
            response = NativeSavingsSnapshotResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/investments/accounts":
            response = NativeInvestmentAccountResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/investments/history":
            response = NativeInvestmentSnapshotResponseSerializer(many=self.method == "GET")
        elif path == "/api/investment-performance/{kind}":
            response = InvestmentPerformanceResponseSerializer
        elif path == "/api/fund-analysis":
            response = NativeFundPositionResponseSerializer(many=True)
        elif path == "/api/stock-analysis":
            response = NativeStockPositionResponseSerializer(many=True)
        elif path == "/api/crypto-analysis":
            response = NativeCryptoPositionResponseSerializer(many=True)
        elif path == "/api/portfolio-analysis":
            response = PortfolioAnalysisResponseSerializer
        elif path == "/api/fund-chart/{instrument_id}":
            response = FundChartResponseSerializer
        elif path in {
            "/api/stock-chart/{instrument_id}",
            "/api/crypto-chart/{instrument_id}",
        }:
            response = MarketChartResponseSerializer
        elif family_path in {
            "/api/fund-accounts",
            "/api/stock-accounts",
            "/api/crypto-accounts",
        }:
            response = AccountResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/portfolio":
            response = ManualAssetResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/real-estate":
            response = RealEstateResponseSerializer(many=self.method == "GET")
        elif family_path in {"/api/orders", "/api/stock-orders", "/api/crypto-orders"}:
            response_serializer = {
                "/api/orders": FundTransactionResponseSerializer,
                "/api/stock-orders": StockTransactionResponseSerializer,
                "/api/crypto-orders": CryptoTransactionResponseSerializer,
            }[family_path]
            response = response_serializer(many=self.method == "GET")
        elif family_path in {"/api/fund-prices", "/api/stock-prices", "/api/crypto-prices"}:
            response = PriceResponseSerializer(many=self.method == "GET")
            if self.method == "PUT":
                response = OkSerializer
        elif path in {
            "/api/fund-prices/fetch",
            "/api/stock-prices/fetch",
            "/api/crypto-prices/fetch",
        }:
            response = PriceFetchResponseSerializer
        elif family_path == "/api/fx-rates":
            response = FxRateResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/stock-splits":
            response = StockSplitResponseSerializer(many=self.method == "GET")
        elif path == "/api/budget":
            response = BudgetRowSerializer(many=True)
        elif family_path in {
            "/api/savings/accounts",
            "/api/investments/accounts",
            "/api/fund-accounts",
            "/api/stock-accounts",
            "/api/crypto-accounts",
            "/api/savings/history",
            "/api/investments/history",
            "/api/portfolio",
            "/api/real-estate",
            "/api/budget",
            "/api/orders",
            "/api/stock-orders",
            "/api/crypto-orders",
            "/api/stock-splits",
            "/api/fund-prices",
            "/api/stock-prices",
            "/api/crypto-prices",
            "/api/fx-rates",
        }:
            response = FinancialObjectSerializer(many=self.method == "GET")
        elif self.method == "GET" and path in LIST_PATHS:
            response = ApiListSerializer(many=True)
        responses: dict[int, Any] = {
            200: response,
            400: ApiErrorSerializer,
            403: ApiErrorSerializer,
        }
        if self.method == "POST" and path in CREATED_POST_PATHS:
            responses[201] = response
            if path != "/api/fx-rates":
                responses.pop(200, None)
        if self.method == "DELETE" and family_path not in {
            "/api/account",
            "/api/administration/users",
        }:
            responses[200] = OkSerializer
        if self.method == "DELETE" and path in {
            "/api/account",
            "/api/administration/users/{user_id}",
        }:
            responses = {204: None, 400: ApiErrorSerializer, 403: ApiErrorSerializer}
            if path == "/api/account":
                responses[409] = ApiErrorSerializer
        if self.path.endswith("/account-imports") or "account-imports/" in self.path:
            responses[409] = ApiErrorSerializer
        return responses
