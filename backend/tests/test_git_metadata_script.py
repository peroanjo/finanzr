"""Verify build metadata forwarding without starting deployment services."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy/version.sh"


def metadata(checkout: Path, **overrides: str) -> list[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"FINANZR_GIT_COMMIT", "FINANZR_GIT_BRANCH"}
    }
    environment.update(overrides)
    return subprocess.check_output(
        [
            "sh",
            "-c",
            '. "$1"; finanzr_load_git_metadata; '
            'printf "%s\\n%s\\n" "$FINANZR_GIT_BRANCH" "$FINANZR_GIT_COMMIT"',
            "metadata",
            str(SCRIPT),
        ],
        cwd=checkout,
        env=environment,
        text=True,
    ).splitlines()


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "dev", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "Synthetic build",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


def test_script_detects_branch_and_full_commit(checkout: Path) -> None:
    branch, revision = metadata(checkout)
    assert branch == "dev"
    assert (
        revision
        == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    )


def test_detached_build_preserves_explicit_branch(checkout: Path) -> None:
    subprocess.run(["git", "checkout", "--detach"], cwd=checkout, check=True, capture_output=True)
    assert metadata(checkout)[0] == ""
    assert metadata(checkout, FINANZR_GIT_BRANCH="release/synthetic")[0] == "release/synthetic"


def test_source_archive_has_no_assumed_branch(tmp_path: Path) -> None:
    assert metadata(tmp_path) == ["", ""]
