from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market_data", "0006_fx_rates_and_quote_currency"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="fxrate",
            old_name="market_data_fx_quote_6b5a7d_idx",
            new_name="market_data_fx_quote_6b5a7d_ix",
        ),
    ]
