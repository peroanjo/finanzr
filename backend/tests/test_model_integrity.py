from datetime import date

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.db import IntegrityError


@pytest.fixture
def user() -> User:
    return User.objects.create_user(email="owner@example.com", password="secret-value")


@pytest.fixture
def workspace(user: User) -> Workspace:
    workspace = Workspace.objects.create(name="Personal", slug="personal")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER,
    )
    return workspace


@pytest.mark.django_db
def test_workspace_can_be_scoped_through_membership(user: User, workspace: Workspace) -> None:
    other = Workspace.objects.create(name="Ajeno", slug="ajeno")

    visible = Workspace.objects.filter(memberships__user=user)

    assert list(visible) == [workspace]
    assert other not in visible


@pytest.mark.django_db(transaction=True)
def test_membership_is_unique(user: User, workspace: Workspace) -> None:
    with pytest.raises(IntegrityError):
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMembership.Role.VIEWER,
        )


@pytest.mark.django_db(transaction=True)
def test_account_snapshot_has_one_value_per_date(workspace: Workspace) -> None:
    account = Account.objects.create(
        workspace=workspace,
        name="Ahorro",
        kind=Account.Kind.SAVINGS,
    )
    AccountSnapshot.objects.create(account=account, date=date(2026, 7, 1), value=100)

    with pytest.raises(IntegrityError):
        AccountSnapshot.objects.create(account=account, date=date(2026, 7, 1), value=200)
