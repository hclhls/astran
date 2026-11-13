"""gf180 adapter: the contract documented in pdks/README.md."""
import shutil

import klayout.db as kdb
from pathlib import Path

from pdks.common import AdapterError, CheckResult
from pdks.gf180 import checks, netlist, pdk
from pdks.gf180 import postprocess as postprocess_mod

DEFAULT_CELLS = ["inv", "nand2", "nor2", "aoi21"]
BOUNDARY_LAYER = pdk.LAYERS["prBoundary"]     # cell box (0/0)
TOOLS = ["magic", "netgen", "klayout", "highs"]


def check_environment() -> None:
    pdk.pdk_dir()
    missing = [t for t in TOOLS if shutil.which(t) is None]
    if missing:
        raise AdapterError("tools not found on PATH: " + ", ".join(missing) +
                           " (run inside `nix develop`)")


def layout_name(cell: str) -> str:
    return netlist.layout_name(cell)


def write_astran_netlist(cell: str, out: Path) -> str:
    return netlist.write_astran_netlist(cell, out)


def write_lvs_netlist(cell: str, out: Path) -> None:
    netlist.write_lvs_netlist(cell, out)


TECH_RUL = Path(__file__).with_name("tech.rul")

# Starting circuit settings (tuned in Task 10).
SETTINGS = [
    'set vddnet VDD', 'set gndnet VSS',
    'set celltemplate "Taps w/ continuous diff"',
    'set hgrid 0.56', 'set vgrid 0.56', 'set rowheight 7',
    'set supplysize 0.6', 'set nwellpos 1.76', 'set nwellborder 0.6', 'set pnselborder 0.23',
]


def astran_script(astran_cell: str, netlist: Path, gds_out: Path) -> str:
    lines = ['set lpsolve "highs"',
             f'load technology "{TECH_RUL}"',
             f'load netlist "{Path(netlist).resolve()}"']
    lines += SETTINGS
    lines += [f'cellgen select {astran_cell}',
              'cellgen fold 2 0',
              'cellgen place 150 3 3 4 1 4 2',
              'cellgen route 1 0 1 1',
              'cellgen compact 1 0 50 2 1 1 0 0 0 600',
              f'export layout {astran_cell} {Path(gds_out).resolve()}']
    return "\n".join(lines) + "\n"


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    postprocess_mod.postprocess(gds_in, gds_out, cell)


def drc(gds: Path, top: str, workdir: Path) -> list:
    workdir = Path(workdir)
    return [("magic", checks.magic_drc(gds, top, workdir / "drc_magic")),
            ("klayout", checks.klayout_drc(gds, top, workdir / "drc_klayout"))]


def lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult:
    return checks.netgen_lvs(gds, top, ref, Path(workdir) / "lvs")


def cell_size(gds: Path, top: str) -> tuple:
    """CELLBOX (prBoundary) width and height in um."""
    ly = kdb.Layout()
    ly.read(str(gds))
    cell = ly.cell(top) or ly.top_cell()
    box = kdb.Region(cell.begin_shapes_rec(ly.layer(*pdk.LAYERS["prBoundary"]))).bbox()
    if box.empty():
        raise AdapterError(f"{gds}: no prBoundary shape in cell {cell.name}")
    return box.width() * ly.dbu, box.height() * ly.dbu


def reference_size(cell: str) -> tuple:
    """prBoundary width and height of the foundry _1 cell, from the 7t GDS (um)."""
    name = netlist.ref_name(cell)
    path = pdk.pdk_dir() / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds"
    ly = kdb.Layout()
    ly.read(str(path))
    c = ly.cell(name)
    if c is None:
        raise AdapterError(f"{name} not found in {path}")
    box = kdb.Region(c.begin_shapes_rec(ly.layer(*pdk.LAYERS["prBoundary"]))).bbox()
    return box.width() * ly.dbu, box.height() * ly.dbu


def notes() -> list:
    sw = " ".join(f"{k}={v}" for k, v in checks.KLAYOUT_SWITCHES.items())
    return [f"klayout DRC (run_drc.py) switches: {sw}",
            "Reference cells are tapless; the area ratio is against their prBoundary."]
