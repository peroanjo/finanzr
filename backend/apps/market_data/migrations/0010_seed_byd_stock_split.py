from datetime import date
from decimal import Decimal
from typing import Any

from django.db import migrations

BYD_ISIN = "CNE100000296"
BYD_EFFECTIVE_DATE = date(2025, 6, 10)
BYD_RATIO = Decimal("3")
BYD_SOURCE = "migration:canonical-byd-2025-06-10"


def seed_byd_stock_split(apps: Any, schema_editor: Any) -> None:
    """Seed the confirmed BYD split only where the instrument is workspace-visible."""
    InstrumentIdentifier = apps.get_model("market_data", "InstrumentIdentifier")
    StockSplit = apps.get_model("market_data", "StockSplit")
    WorkspaceInstrument = apps.get_model("market_data", "WorkspaceInstrument")
    Transaction = apps.get_model("transactions", "Transaction")

    instrument_ids = InstrumentIdentifier.objects.filter(
        scheme="isin",
        value=BYD_ISIN,
        venue="",
        instrument__kind="stock",
    ).values_list("instrument_id", flat=True)
    for instrument_id in instrument_ids:
        workspace_ids = set(
            WorkspaceInstrument.objects.filter(instrument_id=instrument_id).values_list(
                "workspace_id", flat=True
            )
        )
        workspace_ids.update(
            Transaction.objects.filter(instrument_id=instrument_id).values_list(
                "account__workspace_id", flat=True
            )
        )
        for workspace_id in workspace_ids:
            StockSplit.objects.get_or_create(
                workspace_id=workspace_id,
                instrument_id=instrument_id,
                effective_date=BYD_EFFECTIVE_DATE,
                defaults={"ratio": BYD_RATIO, "source": BYD_SOURCE},
            )


def reverse_byd_stock_split(apps: Any, schema_editor: Any) -> None:
    """Keep seeded rows on reverse because users may have edited them."""


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_snapshot_currency"),
        ("market_data", "0009_native_market_prices"),
        ("transactions", "0004_transaction_quote_currency_length"),
        ("workspaces", "0004_repair_personal_workspaces"),
    ]

    operations = [
        migrations.RunPython(seed_byd_stock_split, reverse_byd_stock_split),
    ]
