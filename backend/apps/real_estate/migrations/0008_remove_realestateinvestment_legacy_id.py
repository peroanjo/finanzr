from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("real_estate", "0007_realestatecashflow_withholding_rate")]

    operations = [
        migrations.RemoveConstraint(
            model_name="realestateinvestment",
            name="real_estate_legacy_id_unique",
        ),
        migrations.RemoveField(
            model_name="realestateinvestment",
            name="legacy_id",
        ),
    ]
