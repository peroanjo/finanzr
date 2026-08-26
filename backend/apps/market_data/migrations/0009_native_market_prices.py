import uuid
from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def move_manual_prices(apps: Any, schema_editor: Any) -> None:
    MarketPrice = apps.get_model("market_data", "MarketPrice")
    WorkspaceMarketPriceOverride = apps.get_model(
        "market_data", "WorkspaceMarketPriceOverride"
    )
    Workspace = apps.get_model("workspaces", "Workspace")
    workspaces = list(Workspace.objects.all())
    for price in MarketPrice.objects.filter(source="manual"):
        for workspace in workspaces:
            WorkspaceMarketPriceOverride.objects.update_or_create(
                workspace=workspace,
                instrument=price.instrument,
                defaults={
                    "quoted_at": price.quoted_at,
                    "close": price.close,
                    "currency": price.currency,
                    "source": "manual",
                },
            )
    MarketPrice.objects.filter(source="manual").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("market_data", "0008_workspace_fx_overrides"),
        ("workspaces", "0003_alter_workspaceinvitation_role_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceMarketPriceOverride",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quoted_at", models.DateTimeField()),
                ("close", models.DecimalField(decimal_places=10, max_digits=24)),
                ("currency", models.CharField(max_length=4)),
                ("source", models.CharField(default="manual", max_length=40)),
                (
                    "instrument",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_price_overrides",
                        to="market_data.instrument",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="market_price_overrides",
                        to="workspaces.workspace",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="workspacemarketpriceoverride",
            constraint=models.UniqueConstraint(
                fields=("workspace", "instrument"),
                name="workspace_market_price_override_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspacemarketpriceoverride",
            constraint=models.CheckConstraint(
                condition=models.Q(("close__gte", 0)),
                name="workspace_market_price_close_nonnegative",
            ),
        ),
        migrations.AddIndex(
            model_name="workspacemarketpriceoverride",
            index=models.Index(
                fields=["workspace", "instrument", "-quoted_at"],
                name="workspace_market_price_ix",
            ),
        ),
        migrations.RunPython(move_manual_prices, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="marketprice",
            name="market_price_eur_nonnegative",
        ),
        migrations.RemoveField(model_name="marketprice", name="fx_rate_to_eur"),
        migrations.RemoveField(model_name="marketprice", name="price_eur"),
    ]
