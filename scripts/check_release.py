#!/usr/bin/env python3
"""Validate version and reproducibility metadata before creating a release."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?\Z")
REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?")
LOCKED = re.compile(r"^([A-Za-z0-9_.-]+)==([^ \\;]+)")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_requirements(path: Path) -> set[str]:
    result: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            result.update(direct_requirements(path.parent / line[3:].strip()))
            continue
        match = REQUIREMENT.match(line)
        if match:
            result.add(normalized(match.group(1)))
    return result


def locked_requirements(path: Path) -> set[str]:
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LOCKED.match(line)
        if match:
            result.add(normalized(match.group(1)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="also require this tag to match v<VERSION>")
    args = parser.parse_args()
    errors: list[str] = []

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        errors.append(f"VERSION is not a supported SemVer value: {version!r}")

    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    observed = {
        "frontend/package.json": package.get("version"),
        "frontend/package-lock.json": package_lock.get("version"),
        "frontend/package-lock.json packages['']": package_lock.get("packages", {})
        .get("", {})
        .get("version"),
    }
    for source, value in observed.items():
        if value != version:
            errors.append(f"{source} has version {value!r}; expected {version!r}")

    settings = (ROOT / "backend/config/settings/base.py").read_text(encoding="utf-8")
    if '"VERSION": __version__' not in settings:
        errors.append("OpenAPI does not read its version from finanzr.__version__")
    build_info = (ROOT / "frontend/src/buildInfo.ts").read_text(encoding="utf-8")
    if "VITE_FINANZR_VERSION" not in build_info:
        errors.append("the frontend does not expose VITE_FINANZR_VERSION")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        errors.append(f"CHANGELOG.md has no release heading for {version}")
    release_notes = ROOT / ".github/release-notes" / f"{version}.md"
    if not release_notes.exists():
        errors.append(f"missing release notes: {release_notes.relative_to(ROOT)}")

    for source, lock in (("base.txt", "base.lock"), ("dev.txt", "dev.lock")):
        source_path = ROOT / "backend/requirements" / source
        lock_path = ROOT / "backend/requirements" / lock
        if not lock_path.exists():
            errors.append(f"missing {lock_path.relative_to(ROOT)}")
            continue
        missing = direct_requirements(source_path) - locked_requirements(lock_path)
        if missing:
            errors.append(f"{lock} does not pin direct requirements: {', '.join(sorted(missing))}")
        if "--hash=sha256:" not in lock_path.read_text(encoding="utf-8"):
            errors.append(f"{lock} does not contain distribution hashes")

    image_files = [
        ROOT / "backend/Dockerfile",
        ROOT / "frontend/Dockerfile",
        ROOT / "compose.yaml",
        ROOT / "compose.production.yaml",
    ]
    for path in image_files:
        build_stages: set[str] = set()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("FROM "):
                parts = stripped.split()
                image = parts[1]
                if image in build_stages:
                    continue
                if len(parts) >= 4 and parts[-2].upper() == "AS":
                    build_stages.add(parts[-1])
            elif stripped.startswith("image: "):
                image = stripped.removeprefix("image: ")
                if image.startswith("finanzr-"):
                    continue
            else:
                continue
            if "@sha256:" not in image:
                errors.append(
                    f"{path.relative_to(ROOT)}:{line_number} does not pin an image digest"
                )

    notice = ROOT / "frontend/public/THIRD_PARTY_NOTICES.txt"
    if "SIL OPEN FONT LICENSE Version 1.1" not in notice.read_text(encoding="utf-8"):
        errors.append("the distributed frontend is missing the complete Manrope OFL notice")

    if args.tag and args.tag != f"v{version}":
        errors.append(f"tag {args.tag!r} does not match expected tag 'v{version}'")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Release metadata is coherent for v{version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
