from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("market_data", "0002_initial")]

    operations = [
        migrations.AddField(
            model_name="instrument",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        )
    ]
