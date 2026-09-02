from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Account, AccountSnapshot, FinancialProvider
from apps.audit.models import AuditEvent
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceInstrument,
)
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership

DEMO_EMAIL = "demo@finanzr.local"
DEMO_PASSWORD = "finanzr-demo-local"
DEMO_WORKSPACE_SLUG = "demo"

MONTH_ENDS = [
    date(2025, 8, 31),
    date(2025, 9, 30),
    date(2025, 10, 31),
    date(2025, 11, 30),
    date(2025, 12, 31),
    date(2026, 1, 31),
    date(2026, 2, 28),
    date(2026, 3, 31),
    date(2026, 4, 30),
    date(2026, 5, 31),
    date(2026, 6, 30),
    date(2026, 7, 31),
]


def money(value: Any) -> Decimal:
    return Decimal(str(value))


class Command(BaseCommand):
    help = "Create or regenerate an isolated demo user with synthetic financial data"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", default=DEMO_EMAIL)
        parser.add_argument("--password", default=DEMO_PASSWORD)

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        email = str(options["email"]).strip().lower()
        password = str(options["password"])
        if len(password) < 12:
            raise ValueError("The demo password must be at least 12 characters long")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"display_name": "Usuario demo"},
        )
        user.display_name = "Usuario demo"
        user.role = User.Role.DEMO
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()

        self._remove_previous_workspace()
        workspace = Workspace.objects.create(
            name="Demo Finanzr",
            slug=DEMO_WORKSPACE_SLUG,
            base_currency="EUR",
            timezone="Europe/Madrid",
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMembership.Role.OWNER,
        )

        providers = self._providers()
        self._seed_savings(workspace, providers)
        self._seed_manual_balances(workspace, providers)
        self._seed_market_portfolio(workspace, providers)
        self._seed_real_estate(workspace, providers)
        ManualAsset.objects.create(
            workspace=workspace,
            provider_label="Cooperativa local",
            name="Participación energética",
            asset_class="Alternativos",
            subtype="Cooperativa renovable",
            value=money("2750"),
            currency=workspace.base_currency,
            valued_at=date(2026, 7, 29),
        )

        self.stdout.write(self.style.SUCCESS("Demo workspace regenerated with synthetic data."))
        self.stdout.write(f"Email: {email}")
        self.stdout.write(f"Password: {password}")

    def _remove_previous_workspace(self) -> None:
        workspace = Workspace.objects.filter(slug=DEMO_WORKSPACE_SLUG).first()
        if not workspace:
            return
        Transaction.objects.filter(account__workspace=workspace).delete()
        AccountSnapshot.objects.filter(account__workspace=workspace).delete()
        Account.objects.filter(workspace=workspace).delete()
        RealEstateCashFlow.objects.filter(investment__workspace=workspace).delete()
        RealEstateInvestment.objects.filter(workspace=workspace).delete()
        ManualAsset.objects.filter(workspace=workspace).delete()
        WorkspaceInstrument.objects.filter(workspace=workspace).delete()
        AuditEvent.objects.filter(workspace=workspace).delete()
        workspace.delete()

    def _providers(self) -> dict[str, FinancialProvider]:
        definitions = {
            "bank": ("banco-horizonte-demo", "Banco Horizonte · Demo", "bank"),
            "broker": ("broker-orbita-demo", "Broker Órbita · Demo", "broker"),
            "funds": ("gestora-norte-demo", "Gestora Norte · Demo", "broker"),
            "crypto": ("exchange-polar-demo", "Exchange Polar · Demo", "exchange"),
            "real_estate": ("inmobiliaria-faro-demo", "Faro Crowdfunding · Demo", "real_estate"),
        }
        result = {}
        for key, (slug, name, provider_type) in definitions.items():
            result[key], _ = FinancialProvider.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "provider_type": provider_type,
                    "is_active": True,
                },
            )
        return result

    def _account(
        self,
        workspace: Workspace,
        *,
        kind: str,
        legacy_id: int,
        name: str,
        provider: FinancialProvider,
        subtype: str,
    ) -> Account:
        return Account.objects.create(
            workspace=workspace,
            provider=provider,
            name=name,
            kind=kind,
            subtype=subtype,
            currency="EUR",
            external_id=f"legacy:{kind}:{legacy_id}",
        )

    def _snapshots(
        self,
        account: Account,
        values: Sequence[float],
        contributions: Sequence[float],
        earnings: Sequence[float],
    ) -> None:
        for closed_at, value, contribution, result in zip(
            MONTH_ENDS, values, contributions, earnings, strict=True
        ):
            AccountSnapshot.objects.create(
                account=account,
                date=closed_at,
                value=money(value),
                contribution=money(contribution),
                earnings=money(result),
            )

    def _seed_savings(
        self,
        workspace: Workspace,
        providers: dict[str, FinancialProvider],
    ) -> None:
        current = self._account(
            workspace,
            kind=Account.Kind.SAVINGS,
            legacy_id=1,
            name="Cuenta diaria",
            provider=providers["bank"],
            subtype="Cuenta corriente",
        )
        remunerated = self._account(
            workspace,
            kind=Account.Kind.SAVINGS,
            legacy_id=2,
            name="Colchón remunerado",
            provider=providers["bank"],
            subtype="Cuenta remunerada",
        )
        cash = self._account(
            workspace,
            kind=Account.Kind.SAVINGS,
            legacy_id=3,
            name="Efectivo",
            provider=providers["bank"],
            subtype="Efectivo",
        )
        self._snapshots(
            current,
            [2100, 2450, 2380, 2710, 2600, 2940, 3180, 3020, 3350, 3490, 3650, 3820],
            [0, 350, -70, 330, -110, 340, 240, -160, 330, 140, 160, 170],
            [0] * 12,
        )
        self._snapshots(
            remunerated,
            [8200, 8420, 8650, 8870, 9100, 9340, 9580, 9820, 10100, 10420, 10850, 11230],
            [0, 205, 210, 200, 210, 220, 220, 220, 260, 300, 410, 355],
            [12, 15, 20, 20, 20, 20, 20, 20, 20, 20, 20, 25],
        )
        self._snapshots(
            cash,
            [320, 300, 280, 350, 370, 340, 390, 410, 380, 420, 440, 450],
            [0, -20, -20, 70, 20, -30, 50, 20, -30, 40, 20, 10],
            [0] * 12,
        )

    def _seed_manual_balances(
        self,
        workspace: Workspace,
        providers: dict[str, FinancialProvider],
    ) -> None:
        definitions = [
            (
                1,
                "Cartera indexada",
                providers["funds"],
                "Fondos indexados",
                [9300, 9450, 9700, 9920, 10150, 10380, 10540, 10820, 10980, 11250, 11600, 12019],
                [0, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150],
            ),
            (
                2,
                "Acciones y ETF",
                providers["broker"],
                "Broker",
                [3700, 3820, 3990, 4120, 4250, 4400, 4530, 4690, 4780, 4900, 5020, 5111],
                [0, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            ),
            (
                3,
                "Crypto",
                providers["crypto"],
                "Exchange",
                [2600, 2800, 3100, 2950, 3400, 3650, 3900, 4200, 3850, 4100, 4320, 4480],
                [0, 75, 75, 75, 75, 75, 75, 75, 75, 75, 75, 75],
            ),
        ]
        for legacy_id, name, provider, subtype, values, contributions in definitions:
            account = self._account(
                workspace,
                kind=Account.Kind.MANUAL_INVESTMENT,
                legacy_id=legacy_id,
                name=name,
                provider=provider,
                subtype=subtype,
            )
            earnings = [0.0]
            earnings.extend(
                round(values[index] - values[index - 1] - contributions[index], 2)
                for index in range(1, len(values))
            )
            self._snapshots(account, values, contributions, earnings)

    def _instrument(
        self,
        workspace: Workspace,
        *,
        kind: str,
        name: str,
        scheme: str,
        identifier: str,
        yahoo: str,
        metadata: dict[str, str] | None = None,
    ) -> Instrument:
        identity = (
            InstrumentIdentifier.objects.select_related("instrument")
            .filter(
                scheme=scheme,
                value=identifier,
                venue="",
            )
            .first()
        )
        if identity:
            instrument = identity.instrument
            if instrument.kind != kind:
                raise ValueError(f"{identifier} already belongs to another asset type")
        else:
            instrument = Instrument.objects.create(
                kind=kind,
                name=name,
                base_currency="EUR",
                metadata=metadata or {},
            )
            InstrumentIdentifier.objects.create(
                instrument=instrument,
                scheme=scheme,
                value=identifier,
                venue="",
                is_primary=True,
            )
        WorkspaceInstrument.objects.get_or_create(workspace=workspace, instrument=instrument)
        if (
            yahoo
            and not InstrumentIdentifier.objects.filter(
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                value=yahoo,
                venue="",
            ).exists()
        ):
            InstrumentIdentifier.objects.create(
                instrument=instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                value=yahoo,
                venue="",
            )
        return instrument

    def _price(self, instrument: Instrument, value: str) -> None:
        MarketPrice.objects.update_or_create(
            instrument=instrument,
            granularity=MarketPrice.Granularity.SPOT,
            source="demo",
            defaults={
                "quoted_at": timezone.now(),
                "close": money(value),
                "currency": "EUR",
            },
        )

    def _buy(
        self,
        account: Account,
        instrument: Instrument,
        *,
        external_id: str,
        traded_at: date,
        net_amount: str,
        unit_price: str,
        provider_type: str,
    ) -> None:
        amount = money(net_amount)
        price = money(unit_price)
        quantity = (amount / price).quantize(money("0.000000000000000001"))
        Transaction.objects.create(
            account=account,
            instrument=instrument,
            external_id=external_id,
            trade_date=traded_at,
            settlement_date=traded_at,
            operation_type=Transaction.OperationType.BUY,
            cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
            quantity=quantity,
            unit_price=price,
            net_amount=amount,
            fee=money("0"),
            currency="EUR",
            provider_operation_type=provider_type,
            raw_metadata={"legacy_name": instrument.name, "demo": True},
        )

    def _seed_market_portfolio(
        self,
        workspace: Workspace,
        providers: dict[str, FinancialProvider],
    ) -> None:
        funds = self._account(
            workspace,
            kind=Account.Kind.FUNDS,
            legacy_id=1,
            name="Cartera indexada",
            provider=providers["funds"],
            subtype="Fondos indexados",
        )
        stocks = self._account(
            workspace,
            kind=Account.Kind.STOCKS,
            legacy_id=1,
            name="Broker principal",
            provider=providers["broker"],
            subtype="Acciones y ETF",
        )
        crypto = self._account(
            workspace,
            kind=Account.Kind.CRYPTO,
            legacy_id=1,
            name="Cuenta crypto",
            provider=providers["crypto"],
            subtype="Spot",
        )

        global_fund = self._instrument(
            workspace,
            kind=Instrument.Kind.FUND,
            name="Indexado global",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="IE00B03HCZ61",
            yahoo="",
            metadata={"asset_class": "Renta Variable", "subtype": "Global"},
        )
        bond_fund = self._instrument(
            workspace,
            kind=Instrument.Kind.FUND,
            name="Bonos euro",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="IE00B18GC888",
            yahoo="",
            metadata={"asset_class": "Renta Fija", "subtype": "Euro"},
        )
        sp500_fund = self._instrument(
            workspace,
            kind=Instrument.Kind.FUND,
            name="Fidelity S&P 500",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="IE00BYX5MX67",
            yahoo="0P0001CLDM.F",
            metadata={"asset_class": "Renta Variable", "subtype": "Estados Unidos"},
        )
        emerging_fund = self._instrument(
            workspace,
            kind=Instrument.Kind.FUND,
            name="Vanguard Mercados Emergentes",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="IE0031786142",
            yahoo="0P000060MS.F",
            metadata={"asset_class": "Renta Variable", "subtype": "Emergentes"},
        )
        apple = self._instrument(
            workspace,
            kind=Instrument.Kind.STOCK,
            name="Apple",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="US0378331005",
            yahoo="AAPL",
        )
        world_etf = self._instrument(
            workspace,
            kind=Instrument.Kind.STOCK,
            name="ETF MSCI World",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="IE00B4L5Y983",
            yahoo="EUNL.DE",
        )
        microsoft = self._instrument(
            workspace,
            kind=Instrument.Kind.STOCK,
            name="Microsoft",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="US5949181045",
            yahoo="MSFT",
        )
        inditex = self._instrument(
            workspace,
            kind=Instrument.Kind.STOCK,
            name="Inditex",
            scheme=InstrumentIdentifier.Scheme.ISIN,
            identifier="ES0148396007",
            yahoo="ITX.MC",
        )
        bitcoin = self._instrument(
            workspace,
            kind=Instrument.Kind.CRYPTO,
            name="Bitcoin",
            scheme=InstrumentIdentifier.Scheme.CRYPTO_SYMBOL,
            identifier="BTC",
            yahoo="BTC-EUR",
        )
        ethereum = self._instrument(
            workspace,
            kind=Instrument.Kind.CRYPTO,
            name="Ethereum",
            scheme=InstrumentIdentifier.Scheme.CRYPTO_SYMBOL,
            identifier="ETH",
            yahoo="ETH-EUR",
        )

        # Yahoo quotes from 2026-07-30, converted to EUR where needed.
        for instrument, value in [
            (global_fund, "61.4591"),
            (bond_fund, "99.3291"),
            (sp500_fund, "16.111"),
            (emerging_fund, "289.578"),
            (apple, "294.631128"),
            (world_etf, "123.48"),
            (microsoft, "391.23903"),
            (inditex, "57.48"),
            (bitcoin, "56201.97"),
            (ethereum, "1670.35"),
        ]:
            self._price(instrument, value)

        # Historical Yahoo closes in EUR. Apple uses the same day's USD/EUR rate.
        # The amount stays round and determines the number of units.
        purchases = [
            (
                funds,
                global_fund,
                "demo:fund:global:1",
                date(2025, 8, 15),
                "4000",
                "51.4138984680",
                "SUSCRIPCION",
            ),
            (
                funds,
                global_fund,
                "demo:fund:global:2",
                date(2026, 5, 12),
                "4610",
                "58.8935012817",
                "SUSCRIPCION",
            ),
            (
                funds,
                bond_fund,
                "demo:fund:bond:1",
                date(2025, 11, 10),
                "1440",
                "100.3751983643",
                "SUSCRIPCION",
            ),
            (
                funds,
                bond_fund,
                "demo:fund:bond:2",
                date(2026, 4, 8),
                "1255",
                "99.9937973022",
                "SUSCRIPCION",
            ),
            (
                funds,
                sp500_fund,
                "demo:fund:sp500:1",
                date(2025, 10, 15),
                "1400",
                "14.0843000412",
                "SUSCRIPCION",
            ),
            (
                funds,
                sp500_fund,
                "demo:fund:sp500:2",
                date(2026, 4, 15),
                "1200",
                "14.6714000702",
                "SUSCRIPCION",
            ),
            (
                funds,
                emerging_fund,
                "demo:fund:emerging:1",
                date(2025, 12, 15),
                "1200",
                "240.4282989502",
                "SUSCRIPCION",
            ),
            (
                funds,
                emerging_fund,
                "demo:fund:emerging:2",
                date(2026, 6, 15),
                "1000",
                "315.8327026367",
                "SUSCRIPCION",
            ),
            (
                stocks,
                apple,
                "demo:stock:apple:1",
                date(2025, 9, 18),
                "1260",
                "201.7460337064",
                "Compra",
            ),
            (
                stocks,
                apple,
                "demo:stock:apple:2",
                date(2026, 5, 20),
                "960",
                "259.9924197346",
                "Compra",
            ),
            (
                stocks,
                world_etf,
                "demo:stock:world:1",
                date(2025, 10, 6),
                "1260",
                "109.2399978638",
                "Compra",
            ),
            (
                stocks,
                world_etf,
                "demo:stock:world:2",
                date(2026, 5, 6),
                "1204",
                "119.5699996948",
                "Compra",
            ),
            (
                stocks,
                microsoft,
                "demo:stock:microsoft:1",
                date(2025, 11, 18),
                "1500",
                "426.0272160230",
                "Compra",
            ),
            (
                stocks,
                microsoft,
                "demo:stock:microsoft:2",
                date(2026, 4, 20),
                "900",
                "354.7658479794",
                "Compra",
            ),
            (
                stocks,
                inditex,
                "demo:stock:inditex:1",
                date(2025, 12, 3),
                "1100",
                "53.4199981689",
                "Compra",
            ),
            (
                stocks,
                inditex,
                "demo:stock:inditex:2",
                date(2026, 6, 3),
                "800",
                "53.4599990845",
                "Compra",
            ),
            (
                crypto,
                bitcoin,
                "demo:crypto:btc:1",
                date(2025, 12, 12),
                "1360",
                "76868.4140625",
                "Compra",
            ),
            (
                crypto,
                bitcoin,
                "demo:crypto:btc:2",
                date(2026, 6, 9),
                "1090",
                "53440.2265625",
                "Compra",
            ),
            (
                crypto,
                ethereum,
                "demo:crypto:eth:1",
                date(2026, 1, 16),
                "920",
                "2840.3762207031",
                "Compra",
            ),
            (
                crypto,
                ethereum,
                "demo:crypto:eth:2",
                date(2026, 4, 17),
                "830",
                "2056.5480957031",
                "Compra",
            ),
        ]
        for (
            account,
            instrument,
            external_id,
            traded_at,
            amount,
            price,
            provider_type,
        ) in purchases:
            self._buy(
                account,
                instrument,
                external_id=external_id,
                traded_at=traded_at,
                net_amount=amount,
                unit_price=price,
                provider_type=provider_type,
            )

    def _seed_real_estate(
        self,
        workspace: Workspace,
        providers: dict[str, FinancialProvider],
    ) -> None:
        active = RealEstateInvestment.objects.create(
            workspace=workspace,
            provider=providers["real_estate"],
            name="Residencial Valencia",
            status=RealEstateInvestment.Status.ACTIVE,
            start_date=date(2026, 2, 15),
            maturity_date=date(2027, 2, 15),
            expected_profit=money("315"),
            expected_irr=money("0.078"),
            expected_term_months=12,
            origin="Aportación demo",
            currency=workspace.base_currency,
        )
        completed = RealEstateInvestment.objects.create(
            workspace=workspace,
            provider=providers["real_estate"],
            name="Rehabilitación Bilbao",
            status=RealEstateInvestment.Status.COMPLETED,
            start_date=date(2025, 3, 10),
            maturity_date=date(2026, 3, 10),
            expected_profit=money("210"),
            expected_irr=money("0.07"),
            expected_term_months=12,
            origin="Aportación demo",
            currency=workspace.base_currency,
        )
        RealEstateCashFlow.objects.bulk_create(
            [
                RealEstateCashFlow(
                    investment=active,
                    effective_date=active.start_date,
                    flow_type=RealEstateCashFlow.FlowType.CONTRIBUTION,
                    amount=money("5000"),
                    is_external=True,
                    source_note="Capital demo",
                ),
                RealEstateCashFlow(
                    investment=completed,
                    effective_date=completed.start_date,
                    flow_type=RealEstateCashFlow.FlowType.CONTRIBUTION,
                    amount=money("3000"),
                    is_external=True,
                    source_note="Capital demo",
                ),
                RealEstateCashFlow(
                    investment=completed,
                    effective_date=completed.maturity_date,
                    flow_type=RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                    amount=money("3000"),
                    source_note="Devolución demo",
                ),
                RealEstateCashFlow(
                    investment=completed,
                    effective_date=completed.maturity_date,
                    flow_type=RealEstateCashFlow.FlowType.PROFIT,
                    amount=money("210"),
                    source_note="Beneficio demo",
                ),
            ]
        )
