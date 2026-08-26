"""i18n compatibility for importer consumers."""

from __future__ import annotations


def gettext(message: str) -> str:
    """Translate through Django when configured, otherwise return the source text."""

    try:
        from django.core.exceptions import ImproperlyConfigured
        from django.utils.translation import gettext as django_gettext
    except ModuleNotFoundError:
        return message
    try:
        return django_gettext(message)
    except ImproperlyConfigured:
        return message


def gettext_noop(message: str) -> str:
    """Mark static catalog metadata without resolving it at import time."""

    return message
