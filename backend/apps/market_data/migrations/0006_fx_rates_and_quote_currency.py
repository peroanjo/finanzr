import uuid

from django.db import migrations, models


def copy_quote_currency(apps, schema_editor):
    Instrument = apps.get_model("market_data", "Instrument")
    Transaction = apps.get_model("transactions", "Transaction")
    MarketPrice = apps.get_model("market_data", "MarketPrice")

    for instrument in Instrument.objects.all().iterator():
        currency = (
            Transaction.objects.filter(instrument_id=instrument.pk)
            .exclude(currency="")
            .values_list("currency", flat=True)
            .first()
            or MarketPrice.objects.filter(instrument_id=instrument.pk)
            .exclude(currency="")
            .values_list("currency", flat=True)
            .first()
            or "EUR"
        )
        currency = str(currency).upper()[:3]
        instrument.quote_currency = currency
        instrument.save(update_fields=["quote_currency"])


class Migration(migrations.Migration):
    dependencies = [
        ("market_data", "0005_alter_instrument_kind_and_more"),
        ("transactions", "0003_transaction_currency_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="instrument",
            name="quote_currency",
            field=models.CharField(default="EUR", max_length=3),
        ),
        migrations.CreateModel(
            name="FxRate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quote_currency", models.CharField(max_length=3)),
                ("base_currency", models.CharField(max_length=3)),
                ("rate_date", models.DateField()),
                ("rate", models.DecimalField(decimal_places=12, max_digits=24)),
                ("source", models.CharField(max_length=40)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("quote_currency", "base_currency", "rate_date", "source"),
                        name="fx_rate_pair_date_source_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("rate__gt", 0)),
                        name="fx_rate_positive",
                    ),
                ],
                "indexes": [
                    models.Index(
                        fields=("quote_currency", "base_currency", "-rate_date"),
                        name="market_data_fx_quote_6b5a7d_idx",
                    )
                ],
            },
        ),
        migrations.RunPython(copy_quote_currency, migrations.RunPython.noop),
    ]
