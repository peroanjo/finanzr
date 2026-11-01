"""Read-only, bounded GitHub release information for installation administrators."""

from __future__ import annotations

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.users.models import User
from finanzr import __version__

REPOSITORY = "peroanjo/finanzr"
WEB_URL = f"https://github.com/{REPOSITORY}"
API_URL = f"https://api.github.com/repos/{REPOSITORY}"
CACHE_SECONDS = 3600


def github(path: str) -> Any:
    """Use only the canonical public repository; never send credentials or financial data."""
    request = UrlRequest(
        f"{API_URL}/{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Finanzr-version-check"},
    )
    with urlopen(request, timeout=3) as response:  # noqa: S310
        return json.loads(response.read(2_000_000))


def installed_commit() -> str | None:
    """Prefer an embedded build revision, with a source-checkout fallback."""
    revision = os.environ.get("FINANZR_GIT_COMMIT", "")
    if not revision:
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=settings.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=1,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return revision if re.fullmatch(r"[0-9a-fA-F]{40}", revision) else None


def compare(base: str, head: str) -> dict[str, Any]:
    result = github(f"compare/{quote(base, safe='')}...{quote(head, safe='')}?per_page=20")
    return {
        "status": result["status"],
        "ahead_by": result["ahead_by"],
        "behind_by": result["behind_by"],
        "url": f"{WEB_URL}/compare/{quote(base, safe='')}...{quote(head, safe='')}",
        "commits": [
            {
                "sha": row["sha"],
                "message": row["commit"]["message"].splitlines()[0],
                "url": f"{WEB_URL}/commit/{row['sha']}",
            }
            for row in result.get("commits", [])
        ],
    }


def release_on_main(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("draft"):
        return None
    tag = row["tag_name"]
    ancestry = compare(tag, "main")
    if ancestry["status"] not in {"ahead", "identical"}:
        return None
    return {
        "tag": tag,
        "distance_from_main": ancestry["ahead_by"],
        "name": row.get("name") or tag,
        "published_at": row["published_at"],
        "prerelease": row["prerelease"],
        "notes": (row.get("body") or "")[:50000],
        "url": f"{WEB_URL}/releases/tag/{quote(tag, safe='')}",
    }


def build_status(revision: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "installed_version": __version__,
        "installed_commit": revision,
        "comparison_basis": "commit" if revision else "version_tag",
        "repository_url": WEB_URL,
        "checked_at": timezone.now().isoformat(),
        "releases": [],
        "release_status": "unavailable",
        "main": None,
        "release_update": "unknown",
        "latest_release": None,
    }
    base = revision or f"v{__version__}"
    try:
        rows = github("releases?per_page=10")
        with ThreadPoolExecutor(max_workers=4) as executor:
            releases = list(executor.map(release_on_main, rows))
        result["releases"] = sorted(
            (row for row in releases if row is not None),
            key=lambda row: row["published_at"],
            reverse=True,
        )
        result["release_status"] = "available"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        result["main"] = compare(base, "main")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if result["releases"]:
        latest = min(result["releases"], key=lambda row: row["distance_from_main"])
        result["latest_release"] = latest["tag"]
        try:
            comparison = compare(base, latest["tag"])
            result["release_update"] = {
                "ahead": "available",
                "identical": "current",
                "behind": "ahead",
                "diverged": "diverged",
            }.get(comparison["status"], "unknown")
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return result


@api_view(["GET"])
def version_status(request: Request) -> Response:
    if getattr(request.user, "role", None) != User.Role.ADMIN:
        return Response({"error": _("Insufficient permissions")}, status=403)
    revision = installed_commit()
    key = f"installation-version:{__version__}:{revision}"
    result = cache.get(key)
    if result is None:
        result = build_status(revision)
        cache.set(key, result, CACHE_SECONDS)
    return Response(result)
