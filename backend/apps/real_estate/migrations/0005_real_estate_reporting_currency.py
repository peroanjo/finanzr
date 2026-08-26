from django.db import migrations, models


def use_workspace_currency(apps, schema_editor):
    Investment = apps.get_model("real_estate", "RealEstateInvestment")
    for investment in Investment.objects.select_related("workspace").iterator():
        investment.currency = investment.workspace.base_currency
        investment.save(update_fields=("currency",))


class Migration(migrations.Migration):
    dependencies = [("real_estate", "0004_alter_realestatecashflow_flow_type_and_more")]

    operations = [
        migrations.AddField(
            model_name="realestateinvestment",
            name="currency",
            field=models.CharField(default="EUR", max_length=3),
            preserve_default=False,
        ),
        migrations.RunPython(use_workspace_currency, migrations.RunPython.noop),
    ]
