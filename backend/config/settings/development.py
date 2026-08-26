from .base import *  # noqa: F403

DEBUG = True

if env_bool("DJANGO_USE_SQLITE"):  # noqa: F405
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BACKEND_DIR / "db.sqlite3",  # noqa: F405
        }
    }
