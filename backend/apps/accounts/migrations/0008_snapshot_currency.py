from django.db import migrations, models


def copy_snapshot_currency(apps, schema_editor):
    AccountSnapshot = apps.get_model("accounts", "AccountSnapshot")
    AccountSnapshot.objects.filter(currency="").update(currency="EUR")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_snapshot_currency_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountsnapshot",
            name="currency",
            field=models.CharField(default="EUR", max_length=3),
        ),
        migrations.RunPython(copy_snapshot_currency, migrations.RunPython.noop),
    ]
