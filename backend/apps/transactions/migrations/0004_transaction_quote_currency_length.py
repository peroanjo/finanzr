from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transactions", "0003_transaction_currency_snapshot")]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="currency",
            field=models.CharField(default="EUR", max_length=4),
        )
    ]
