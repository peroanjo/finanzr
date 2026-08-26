import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_install_bootstrap_uses_hidden_stdin_without_password_argv() -> None:
    script_path = ROOT / "deploy/install.sh"
    readme_path = ROOT / "README.md"
    if not script_path.exists() or not readme_path.exists():
        pytest.skip("repository root is not mounted in the backend test image")
    script = script_path.read_text()
    recommended = readme_path.read_text().split("sudo env", 1)[1].split("```", 1)[0]

    assert "--password-stdin" in script
    assert '--password "$owner_password"' not in script
    assert "FINANZR_OWNER_PASSWORD='" not in recommended
    subprocess.run(["sh", "-n", str(script_path)], check=True)
