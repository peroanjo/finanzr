from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_alter_account_kind_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountsnapshot",
            name="base_contribution",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="base_currency",
            field=models.CharField(default="EUR", max_length=3),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="base_earnings",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="base_value",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="fx_rate_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="fx_rate_to_base",
            field=models.DecimalField(
                blank=True, decimal_places=12, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="accountsnapshot",
            name="fx_source",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
