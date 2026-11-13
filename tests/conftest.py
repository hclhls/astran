import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def astran_cli() -> Path:
    exe = ROOT / "Astran/build/bin/astran-cli"
    r = subprocess.run(["make", "-C", str(ROOT / "Astran"), "-f", "cli.mk", "-j4"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert exe.exists()
    return exe


@pytest.fixture
def workdir(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def run_astran(astran_cli):
    def run(script_text: str, cwd: Path) -> subprocess.CompletedProcess:
        script = Path(cwd) / "script.run"
        script.write_text(script_text)
        return subprocess.run([str(astran_cli), "script.run"], cwd=cwd,
                              capture_output=True, text=True, timeout=900)
    return run
