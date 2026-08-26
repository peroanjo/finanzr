from django.db import migrations, models


def use_workspace_currency(apps, schema_editor):
    ManualAsset = apps.get_model("portfolio", "ManualAsset")
    for asset in ManualAsset.objects.select_related("workspace").iterator():
        asset.currency = asset.workspace.base_currency
        asset.save(update_fields=("currency",))


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0003_manualasset_legacy_id_and_more")]

    operations = [
        migrations.RunPython(use_workspace_currency, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="manualasset",
            name="currency",
            field=models.CharField(max_length=3),
        ),
    ]
