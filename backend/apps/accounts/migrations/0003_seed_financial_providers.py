import uuid
from typing import Any

from django.db import migrations


PROVIDERS = (
    ("abanca", "Abanca", "bank", "https://www.abanca.com/"),
    ("renault-bank", "Renault Bank", "bank", "https://renaultbank.es/"),
    ("myinvestor", "MyInvestor", "broker", "https://myinvestor.es/"),
    ("trade-republic", "Trade Republic", "broker", "https://traderepublic.com/"),
    ("revolut", "Revolut", "broker", "https://www.revolut.com/"),
    ("kraken", "Kraken", "exchange", "https://www.kraken.com/"),
    ("urbanitae", "Urbanitae", "real_estate", "https://urbanitae.com/"),
    ("wecity", "WeCity", "real_estate", "https://www.wecity.com/"),
    ("civislend", "Civislend", "real_estate", "https://www.civislend.com/"),
)


def seed_providers(apps: Any, schema_editor: Any) -> None:
    provider_model = apps.get_model("accounts", "FinancialProvider")
    for slug, name, provider_type, website in PROVIDERS:
        provider, created = provider_model.objects.get_or_create(
            slug=slug,
            defaults={
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"https://finanzr.dev/providers/{slug}"),
                "name": name,
                "provider_type": provider_type,
                "website": website,
                "is_active": True,
            },
        )
        if not created:
            provider.name = name
            provider.provider_type = provider_type
            provider.website = website
            provider.is_active = True
            provider.save(update_fields=("name", "provider_type", "website", "is_active"))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]

    operations = [migrations.RunPython(seed_providers, migrations.RunPython.noop)]
