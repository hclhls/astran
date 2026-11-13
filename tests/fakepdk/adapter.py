"""In-memory adapter used to test the driver. Implements the contract in pdks/README.md."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError, CheckResult

DEFAULT_CELLS = ["good", "nodrc", "nogds", "missing"]
BOUNDARY_LAYER = (7, 0)
NEIGHBOURS_SEEN = []          # filled by tests through a wrapper around build_abutment


def check_environment() -> None:
    pass


def layout_name(cell: str) -> str:
    return "fake_" + cell


def write_astran_netlist(cell: str, out: Path) -> str:
    if cell == "missing":
        raise AdapterError("cell missing not in library")
    Path(out).write_text(f".subckt {cell}\n.ends\n")
    return cell


def write_lvs_netlist(cell: str, out: Path) -> None:
    Path(out).write_text(f"* ref {cell}\n")


def astran_script(astran_cell: str, netlist: Path, gds_out: Path) -> str:
    return f"cell {astran_cell}\nout {gds_out}\n"


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    if not Path(gds_in).stat().st_size:
        raise AdapterError("empty raw gds")
    ly = kdb.Layout()
    ly.dbu = 0.001
    top = ly.create_cell(layout_name(cell))
    top.shapes(ly.layer(*BOUNDARY_LAYER)).insert(kdb.DBox(0, 0, 2.0, 3.0))
    ly.write(str(gds_out))


def drc(gds: Path, top: str, workdir: Path) -> list:
    bad = "nodrc" in top and not top.endswith("__abut")
    r = CheckResult(not bad, 3 if bad else 0, Path(workdir) / "drc.rpt", "fake")
    return [("fakecheck", r)]


def lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult:
    return CheckResult(True, 0, Path(workdir) / "lvs.rpt", "fake")


def cell_size(gds: Path, top: str) -> tuple:
    return 2.0, 3.0


def reference_size(cell: str) -> tuple:
    return 1.0, 3.0


def notes() -> list:
    return ["note: fake adapter"]
