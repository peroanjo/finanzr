from django.db import migrations, models


def classify_existing_users(apps, schema_editor):
    user_model = apps.get_model("users", "User")
    user_model.objects.filter(email__iexact="demo@finanzr.local").update(role="demo")
    user_model.objects.filter(is_staff=True).exclude(role="demo").update(role="admin")
    if not user_model.objects.filter(role="admin").exists():
        first_user = (
            user_model.objects.filter(is_active=True)
            .exclude(role="demo")
            .order_by("date_joined")
            .first()
        )
        if first_user:
            first_user.role = "admin"
            first_user.save(update_fields=("role",))


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Administrador"),
                    ("user", "Usuario"),
                    ("demo", "Demo"),
                ],
                default="user",
                max_length=10,
                verbose_name="rol de cuenta",
            ),
        ),
        migrations.RunPython(classify_existing_users, migrations.RunPython.noop),
    ]
