import uuid
from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def copy_manual_rates(apps: Any, schema_editor: Any) -> None:
    FxRate = apps.get_model("market_data", "FxRate")
    WorkspaceFxOverride = apps.get_model("market_data", "WorkspaceFxOverride")
    Workspace = apps.get_model("workspaces", "Workspace")
    workspaces = list(Workspace.objects.all())
    for rate in FxRate.objects.filter(source="manual"):
        for workspace in workspaces:
            WorkspaceFxOverride.objects.get_or_create(
                workspace=workspace,
                quote_currency=rate.quote_currency,
                base_currency=rate.base_currency,
                rate_date=rate.rate_date,
                defaults={"rate": rate.rate, "source": "manual"},
            )
    FxRate.objects.filter(source="manual").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("market_data", "0007_rename_fx_rate_index"),
        ("workspaces", "0003_alter_workspaceinvitation_role_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceFxOverride",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quote_currency", models.CharField(max_length=3)),
                ("base_currency", models.CharField(max_length=3)),
                ("rate_date", models.DateField()),
                ("rate", models.DecimalField(decimal_places=12, max_digits=24)),
                ("source", models.CharField(default="manual", max_length=40)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fx_overrides",
                        to="workspaces.workspace",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="workspacefxoverride",
            constraint=models.UniqueConstraint(
                fields=("workspace", "quote_currency", "base_currency", "rate_date"),
                name="workspace_fx_override_pair_date_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspacefxoverride",
            constraint=models.CheckConstraint(
                condition=models.Q(("rate__gt", 0)), name="workspace_fx_override_positive"
            ),
        ),
        migrations.AddIndex(
            model_name="workspacefxoverride",
            index=models.Index(
                fields=["workspace", "quote_currency", "base_currency", "-rate_date"],
                name="workspace_fx_pair_date_ix",
            ),
        ),
        migrations.RunPython(copy_manual_rates, migrations.RunPython.noop),
    ]
