from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from apps.api.cache_invalidation import (
    CACHE_EPOCH_KEY,
    _advance_cache_epoch,
    cache_epoch,
    invalidate_cache,
)
from django.core.cache.backends.filebased import FileBasedCache
from django.db import transaction

_FILE_CACHE_PROCESS = """
import sys
from django.core.cache.backends.filebased import FileBasedCache

cache = FileBasedCache(sys.argv[1], {"TIMEOUT": 3600})
key = "workspace:synthetic"
action = sys.argv[2]
if action == "set":
    cache.set(key, "synthetic-value")
    print("set")
elif action == "get":
    print(cache.get(key, "missing"))
elif action == "clear":
    cache.clear()
    print("cleared")
else:
    raise SystemExit(f"unknown action: {action}")
"""


def _run_file_cache_process(directory: str, action: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", _FILE_CACHE_PROCESS, directory, action],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.mark.django_db(transaction=True)
def test_invalidation_is_immediate_after_commit_and_discarded_on_rollback() -> None:
    with patch("apps.api.cache_invalidation._advance_cache_epoch") as advance:
        invalidate_cache()
        advance.assert_called_once_with()

        advance.reset_mock()
        with transaction.atomic():
            invalidate_cache()
            advance.assert_not_called()
        advance.assert_called_once_with()

        advance.reset_mock()
        with pytest.raises(RuntimeError, match="synthetic rollback"):
            with transaction.atomic():
                invalidate_cache()
                raise RuntimeError("synthetic rollback")
        advance.assert_not_called()


def test_epoch_marker_is_persistent_and_publication_uses_atomic_replacement() -> None:
    with patch("apps.api.cache_invalidation.cache") as cache_mock:
        cache_mock.get.return_value = None
        cache_mock.get.side_effect = [None, "synthetic-epoch"]
        cache_mock.add.return_value = True

        assert cache_epoch() == "synthetic-epoch"
        cache_mock.add.assert_called_once()
        assert cache_mock.add.call_args.kwargs["timeout"] is None

        _advance_cache_epoch()
        cache_mock.set.assert_called_once()
        assert cache_mock.set.call_args.args[0] == CACHE_EPOCH_KEY
        assert cache_mock.set.call_args.kwargs["timeout"] is None


def test_file_cache_is_visible_and_invalidated_between_processes() -> None:
    with tempfile.TemporaryDirectory(prefix="finanzr-cache-") as directory:
        cache_directory = str(Path(directory) / "cache")
        assert _run_file_cache_process(cache_directory, "set") == "set"
        assert _run_file_cache_process(cache_directory, "get") == "synthetic-value"
        assert _run_file_cache_process(cache_directory, "clear") == "cleared"
        assert _run_file_cache_process(cache_directory, "get") == "missing"
        assert stat.S_IMODE(Path(cache_directory).stat().st_mode) == 0o700


def test_old_cache_aside_write_is_hidden_after_epoch_publication() -> None:
    with tempfile.TemporaryDirectory(prefix="finanzr-cache-epoch-") as directory:
        cache_backend = FileBasedCache(directory, {"TIMEOUT": 3600})
        base_key = "investment-performance:v2:synthetic-workspace:stock:all:1y:EUR:saveback=0"
        old_epoch = "epoch-before-mutation"
        new_epoch = "epoch-after-mutation"
        cache_backend.set(CACHE_EPOCH_KEY, old_epoch, timeout=None)

        old_key = f"{base_key}:epoch={old_epoch}"
        new_key = f"{base_key}:epoch={new_epoch}"
        cache_backend.set(CACHE_EPOCH_KEY, new_epoch, timeout=None)
        # A GET that started before the mutation may finish its write afterwards.
        cache_backend.set(old_key, {"data": ["stale-after-mutation"]}, timeout=3600)

        assert cache_backend.get(CACHE_EPOCH_KEY) == new_epoch
        assert cache_backend.get(new_key) is None
        assert cache_backend.get(old_key) == {"data": ["stale-after-mutation"]}
