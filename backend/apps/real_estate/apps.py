from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RealEstateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.real_estate"
    verbose_name = _("Real estate")
