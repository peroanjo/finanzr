from django.contrib import admin

from .models import Workspace, WorkspaceMembership


class MembershipInline(admin.TabularInline):  # type: ignore[type-arg]
    model = WorkspaceMembership
    extra = 0


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "base_currency", "archived_at")
    search_fields = ("name", "slug")
    inlines = (MembershipInline,)


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("workspace", "user", "role", "created_at")
    list_filter = ("role",)
    autocomplete_fields = ("workspace", "user")
