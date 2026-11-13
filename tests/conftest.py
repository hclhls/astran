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


FLOW = '''set lpsolve "highs"
load technology "{rul}"
load netlist "{work}/lib65.sp"
cellgen select INV0
cellgen fold 2 0
cellgen place 150 3 3 4 1 4 2
cellgen route 1 0 1 1
cellgen compact 1 0 50 2 1 1 0 0 0 600
{exports}
'''


@pytest.fixture
def legacy_flow(run_astran, repo_root):
    """Runs the 0.065 generator flow with the given rule file; returns the workdir result."""
    def go(rul: Path, cwd: Path, exports=("export layout INV0 INV0.gds",)):
        script = FLOW.format(rul=rul, work=repo_root / "Astran/build/Work", exports="\n".join(exports))
        r = run_astran(script, cwd)
        assert r.returncode == 0, r.stdout
        return r
    return go


@pytest.fixture
def generated_mini_gds(legacy_flow, workdir, repo_root) -> Path:
    legacy_flow(repo_root / "tests/data/mini.rul", workdir)
    return workdir / "INV0.gds"


@pytest.fixture(scope="session")
def generated_inv_raw(astran_cli, tmp_path_factory) -> Path:
    """Raw Astran GDS of the sky130 'inv' cell."""
    from pdks.sky130 import adapter
    wd = tmp_path_factory.mktemp("inv_raw")
    name = adapter.write_astran_netlist("inv", wd / "astran.sp")
    gds = wd / "raw.gds"
    (wd / "cell.run").write_text(adapter.astran_script(name, wd / "astran.sp", gds))
    r = subprocess.run([str(astran_cli), "cell.run"], cwd=wd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout
    return gds
