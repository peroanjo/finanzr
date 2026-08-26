from django.db import migrations, models


def bind_existing_importers(apps, schema_editor):
    Account = apps.get_model("accounts", "Account")
    for account in Account.objects.select_related("provider"):
        provider = account.provider.name if account.provider_id else account.provider_label
        normalized = provider.strip().casefold()
        slug = ""
        if account.kind == "funds" and ("myinvestor" in normalized or "inversis" in normalized):
            slug = "fund_broker"
        elif account.kind == "stocks" and "trade republic" in normalized:
            slug = "trade_republic"
        elif account.kind == "crypto" and "kraken" in normalized:
            slug = "kraken_spot"
        if slug:
            account.importer_slug = slug
            account.save(update_fields=("importer_slug",))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_rename_kraken_provider")]

    operations = [
        migrations.AddField(
            model_name="account",
            name="importer_slug",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.RunPython(bind_existing_importers, migrations.RunPython.noop),
    ]
