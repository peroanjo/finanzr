from uuid import uuid4

from django.core.cache import cache
from django.db import transaction

CACHE_EPOCH_KEY = "investment-cache:epoch:v1"


def cache_epoch() -> str:
    """Return the shared cache-aside epoch, creating a persistent marker if needed."""
    epoch = cache.get(CACHE_EPOCH_KEY)
    if epoch is None:
        candidate = uuid4().hex
        cache.add(CACHE_EPOCH_KEY, candidate, timeout=None)
        epoch = cache.get(CACHE_EPOCH_KEY, candidate)
    return str(epoch)


def _advance_cache_epoch() -> None:
    """Publish a new epoch as one atomic cache value replacement."""
    cache.set(CACHE_EPOCH_KEY, uuid4().hex, timeout=None)


def invalidate_cache() -> None:
    """Invalidate derived cache entries after the surrounding transaction commits."""
    transaction.on_commit(_advance_cache_epoch)
