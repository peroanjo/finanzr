from typing import Any

from django.db import migrations


def rename_kraken_provider(apps: Any, schema_editor: Any) -> None:
    provider_model = apps.get_model("accounts", "FinancialProvider")
    account_model = apps.get_model("accounts", "Account")
    provider_model.objects.filter(slug="kraken").update(name="KrakenPro")
    account_model.objects.filter(
        kind="crypto", provider_label__iexact="Kraken"
    ).update(provider_label="KrakenPro")


def restore_kraken_provider(apps: Any, schema_editor: Any) -> None:
    provider_model = apps.get_model("accounts", "FinancialProvider")
    account_model = apps.get_model("accounts", "Account")
    provider_model.objects.filter(slug="kraken").update(name="Kraken")
    account_model.objects.filter(
        kind="crypto", provider_label__iexact="KrakenPro"
    ).update(provider_label="Kraken")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_seed_financial_providers")]

    operations = [
        migrations.RunPython(rename_kraken_provider, restore_kraken_provider),
    ]
