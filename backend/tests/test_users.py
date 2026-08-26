import pytest
from apps.users.models import User
from django.db import IntegrityError


@pytest.mark.django_db
def test_user_uses_normalized_email_as_login() -> None:
    user = User.objects.create_user(email=" Persona@Example.COM ", password="secret-value")

    assert user.email == "persona@example.com"
    assert user.username is None
    assert user.check_password("secret-value")
    assert user.role == User.Role.USER


@pytest.mark.django_db
def test_create_superuser_sets_required_flags() -> None:
    user = User.objects.create_superuser(email="admin@example.com", password="secret-value")

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.role == User.Role.ADMIN


@pytest.mark.django_db(transaction=True)
def test_email_is_unique_case_insensitively() -> None:
    User.objects.create_user(email="same@example.com", password="secret-value")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="SAME@example.com", password="secret-value")
