from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from apps.common.models import default_summary_sources_value


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0003_installationsettings_default_crowdfunding_tax_rate"),
        ("users", "0004_alter_user_options_alter_user_display_name_and_more"),
        ("workspaces", "0003_alter_workspaceinvitation_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="installationsettings",
            name="default_summary_sources",
            field=models.JSONField(
                default=default_summary_sources_value,
                verbose_name="default summary sources",
            ),
        ),
        migrations.CreateModel(
            name="SummaryPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "included_sources",
                    models.JSONField(
                        default=list,
                        verbose_name="included summary sources",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="summary_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="summary_preferences",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "summary preference",
                "verbose_name_plural": "summary preferences",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "workspace"),
                        name="summary_preference_user_workspace_unique",
                    )
                ],
            },
        ),
    ]
