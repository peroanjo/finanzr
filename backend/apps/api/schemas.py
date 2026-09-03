"""OpenAPI serializers for the API's stable JSON envelopes."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class ApiErrorSerializer(serializers.Serializer[dict[str, Any]]):
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)


class ApiPayloadSerializer(serializers.Serializer[dict[str, Any]]):
    """Common request fields accepted by legacy-shaped non-transaction endpoints."""

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


class InstrumentIdentifierRequestSerializer(StrictSerializer):
    """Native identifier input; the route supplies the instrument kind."""

    scheme = serializers.ChoiceField(choices=("isin", "yahoo", "crypto_symbol", "kraken", "other"))
    # Blank is only meaningful for a fund update, where it explicitly clears
    # the selected Yahoo ticker. The contextual validator rejects it for all
    # other operations and schemes.
    value = serializers.CharField(required=True, allow_blank=True, max_length=120)
    venue = serializers.CharField(required=False, allow_blank=True, max_length=40, default="")
    is_primary = serializers.BooleanField(required=False, default=False)


INSTRUMENT_IDENTIFIER_SCHEMES: dict[str, frozenset[str]] = {
    "fund": frozenset({"isin", "yahoo", "other"}),
    "stock": frozenset({"isin", "yahoo", "other"}),
    "etf": frozenset({"isin", "yahoo", "other"}),
    "crypto": frozenset({"crypto_symbol", "yahoo", "kraken", "other"}),
}
INSTRUMENT_REQUIRED_SCHEME = {
    "fund": "isin",
    "stock": "isin",
    "etf": "isin",
    "crypto": "crypto_symbol",
}


def normalize_instrument_identifier_value(scheme: str, value: str) -> str:
    value = value.strip()
    if scheme in {"isin", "crypto_symbol", "kraken"}:
        return value.upper()
    return value


def validate_instrument_identifiers(
    attrs: dict[str, Any],
    *,
    kind: str | None,
    require_identity: bool,
    allow_fund_blank_yahoo: bool = False,
) -> dict[str, Any]:
    identifiers = attrs.get("identifiers")
    if identifiers is None or kind is None:
        return attrs
    normalized = [
        {
            **item,
            "value": normalize_instrument_identifier_value(item["scheme"], item["value"]),
            "venue": item.get("venue", "").strip(),
        }
        for item in identifiers
    ]
    allowed = INSTRUMENT_IDENTIFIER_SCHEMES.get(kind, frozenset())
    invalid = sorted({item["scheme"] for item in normalized} - allowed)
    if invalid:
        raise serializers.ValidationError(
            {
                "identifiers": [
                    _("Identifier scheme(s) are not valid for this instrument kind: %(schemes)s")
                    % {"schemes": ", ".join(invalid)}
                ]
            }
        )
    for item in normalized:
        if not item["value"] and not (
            kind == "fund"
            and item["scheme"] == "yahoo"
            and (allow_fund_blank_yahoo or not require_identity)
        ):
            raise serializers.ValidationError(
                {"identifiers": [_("Identifier values cannot be blank")]}
            )
    if len({(item["scheme"], item["venue"]) for item in normalized}) != len(normalized):
        raise serializers.ValidationError(
            {"identifiers": [_("Only one identifier per scheme and venue is supported")]}
        )
    primary_counts: dict[str, int] = {}
    for item in normalized:
        if item["is_primary"]:
            primary_counts[item["scheme"]] = primary_counts.get(item["scheme"], 0) + 1
    if any(count > 1 for count in primary_counts.values()):
        raise serializers.ValidationError(
            {"identifiers": [_("Only one primary identifier per scheme is supported")]}
        )
    required = INSTRUMENT_REQUIRED_SCHEME.get(kind)
    if require_identity and required:
        canonical = [
            item
            for item in normalized
            if item["scheme"] == required and item["venue"] == "" and item["value"]
        ]
        if len(canonical) != 1:
            raise serializers.ValidationError(
                {
                    "identifiers": [
                        _(
                            "Exactly one canonical %(scheme)s identifier at the "
                            "default venue is required"
                        )
                        % {"scheme": required}
                    ]
                }
            )
    attrs["identifiers"] = normalized
    return attrs


class InstrumentRequestSerializer(StrictSerializer):
    """Strict native instrument create fields.

    Identifiers are deliberately explicit so the API can validate the
    required identity scheme for the route's kind without exposing storage
    metadata or the historical Spanish field names.
    """

    name = serializers.CharField(required=True, allow_blank=False, max_length=240)
    quote_currency = serializers.CharField(required=False, default="EUR", max_length=3)
    identifiers = InstrumentIdentifierRequestSerializer(many=True, required=True, allow_empty=False)
    asset_class = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    subtype = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=120
    )
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        name = attrs.get("name")
        if name is not None:
            attrs["name"] = name.strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": [_("This field may not be blank.")]})
        return validate_instrument_identifiers(
            attrs, kind=self.context.get("instrument_kind"), require_identity=True
        )


class InstrumentUpdateRequestSerializer(StrictSerializer):
    """Strict native instrument update fields addressed by UUID."""

    name = serializers.CharField(required=False, allow_blank=False, max_length=240)
    quote_currency = serializers.CharField(required=False, max_length=3)
    identifiers = InstrumentIdentifierRequestSerializer(
        many=True, required=False, allow_empty=False
    )
    asset_class = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    subtype = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=120
    )
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        name = attrs.get("name")
        if name is not None:
            attrs["name"] = name.strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": [_("This field may not be blank.")]})
        return validate_instrument_identifiers(
            attrs, kind=self.context.get("instrument_kind"), require_identity=False
        )


# Keep kind-specific names for the explicit OpenAPI mapper.  Validation of
# identifier schemes is performed at the view boundary because the kind comes
# from the collection route, not from the request body.
class IsinInstrumentRequestSerializer(InstrumentRequestSerializer):
    pass


class CryptoInstrumentRequestSerializer(InstrumentRequestSerializer):
    pass


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


class RealEstateMovementRequestSerializer(StrictSerializer):
    id = serializers.UUIDField(required=False)
    flow_type = serializers.ChoiceField(choices=("capital_return", "profit"))
    effective_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=24, decimal_places=8, min_value=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True, max_length=240)


class RealEstateRequestSerializer(StrictSerializer):
    name = serializers.CharField(required=True, allow_blank=False, max_length=200)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=160)
    status = serializers.ChoiceField(
        choices=("active", "completed", "defaulted", "cancelled"), required=False
    )
    start_date = serializers.DateField(required=True)
    maturity_date = serializers.DateField(required=False, allow_null=True)
    expected_profit = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, allow_null=True
    )
    expected_irr_percent = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    expected_term_months = serializers.IntegerField(required=False, min_value=0)
    origin = serializers.CharField(required=False, allow_blank=True, max_length=160)
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    )
    initial_capital = serializers.DecimalField(
        max_digits=24, decimal_places=8, min_value=Decimal("0")
    )
    new_capital = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, min_value=Decimal("0")
    )
    movements = RealEstateMovementRequestSerializer(many=True, required=False)


class RealEstateUpdateRequestSerializer(RealEstateRequestSerializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=200)
    start_date = serializers.DateField(required=False)
    initial_capital = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, min_value=Decimal("0")
    )


class BudgetRowSerializer(serializers.Serializer[dict[str, Any]]):
    categoria = serializers.CharField(required=True)
    cantidad = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    tipo = serializers.CharField(required=True)


class BudgetRequestSerializer(BudgetRowSerializer):
    pass


TRANSACTION_OPERATION_TYPES = ("buy", "sell", "transfer_in", "transfer_out")
TRANSACTION_CASH_FLOW_TYPES = ("contribution", "withdrawal", "internal", "none")


class TransactionRequestSerializer(StrictSerializer):
    trade_date = serializers.DateField(required=True)
    settlement_date = serializers.DateField(required=False, allow_null=True)
    operation_type = serializers.ChoiceField(choices=TRANSACTION_OPERATION_TYPES, required=True)
    quantity = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    net_amount = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    fee = serializers.DecimalField(
        max_digits=24, decimal_places=8, required=False, default=Decimal("0")
    )
    account_id = serializers.UUIDField(required=True)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=4)
    fx_rate_to_base = serializers.DecimalField(
        max_digits=24, decimal_places=12, required=False, allow_null=True
    )
    fx_rate_date = serializers.DateField(required=False, allow_null=True)
    fx_source = serializers.CharField(required=False, allow_blank=True, max_length=40)
    market = serializers.CharField(required=False, allow_blank=True, max_length=80)


class FundTransactionRequestSerializer(TransactionRequestSerializer):
    isin = serializers.CharField(required=True)
    unit_price = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class StockTransactionRequestSerializer(TransactionRequestSerializer):
    isin = serializers.CharField(required=True)
    unit_price = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)
    is_saveback = serializers.BooleanField(required=False)


class CryptoTransactionRequestSerializer(TransactionRequestSerializer):
    symbol = serializers.CharField(required=True)
    unit_price = serializers.DecimalField(max_digits=24, decimal_places=8, required=True)


class FundTransactionUpdateRequestSerializer(FundTransactionRequestSerializer):
    pass


class StockTransactionUpdateRequestSerializer(StockTransactionRequestSerializer):
    pass


class CryptoTransactionUpdateRequestSerializer(CryptoTransactionRequestSerializer):
    pass


class StockSplitRequestSerializer(StrictSerializer):
    instrument_id = serializers.UUIDField(required=True)
    effective_date = serializers.DateField(required=True)
    ratio = serializers.DecimalField(max_digits=24, decimal_places=12, required=True)
    source = serializers.CharField(
        required=False, allow_blank=False, max_length=120, default="manual"
    )  # type: ignore[assignment]

    def validate_ratio(self, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise serializers.ValidationError(_("Ratio must be finite and greater than zero."))
        return value


class StockSplitResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    instrument_id = serializers.UUIDField()
    effective_date = serializers.DateField()
    ratio = serializers.DecimalField(max_digits=24, decimal_places=12, coerce_to_string=False)
    source = serializers.CharField()  # type: ignore[assignment]


class PriceRequestSerializer(StrictSerializer):
    """Native workspace price override request addressed by instrument UUID."""

    close = serializers.DecimalField(max_digits=24, decimal_places=10, required=True)
    currency = serializers.CharField(required=False, max_length=4, allow_blank=False)


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
    id = serializers.UUIDField()
    account_id = serializers.UUIDField()
    account_name = serializers.CharField()
    platform = serializers.CharField()
    asset_name = serializers.CharField()
    trade_date = serializers.DateField()
    settlement_date = serializers.DateField(allow_null=True)
    operation_type = serializers.ChoiceField(choices=TRANSACTION_OPERATION_TYPES)
    cash_flow_type = serializers.ChoiceField(choices=TRANSACTION_CASH_FLOW_TYPES)
    quantity = serializers.FloatField()
    unit_price = serializers.FloatField()
    net_amount = serializers.FloatField()
    fee = serializers.FloatField()
    currency = serializers.CharField()
    base_currency = serializers.CharField()
    base_unit_price = serializers.FloatField(allow_null=True)
    base_net_amount = serializers.FloatField(allow_null=True)
    base_fee = serializers.FloatField(allow_null=True)
    fx_rate_to_base = serializers.FloatField(allow_null=True)
    fx_rate_date = serializers.DateField(allow_null=True)
    fx_source = serializers.CharField()
    market = serializers.CharField()
    provider_operation_type = serializers.CharField(allow_blank=True)


class FundTransactionResponseSerializer(TransactionResponseSerializer):
    isin = serializers.CharField()


class StockTransactionResponseSerializer(TransactionResponseSerializer):
    isin = serializers.CharField()
    is_saveback = serializers.BooleanField()


class CryptoTransactionResponseSerializer(TransactionResponseSerializer):
    symbol = serializers.CharField()


class PriceResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    instrument_id = serializers.UUIDField()
    quoted_at = serializers.DateTimeField()
    close = serializers.DecimalField(max_digits=24, decimal_places=10, coerce_to_string=False)
    currency = serializers.CharField()
    base_close = serializers.DecimalField(max_digits=24, decimal_places=10, coerce_to_string=False)
    base_currency = serializers.CharField()
    fx_rate_to_base = serializers.DecimalField(
        max_digits=24, decimal_places=12, coerce_to_string=False
    )
    fx_rate_date = serializers.DateField()
    fx_source = serializers.CharField()
    source = serializers.CharField()  # type: ignore[assignment]


class PriceFetchResultSerializer(serializers.Serializer[dict[str, Any]]):
    instrument_id = serializers.UUIDField()
    base_close = serializers.DecimalField(
        max_digits=24, decimal_places=10, allow_null=True, coerce_to_string=False
    )
    close = serializers.DecimalField(
        max_digits=24, decimal_places=10, allow_null=True, coerce_to_string=False
    )
    currency = serializers.CharField(allow_null=True)
    ticker = serializers.CharField(allow_null=True)
    error = serializers.CharField(allow_null=True)


class PriceFetchResponseSerializer(serializers.Serializer[dict[str, Any]]):
    results = PriceFetchResultSerializer(many=True)


class FundChartPointSerializer(serializers.Serializer[dict[str, Any]]):
    date = serializers.DateField()
    close = serializers.DecimalField(max_digits=24, decimal_places=6, coerce_to_string=False)


class MarketChartPointSerializer(serializers.Serializer[dict[str, Any]]):
    date = serializers.DateField()
    open = serializers.DecimalField(max_digits=24, decimal_places=6, coerce_to_string=False)
    high = serializers.DecimalField(max_digits=24, decimal_places=6, coerce_to_string=False)
    low = serializers.DecimalField(max_digits=24, decimal_places=6, coerce_to_string=False)
    close = serializers.DecimalField(max_digits=24, decimal_places=6, coerce_to_string=False)


class FundChartResponseSerializer(serializers.Serializer[dict[str, Any]]):
    instrument_id = serializers.UUIDField()
    ticker = serializers.CharField()
    currency = serializers.CharField()
    base_currency = serializers.CharField()
    range = serializers.CharField()
    data = FundChartPointSerializer(many=True)  # type: ignore[assignment]


class MarketChartResponseSerializer(serializers.Serializer[dict[str, Any]]):
    instrument_id = serializers.UUIDField()
    ticker = serializers.CharField()
    currency = serializers.CharField()
    base_currency = serializers.CharField()
    range = serializers.CharField()
    data = MarketChartPointSerializer(many=True)  # type: ignore[assignment]


class FxRateResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(required=False)
    quote_currency = serializers.CharField()
    base_currency = serializers.CharField()
    rate_date = serializers.DateField()
    rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    ok = serializers.BooleanField(required=False)


class InstrumentIdentifierResponseSerializer(serializers.Serializer[dict[str, Any]]):
    scheme = serializers.ChoiceField(choices=("isin", "yahoo", "crypto_symbol", "kraken", "other"))
    value = serializers.CharField()
    venue = serializers.CharField()
    is_primary = serializers.BooleanField()


class InstrumentSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=("fund", "stock", "etf", "crypto"))
    name = serializers.CharField()
    quote_currency = serializers.CharField()
    identifiers = InstrumentIdentifierResponseSerializer(many=True)
    asset_class = serializers.CharField(allow_null=True)
    subtype = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


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


class RealEstateMovementResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    flow_type = serializers.ChoiceField(choices=("capital_return", "profit"))
    effective_date = serializers.DateField(allow_null=True)
    amount = serializers.DecimalField(max_digits=24, decimal_places=8)
    note = serializers.CharField()
    applied_tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)


class RealEstateResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    platform = serializers.CharField()
    status = serializers.ChoiceField(choices=("active", "completed", "defaulted", "cancelled"))
    initial_capital = serializers.DecimalField(max_digits=24, decimal_places=8)
    new_capital = serializers.DecimalField(max_digits=24, decimal_places=8)
    returned_capital = serializers.DecimalField(max_digits=24, decimal_places=8)
    realized_profit = serializers.DecimalField(max_digits=24, decimal_places=8)
    net_realized_profit = serializers.DecimalField(max_digits=24, decimal_places=8)
    expected_profit = serializers.DecimalField(max_digits=24, decimal_places=8, allow_null=True)
    net_expected_profit = serializers.DecimalField(max_digits=24, decimal_places=8)
    expected_irr_percent = serializers.DecimalField(max_digits=12, decimal_places=6)
    expected_term_months = serializers.IntegerField()
    start_date = serializers.DateField()
    maturity_date = serializers.DateField(allow_null=True)
    return_date = serializers.DateField(allow_null=True)
    movements = RealEstateMovementResponseSerializer(many=True)
    origin = serializers.CharField()
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    currency = serializers.CharField()


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
