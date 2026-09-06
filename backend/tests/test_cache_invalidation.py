from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from apps.api.cache_invalidation import invalidate_cache
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
    with patch("apps.api.cache_invalidation.cache.clear") as clear:
        invalidate_cache()
        clear.assert_called_once_with()

        clear.reset_mock()
        with transaction.atomic():
            invalidate_cache()
            clear.assert_not_called()
        clear.assert_called_once_with()

        clear.reset_mock()
        with pytest.raises(RuntimeError, match="synthetic rollback"):
            with transaction.atomic():
                invalidate_cache()
                raise RuntimeError("synthetic rollback")
        clear.assert_not_called()


def test_file_cache_is_visible_and_invalidated_between_processes() -> None:
    with tempfile.TemporaryDirectory(prefix="finanzr-cache-") as directory:
        cache_directory = str(Path(directory) / "cache")
        assert _run_file_cache_process(cache_directory, "set") == "set"
        assert _run_file_cache_process(cache_directory, "get") == "synthetic-value"
        assert _run_file_cache_process(cache_directory, "clear") == "cleared"
        assert _run_file_cache_process(cache_directory, "get") == "missing"
        assert stat.S_IMODE(Path(cache_directory).stat().st_mode) == 0o700
