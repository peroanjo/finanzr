import uuid
from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    class Language(models.TextChoices):
        SPANISH = "es-ES", _("Spanish")
        ENGLISH = "en", _("English")

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrator")
        USER = "user", _("User")
        DEMO = "demo", _("Demo")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # type: ignore[assignment]
    email = models.EmailField("email", unique=True)
    display_name = models.CharField(_("display name"), max_length=120, blank=True)
    role = models.CharField(
        _("account role"), max_length=10, choices=Role.choices, default=Role.USER
    )
    language = models.CharField(
        _("preferred language"),
        max_length=5,
        choices=Language.choices,
        blank=True,
        default="",
        help_text=_("Leave it empty to use the installation default language."),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            models.UniqueConstraint(Lower("email"), name="users_email_ci_unique"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email
