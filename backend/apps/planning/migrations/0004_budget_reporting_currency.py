from django.db import migrations, models


def use_workspace_currency(apps, schema_editor):
    BudgetLine = apps.get_model("planning", "BudgetLine")
    for line in BudgetLine.objects.select_related("workspace").iterator():
        line.currency = line.workspace.base_currency
        line.save(update_fields=("currency",))


class Migration(migrations.Migration):
    dependencies = [("planning", "0003_allocationrule_legacy_id_and_more")]

    operations = [
        migrations.AddField(
            model_name="budgetline",
            name="currency",
            field=models.CharField(default="EUR", max_length=3),
            preserve_default=False,
        ),
        migrations.RunPython(use_workspace_currency, migrations.RunPython.noop),
    ]
