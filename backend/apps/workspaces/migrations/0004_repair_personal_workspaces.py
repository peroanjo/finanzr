from django.db import migrations


def repair_personal_workspaces(apps, schema_editor):
    User = apps.get_model("users", "User")
    Workspace = apps.get_model("workspaces", "Workspace")
    WorkspaceMembership = apps.get_model("workspaces", "WorkspaceMembership")
    WorkspaceInvitation = apps.get_model("workspaces", "WorkspaceInvitation")
    AuditEvent = apps.get_model("audit", "AuditEvent")

    created_events = {
        event.object_id: event.workspace_id
        for event in AuditEvent.objects.filter(
            event_type="user.created",
            object_type="user",
            object_id__isnull=False,
        ).order_by("created_at")
    }

    for user in User.objects.all().iterator():
        memberships = WorkspaceMembership.objects.filter(user_id=user.id)
        buggy_workspace_id = created_events.get(user.id)
        owns_workspace = memberships.filter(role="owner").exists()

        if not owns_workspace:
            base_currency = "EUR"
            if buggy_workspace_id is not None:
                base_currency = (
                    Workspace.objects.filter(id=buggy_workspace_id)
                    .values_list("base_currency", flat=True)
                    .first()
                    or base_currency
                )
            workspace, _created = Workspace.objects.get_or_create(
                slug=f"personal-{user.id.hex}",
                defaults={
                    "name": user.display_name.strip() or user.email,
                    "base_currency": base_currency,
                },
            )
            WorkspaceMembership.objects.update_or_create(
                workspace_id=workspace.id,
                user_id=user.id,
                defaults={"role": "owner"},
            )

        explicitly_shared = (
            buggy_workspace_id is not None
            and WorkspaceInvitation.objects.filter(
                workspace_id=buggy_workspace_id,
                accepted_at__isnull=False,
            ).exists()
            and AuditEvent.objects.filter(
                workspace_id=buggy_workspace_id,
                actor_id=user.id,
                event_type="api.post",
                object_type="/api/workspaces/invitations/accept",
                metadata__status=200,
            ).exists()
        )
        if buggy_workspace_id is not None and not explicitly_shared:
            WorkspaceMembership.objects.filter(
                workspace_id=buggy_workspace_id,
                user_id=user.id,
                role="editor",
            ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0002_initial"),
        ("users", "0004_alter_user_options_alter_user_display_name_and_more"),
        ("workspaces", "0003_alter_workspaceinvitation_role_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_personal_workspaces, migrations.RunPython.noop),
    ]
