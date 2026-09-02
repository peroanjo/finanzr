from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0004_manual_asset_reporting_currency")]

    operations = [
        migrations.RemoveConstraint(
            model_name="manualasset",
            name="manual_asset_legacy_id_unique",
        ),
        migrations.RemoveField(
            model_name="manualasset",
            name="legacy_id",
        ),
    ]
