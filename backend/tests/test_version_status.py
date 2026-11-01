from collections.abc import Iterator
from typing import Any
from unittest.mock import patch
from urllib.parse import quote

import pytest
from apps.api import version_status as module
from apps.users.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from finanzr import __version__


@pytest.fixture(autouse=True)
def clear_version_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
@pytest.mark.parametrize("role", [User.Role.USER, User.Role.DEMO])
def test_non_administrators_cannot_check_versions(role: str) -> None:
    user = User.objects.create_user(email="reader@example.com", password="synthetic", role=role)
    client = APIClient()
    client.force_authenticate(user)
    with patch.object(module, "github") as remote:
        assert client.get("/api/installation/version").status_code == 403
        remote.assert_not_called()


@pytest.mark.django_db
def test_anonymous_cannot_check_versions() -> None:
    with patch.object(module, "github") as remote:
        assert APIClient().get("/api/installation/version").status_code in {401, 403}
        remote.assert_not_called()


def release(tag: str = "v2.0.0", **overrides: Any) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "name": "Synthetic release",
        "body": "# Changes\n\n<script>synthetic</script>",
        "published_at": "2026-01-01T00:00:00Z",
        "prerelease": False,
        "draft": False,
        **overrides,
    }


def comparison(status: str = "ahead", count: int = 2) -> dict[str, Any]:
    return {
        "status": status,
        "ahead_by": count,
        "behind_by": 0,
        "commits": [{"sha": "a" * 40, "commit": {"message": "Synthetic change\n\nDetails"}}],
    }


@pytest.mark.django_db
def test_admin_receives_releases_comparison_and_cached_results() -> None:
    user = User.objects.create_user(
        email="admin@example.com", password="synthetic", role=User.Role.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user)

    def remote(path: str) -> Any:
        if path == "releases?per_page=10":
            return [release(prerelease=True), release("v-feature"), release("v-draft", draft=True)]
        if path.startswith("compare/v-feature..."):
            return comparison("diverged")
        return comparison()

    with (
        patch.object(module, "github", side_effect=remote) as github,
        patch.object(module, "installed_commit", return_value="b" * 40),
        patch.object(module, "installed_branch", return_value="dev"),
    ):
        response = client.get("/api/installation/version")
        assert response.status_code == 200
        body = response.json()
        assert [row["tag"] for row in body["releases"]] == ["v2.0.0"]
        assert body["releases"][0]["prerelease"] is True
        assert body["releases"][0]["notes"].startswith("# Changes")
        assert body["installed_branch"] == "dev"
        assert body["release_update"] == "available"
        assert body["branch_comparison"]["ahead_by"] == 2
        assert body["branch_comparison"]["commits"][0]["message"] == "Synthetic change"
        count = github.call_count
        assert client.get("/api/installation/version").json() == body
        assert github.call_count == count


def test_provider_failure_preserves_installed_version_and_unknown_status() -> None:
    with patch.object(module, "github", side_effect=OSError("unavailable")):
        body = module.build_status(None, "dev")
    assert body["installed_version"] == __version__
    assert body["comparison_basis"] == "version_tag"
    assert body["release_status"] == "unavailable"
    assert body["release_update"] == "unknown"
    assert body["branch_comparison"] is None


@pytest.mark.parametrize(
    ("remote_status", "expected"),
    [
        ("ahead", "available"),
        ("identical", "current"),
        ("behind", "ahead"),
        ("diverged", "diverged"),
    ],
)
def test_release_state_uses_ancestry_instead_of_version_string_order(
    remote_status: str, expected: str
) -> None:
    def remote(path: str) -> Any:
        if path.startswith("releases?"):
            return [release()]
        if path.startswith("compare/v2.0.0...dev"):
            return comparison()
        return comparison(remote_status)

    with patch.object(module, "github", side_effect=remote):
        assert module.build_status("b" * 40, "dev")["release_update"] == expected


def test_branch_comparison_still_available_when_releases_fail() -> None:
    def remote(path: str) -> Any:
        if path.startswith("releases?"):
            raise OSError("rate limit")
        return comparison("identical", 0)

    with patch.object(module, "github", side_effect=remote):
        body = module.build_status(None, "dev")
    assert body["branch_comparison"]["status"] == "identical"
    assert body["release_status"] == "unavailable"


def test_embedded_revision_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANZR_GIT_COMMIT", "a" * 40)
    assert module.installed_commit() == "a" * 40
    monkeypatch.setenv("FINANZR_GIT_COMMIT", "invalid/revision")
    assert module.installed_commit() is None


def test_republishing_older_tag_does_not_hide_newer_release() -> None:
    def remote(path: str) -> Any:
        if path.startswith("releases?"):
            return [
                release("v1.0.0", published_at="2026-02-01T00:00:00Z"),
                release("v2.0.0", published_at="2026-01-01T00:00:00Z"),
            ]
        if path.startswith("compare/v1.0.0...dev"):
            return comparison("ahead", 20)
        if path.startswith("compare/v2.0.0...dev"):
            return comparison("ahead", 2)
        if path.startswith("compare/" + "b" * 40 + "...v2.0.0"):
            return comparison("ahead", 10)
        return comparison("identical", 0)

    with patch.object(module, "github", side_effect=remote):
        result = module.build_status("b" * 40, "dev")
    assert result["releases"][0]["tag"] == "v1.0.0"
    assert result["release_update"] == "available"
    assert result["latest_release"] == "v2.0.0"


def test_unknown_branch_does_not_silently_query_main() -> None:
    with patch.object(module, "github") as remote:
        result = module.build_status("b" * 40, None)
    assert result["installed_branch"] is None
    assert result["branch_comparison"] is None
    assert result["release_update"] == "unknown"
    remote.assert_not_called()


@pytest.mark.parametrize("branch", ["dev", "feature/synthetic-update"])
def test_all_ancestry_checks_use_installed_branch(branch: str) -> None:
    paths: list[str] = []

    def remote(path: str) -> Any:
        paths.append(path)
        return [release()] if path.startswith("releases?") else comparison()

    with patch.object(module, "github", side_effect=remote):
        result = module.build_status("b" * 40, branch)
    assert f"compare/v2.0.0...{quote(branch, safe='')}?per_page=20" in paths
    assert f"compare/{'b' * 40}...{quote(branch, safe='')}?per_page=20" in paths
    assert result["installed_branch"] == branch
    assert not any("main" in path for path in paths)


def test_branch_detection_and_detached_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FINANZR_GIT_BRANCH", raising=False)
    with patch.object(module, "git_value", return_value="dev"):
        assert module.installed_branch() == "dev"
    with patch.object(module, "git_value", return_value=None):
        assert module.installed_branch() is None
    monkeypatch.setenv("FINANZR_GIT_BRANCH", "feature/synthetic")
    with patch.object(module, "git_value") as git:
        assert module.installed_branch() == "feature/synthetic"
        git.assert_not_called()
    monkeypatch.setenv("FINANZR_GIT_BRANCH", "../invalid")
    assert module.installed_branch() is None


@pytest.mark.django_db
def test_switching_branch_does_not_reuse_cached_status() -> None:
    user = User.objects.create_user(email="admin@example.com", password="synthetic", role="admin")
    client = APIClient()
    client.force_authenticate(user)
    with (
        patch.object(module, "installed_commit", return_value="b" * 40),
        patch.object(module, "installed_branch", side_effect=["dev", "main"]),
        patch.object(
            module,
            "build_status",
            side_effect=lambda revision, branch: {"installed_branch": branch},
        ) as build,
    ):
        assert client.get("/api/installation/version").json()["installed_branch"] == "dev"
        assert client.get("/api/installation/version").json()["installed_branch"] == "main"
        assert build.call_count == 2
