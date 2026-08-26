from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0002_alter_transaction_cash_flow_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="base_currency",
            field=models.CharField(default="EUR", max_length=3),
        ),
        migrations.AddField(
            model_name="transaction",
            name="base_fee",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="base_net_amount",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="base_unit_price",
            field=models.DecimalField(
                blank=True, decimal_places=10, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="fx_rate_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="fx_rate_to_base",
            field=models.DecimalField(
                blank=True, decimal_places=12, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="fx_source",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
