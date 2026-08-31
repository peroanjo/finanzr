"""Explicit OpenAPI mapping for function-based compatibility API views."""

from __future__ import annotations

from typing import Any, cast

from apps.api.schemas import (
    AccountRequestSerializer,
    AccountResponseSerializer,
    AdminUserRequestSerializer,
    AdminUserSerializer,
    AdminUserUpdateRequestSerializer,
    ApiErrorSerializer,
    ApiListSerializer,
    ApiObjectSerializer,
    ApiPayloadSerializer,
    BudgetRequestSerializer,
    BudgetRowSerializer,
    CalculatorRequestSerializer,
    CalculatorResponseSerializer,
    CalculatorUpdateRequestSerializer,
    CryptoInstrumentRequestSerializer,
    CryptoTransactionRequestSerializer,
    CsrfSerializer,
    DeleteAccountRequestSerializer,
    FinancialAccountRequestSerializer,
    FinancialAccountUpdateRequestSerializer,
    FinancialObjectSerializer,
    FundTransactionRequestSerializer,
    FxRateRequestSerializer,
    FxRateResponseSerializer,
    FxRateUpdateRequestSerializer,
    InstallationPreferencesSerializer,
    InstrumentSerializer,
    InstrumentUpdateRequestSerializer,
    InvestmentSnapshotRequestSerializer,
    InvitationAcceptRequestSerializer,
    InvitationRequestSerializer,
    InvitationSerializer,
    IsinInstrumentRequestSerializer,
    LoginRequestSerializer,
    NativeSavingsAccountResponseSerializer,
    NativeSavingsSnapshotRequestSerializer,
    NativeSavingsSnapshotResponseSerializer,
    OkSerializer,
    PasswordRequestSerializer,
    PasswordResetConfirmRequestSerializer,
    PasswordResetRequestSerializer,
    PortfolioRequestSerializer,
    PortfolioResponseSerializer,
    PortfolioUpdateRequestSerializer,
    PreferencesRequestSerializer,
    PriceRequestSerializer,
    PriceResponseSerializer,
    RealEstateRequestSerializer,
    RealEstateResponseSerializer,
    RealEstateUpdateRequestSerializer,
    SavingsAccountRequestSerializer,
    SavingsAccountUpdateRequestSerializer,
    SnapshotResponseSerializer,
    StockSplitRequestSerializer,
    StockTransactionRequestSerializer,
    TransactionResponseSerializer,
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
        "/api/calculator",
        "/api/crypto-accounts",
        "/api/crypto-orders",
        "/api/crypto-prices",
        "/api/cryptos",
        "/api/fund-accounts",
        "/api/fund-prices",
        "/api/funds",
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
    }
)

CREATED_POST_PATHS = frozenset(
    {
        "/api/administration/users",
        "/api/calculator",
        "/api/crypto-accounts",
        "/api/crypto-orders",
        "/api/cryptos",
        "/api/fund-accounts",
        "/api/funds",
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
        if "/upload" in self.path or "account-imports/" in self.path:
            return UploadRequestSerializer()
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
        if family_path in {
            "/api/investments/accounts",
            "/api/fund-accounts",
            "/api/stock-accounts",
            "/api/crypto-accounts",
        }:
            if "{" in path:
                return FinancialAccountUpdateRequestSerializer()
            return FinancialAccountRequestSerializer()
        if family_path == "/api/investments/history":
            return InvestmentSnapshotRequestSerializer()
        if family_path == "/api/portfolio":
            return (
                PortfolioUpdateRequestSerializer() if "{" in path else PortfolioRequestSerializer()
            )
        if family_path == "/api/real-estate":
            return (
                RealEstateUpdateRequestSerializer()
                if "{" in path
                else RealEstateRequestSerializer()
            )
        if family_path == "/api/calculator":
            return (
                CalculatorUpdateRequestSerializer()
                if "{" in path
                else CalculatorRequestSerializer()
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
        elif family_path == "/api/calculator":
            response = CalculatorResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/savings/accounts":
            response = NativeSavingsAccountResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/savings/history":
            response = NativeSavingsSnapshotResponseSerializer(many=self.method == "GET")
        elif family_path in {
            "/api/investments/accounts",
            "/api/fund-accounts",
            "/api/stock-accounts",
            "/api/crypto-accounts",
        }:
            response = AccountResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/investments/history":
            response = SnapshotResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/portfolio":
            response = PortfolioResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/real-estate":
            response = RealEstateResponseSerializer(many=self.method == "GET")
        elif family_path in {"/api/orders", "/api/stock-orders", "/api/crypto-orders"}:
            response = TransactionResponseSerializer(many=self.method == "GET")
        elif family_path in {"/api/fund-prices", "/api/stock-prices", "/api/crypto-prices"}:
            response = PriceResponseSerializer(many=self.method == "GET")
        elif family_path == "/api/fx-rates":
            response = FxRateResponseSerializer(many=self.method == "GET")
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
            "/api/calculator",
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
