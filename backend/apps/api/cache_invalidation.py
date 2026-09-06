from django.core.cache import cache
from django.db import transaction


def invalidate_cache() -> None:
    """Clear derived cache entries after the surrounding transaction commits."""
    transaction.on_commit(cache.clear)
