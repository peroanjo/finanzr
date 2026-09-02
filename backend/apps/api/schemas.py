"""OpenAPI serializers for the compatibility API's stable JSON envelopes."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from rest_framework import serializers


class ApiErrorSerializer(serializers.Serializer[dict[str, Any]]):
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)


class ApiPayloadSerializer(serializers.Serializer[dict[str, Any]]):
    """Common request fields accepted by the legacy-compatible endpoints."""

    nombre = serializers.CharField(required=False)
    tipo = serializers.CharField(required=False)
    moneda = serializers.CharField(required=False)
    cuenta_id = serializers.CharField(required=False)
    fecha = serializers.DateField(required=False)
    fecha_operacion = serializers.DateField(required=False)
    fecha_liquidacion = serializers.DateField(required=False)
    importe = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    valor = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    aporte = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    file = serializers.FileField(required=False)


class LoginRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class WorkspaceRequestSerializer(serializers.Serializer[dict[str, Any]]):
    workspace_id = serializers.UUIDField()


class PasswordRequestSerializer(serializers.Serializer[dict[str, Any]]):
    current_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    password_confirmation = serializers.CharField(write_only=True)


class DeleteAccountRequestSerializer(serializers.Serializer[dict[str, Any]]):
    password = serializers.CharField(write_only=True)


class PreferencesRequestSerializer(serializers.Serializer[dict[str, Any]]):
    language = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    summary_sources = serializers.ListField(
        child=serializers.CharField(), required=False, allow_null=True
    )


class InstallationPreferencesSerializer(serializers.Serializer[dict[str, Any]]):
    default_language = serializers.CharField(required=False)
    default_crowdfunding_tax_rate = serializers.DecimalField(
        max_digits=8, decimal_places=4, required=False
    )
    default_summary_sources = serializers.ListField(child=serializers.CharField(), required=False)
    language = serializers.CharField(required=False)


class AccountRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    current_password = serializers.CharField(write_only=True)


class InvitationRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=("editor", "viewer"), required=False)


class InvitationAcceptRequestSerializer(serializers.Serializer[dict[str, Any]]):
    token = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()


class PasswordResetConfirmRequestSerializer(serializers.Serializer[dict[str, Any]]):
    uid = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)


class AdminUserRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    display_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=("admin", "user"), required=False)
    password = serializers.CharField(write_only=True)
    password_confirmation = serializers.CharField(write_only=True)


class AdminUserUpdateRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(required=False)
    display_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=("admin", "user", "demo"), required=False)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    password_confirmation = serializers.CharField(write_only=True, required=False)


class StrictSerializer(serializers.Serializer[dict[str, Any]]):
    """Serializer base that rejects compatibility-shaped or unknown fields."""

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Expected a JSON object")
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                {"non_field_errors": [f"Unknown field(s): {', '.join(unknown)}"]}
            )
        return cast(dict[str, Any], super().to_internal_value(data))


class UploadRequestSerializer(StrictSerializer):
    """Request body for account-bound imports; identity comes from the path."""

    file = serializers.FileField()


class AccountUploadRequestSerializer(StrictSerializer):
    """Request body for generic imports that select an account explicitly."""

    file = serializers.FileField()
    account_id = serializers.UUIDField(required=True)


class InstrumentRequestSerializer(serializers.Serializer[dict[str, Any]]):
    nombre = serializers.CharField(required=True)
    ticker = serializers.CharField(required=True)
    moneda = serializers.CharField(required=False, default="EUR")


class InstrumentUpdateRequestSerializer(serializers.Serializer[dict[str, Any]]):
    nombre = serializers.CharField(required=False)
    ticker = serializers.CharField(required=False)
    moneda = serializers.CharField(required=False)
    isin = serializers.CharField(required=False)
    symbol = serializers.CharField(required=False)


class IsinInstrumentRequestSerializer(InstrumentRequestSerializer):
    isin = serializers.CharField(required=True)


class CryptoInstrumentRequestSerializer(InstrumentRequestSerializer):
    symbol = serializers.CharField(required=True)


class TradedAccountRequestSerializer(StrictSerializer):
    """Native request contract shared by fund, stock, and crypto accounts."""

    name = serializers.CharField(required=True, allow_blank=False, max_length=160)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)
    importer_slug = serializers.CharField(required=False, allow_blank=True, max_length=80)


class TradedAccountUpdateRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=160)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)
    importer_slug = serializers.CharField(required=False, allow_blank=True, max_length=80)


class SavingsAccountRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=True, allow_blank=False, max_length=160)
    bank = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)


class SavingsAccountUpdateRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=160)
    bank = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)


class NativeSavingsSnapshotRequestSerializer(StrictSerializer):
    account_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)
    balance = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    contribution = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, default=Decimal("0")
    )
    interest = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, default=Decimal("0")
    )


class NativeSavingsAccountResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    bank = serializers.CharField()
    type = serializers.CharField()
    currency = serializers.CharField()


class NativeSavingsSnapshotResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    account_id = serializers.UUIDField()
    date = serializers.DateField()
    balance = serializers.FloatField()
    balance_original = serializers.FloatField()
    contribution = serializers.FloatField()
    contribution_original = serializers.FloatField()
    interest = serializers.FloatField()
    interest_original = serializers.FloatField()
    currency = serializers.CharField()
    base_currency = serializers.CharField()
    exchange_rate = serializers.FloatField()
    exchange_rate_date = serializers.DateField()
    exchange_rate_source = serializers.CharField()


class InvestmentAccountRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=True, allow_blank=False, max_length=160)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)


class InvestmentAccountUpdateRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=160)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    type = serializers.CharField(required=False, allow_blank=True, max_length=80)
    currency = serializers.CharField(required=False, allow_blank=False, max_length=3)


class NativeInvestmentSnapshotRequestSerializer(StrictSerializer):
    account_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)
    value = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    contribution = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, default=Decimal("0")
    )
    interest = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)


class NativeInvestmentAccountResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    platform = serializers.CharField()
    type = serializers.CharField()
    currency = serializers.CharField()


class NativeInvestmentSnapshotResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    account_id = serializers.UUIDField()
    date = serializers.DateField()
    value = serializers.FloatField()
    value_original = serializers.FloatField()
    contribution = serializers.FloatField()
    contribution_original = serializers.FloatField()
    interest = serializers.FloatField()
    interest_original = serializers.FloatField()
    currency = serializers.CharField()
    base_currency = serializers.CharField()
    exchange_rate = serializers.FloatField()
    exchange_rate_date = serializers.DateField()
    exchange_rate_source = serializers.CharField()


class ManualAssetRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=True, allow_blank=False, max_length=200)
    asset_class = serializers.CharField(required=True, allow_blank=False, max_length=80)
    subtype = serializers.CharField(required=False, allow_blank=True, max_length=120)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    value = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class ManualAssetUpdateRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=200)
    asset_class = serializers.CharField(required=False, allow_blank=False, max_length=80)
    subtype = serializers.CharField(required=False, allow_blank=True, max_length=120)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    value = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)


class RealEstateRequestSerializer(serializers.Serializer[dict[str, Any]]):
    nombre = serializers.CharField(required=True)
    plataforma = serializers.CharField(required=False)
    estado = serializers.CharField(required=False)
    fecha_inicio = serializers.DateField(required=False)
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)
    beneficio_estimado = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    tir = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    meses = serializers.IntegerField(required=False)
    origen = serializers.CharField(required=False)
    retencion_irpf = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    capital_inicial = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    capital_nuevo = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    capital_devuelto = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    beneficio_obtenido = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    fecha_devolucion = serializers.DateField(required=False, allow_null=True)
    movimientos = serializers.ListField(required=False)


class RealEstateUpdateRequestSerializer(RealEstateRequestSerializer):
    nombre = serializers.CharField(required=False)


class BudgetRowSerializer(serializers.Serializer[dict[str, Any]]):
    categoria = serializers.CharField(required=True)
    cantidad = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    tipo = serializers.CharField(required=True)


class BudgetRequestSerializer(BudgetRowSerializer):
    pass


class TransactionRequestSerializer(StrictSerializer):
    fecha_operacion = serializers.DateField(required=True)
    fecha_liquidacion = serializers.DateField(required=False, allow_null=True)
    tipo_operacion = serializers.CharField(required=True)
    titulos = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    importe_neto = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    comision = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    account_id = serializers.UUIDField(required=True)
    original_account_id = serializers.UUIDField(required=False)
    divisa = serializers.CharField(required=False, allow_blank=True, max_length=4)
    moneda = serializers.CharField(required=False, allow_blank=True, max_length=4)
    tipo_cambio = serializers.DecimalField(
        max_digits=24, decimal_places=12, required=False, allow_null=True
    )
    fecha_tipo_cambio = serializers.DateField(required=False, allow_null=True)
    fuente_tipo_cambio = serializers.CharField(required=False, allow_blank=True, max_length=40)
    mercado = serializers.CharField(required=False, allow_blank=True, max_length=80)
    es_saveback = serializers.BooleanField(required=False)


class FundTransactionRequestSerializer(TransactionRequestSerializer):
    isin = serializers.CharField(required=True)
    precio_neto = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class StockTransactionRequestSerializer(TransactionRequestSerializer):
    isin = serializers.CharField(required=True)
    precio_compra = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class CryptoTransactionRequestSerializer(TransactionRequestSerializer):
    symbol = serializers.CharField(required=True)
    precio_compra = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class FundTransactionUpdateRequestSerializer(FundTransactionRequestSerializer):
    original_account_id = serializers.UUIDField(required=True)


class StockTransactionUpdateRequestSerializer(StockTransactionRequestSerializer):
    original_account_id = serializers.UUIDField(required=True)


class CryptoTransactionUpdateRequestSerializer(CryptoTransactionRequestSerializer):
    original_account_id = serializers.UUIDField(required=True)


class StockSplitRequestSerializer(serializers.Serializer[dict[str, Any]]):
    fecha = serializers.DateField(required=True)
    ratio = serializers.DecimalField(max_digits=12, decimal_places=6, required=True)
    isin = serializers.CharField(required=True)


class PriceRequestSerializer(serializers.Serializer[dict[str, Any]]):
    precio = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    moneda = serializers.CharField(required=False, default="EUR")


class FxRateRequestSerializer(serializers.Serializer[dict[str, Any]]):
    quote_currency = serializers.CharField(required=False)
    base_currency = serializers.CharField(required=False)
    rate_date = serializers.DateField(required=False)
    rate = serializers.DecimalField(max_digits=24, decimal_places=12, required=True)


class FxRateUpdateRequestSerializer(FxRateRequestSerializer):
    rate = serializers.DecimalField(max_digits=24, decimal_places=12, required=False)


class ManualAssetResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    asset_class = serializers.CharField()
    subtype = serializers.CharField()
    platform = serializers.CharField()
    value = serializers.FloatField()
    currency = serializers.CharField()


class TransactionResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.CharField(required=False)
    fecha_operacion = serializers.DateField(required=False)
    tipo_operacion = serializers.CharField(required=False)
    titulos = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    precio_neto = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    importe_neto = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    comision = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    cuenta_id = serializers.UUIDField(required=False)
    cuenta_nombre = serializers.CharField(required=False)
    plataforma = serializers.CharField(required=False)
    moneda = serializers.CharField(required=False)
    moneda_base = serializers.CharField(required=False)
    importe_base = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    tipo_cambio = serializers.DecimalField(max_digits=24, decimal_places=12, required=False)
    fecha_tipo_cambio = serializers.DateField(required=False)
    fuente_tipo_cambio = serializers.CharField(required=False)
    fecha_liquidacion = serializers.CharField(required=False, allow_blank=True)
    mercado = serializers.CharField(required=False)
    nombre_fondo = serializers.CharField(required=False)
    nombre_activo = serializers.CharField(required=False)
    divisa = serializers.CharField(required=False)
    precio_compra = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    precio_base = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    comision_base = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    es_saveback = serializers.BooleanField(required=False)
    isin = serializers.CharField(required=False)
    symbol = serializers.CharField(required=False)


class PriceResponseSerializer(serializers.Serializer[dict[str, Any]]):
    ok = serializers.BooleanField(required=False)
    isin = serializers.CharField(required=False)
    symbol = serializers.CharField(required=False)
    precio = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    moneda = serializers.CharField(required=False)


class FxRateResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(required=False)
    quote_currency = serializers.CharField()
    base_currency = serializers.CharField()
    rate_date = serializers.DateField()
    rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    ok = serializers.BooleanField(required=False)


class InstrumentSerializer(serializers.Serializer[dict[str, Any]]):
    isin = serializers.CharField(required=False)
    symbol = serializers.CharField(required=False)
    ticker = serializers.CharField()
    nombre = serializers.CharField()
    moneda = serializers.CharField()


class FinancialObjectSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.CharField(required=False)
    nombre = serializers.CharField(required=False)
    tipo = serializers.CharField(required=False)
    fecha = serializers.DateField(required=False)
    moneda = serializers.CharField(required=False)
    valor = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    importe = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    aporte = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    tasa = serializers.DecimalField(max_digits=24, decimal_places=12, required=False)


class AccountResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    platform = serializers.CharField()
    type = serializers.CharField()
    currency = serializers.CharField()
    importer_slug = serializers.CharField()
    importer_name = serializers.CharField()


class PortfolioAnalysisItemSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.CharField()
    nombre = serializers.CharField()
    identificador = serializers.CharField()
    clase = serializers.CharField()
    subtipo = serializers.CharField()
    cuenta = serializers.CharField()
    cuenta_id = serializers.CharField()
    plataforma = serializers.CharField()
    valor = serializers.FloatField()
    peso = serializers.FloatField()
    origen = serializers.CharField()


class PortfolioAnalysisResponseSerializer(serializers.Serializer[dict[str, Any]]):
    total = serializers.FloatField()
    items = PortfolioAnalysisItemSerializer(many=True)


class InvestmentPerformanceResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """Canonical performance envelope shared by all traded instrument kinds."""

    range = serializers.CharField()
    account_id = serializers.CharField()
    kind = serializers.CharField()
    moneda_base = serializers.CharField()
    # DRF's Serializer.data property collides with this response field name;
    # keep the public OpenAPI key while narrowing the typing escape hatch here.
    data = cast(Any, serializers.ListField(child=serializers.JSONField()))


class RealEstateResponseSerializer(FinancialObjectSerializer):
    fecha_inicio = serializers.DateField(required=False)
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)
    beneficio_estimado = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    capital_inicial = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    capital_nuevo = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    movimientos = serializers.ListField(required=False)


class ApiObjectSerializer(serializers.Serializer[dict[str, Any]]):
    """Typed fields shared by object responses from legacy-compatible views."""

    id = serializers.CharField(required=False)
    account_id = serializers.CharField(required=False)
    nombre = serializers.CharField(required=False)
    fecha = serializers.DateField(required=False)
    moneda = serializers.CharField(required=False)
    moneda_base = serializers.CharField(required=False)
    valor = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    importe = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    total = serializers.DecimalField(max_digits=24, decimal_places=8, required=False)
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    ok = serializers.BooleanField(required=False)
    results = serializers.JSONField(required=False)


class ApiListSerializer(ApiObjectSerializer):
    """Typed row schema for collection responses."""


class WorkspaceSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()
    base_currency = serializers.CharField()
    role = serializers.CharField()


class UserSessionSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    display_name = serializers.CharField(allow_blank=True)
    role = serializers.CharField()
    language = serializers.CharField()
    preferred_language = serializers.CharField(allow_null=True)
    default_language = serializers.CharField()
    default_crowdfunding_tax_rate = serializers.FloatField()
    summary_sources = serializers.ListField(child=serializers.CharField())
    summary_sources_scope = serializers.CharField()
    default_summary_sources = serializers.ListField(child=serializers.CharField())
    summary_source_keys = serializers.ListField(child=serializers.CharField())
    active_workspace_id = serializers.UUIDField(allow_null=True)
    workspaces = WorkspaceSummarySerializer(many=True)
    csrfToken = serializers.CharField(required=False)


class CsrfSerializer(serializers.Serializer[dict[str, Any]]):
    csrfToken = serializers.CharField()


class OkSerializer(serializers.Serializer[dict[str, Any]]):
    ok = serializers.BooleanField()


class InvitationSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class AdminUserSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    display_name = serializers.CharField(allow_blank=True)
    role = serializers.CharField()
    is_active = serializers.BooleanField()
    is_self = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
