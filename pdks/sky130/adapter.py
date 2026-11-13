"""sky130 adapter: the contract documented in pdks/README.md."""
import re
import shutil

import klayout.db as kdb
from pathlib import Path

from pdks.common import AdapterError, CheckResult
from pdks.sky130 import checks, netlist, pdk
from pdks.sky130 import postprocess as postprocess_mod

DEFAULT_CELLS = ["inv", "nand2", "nor2", "a21oi"]
BOUNDARY_LAYER = pdk.LAYERS["prBoundary"]     # cell box (235/4)
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
    'set vddnet VPWR', 'set gndnet VGND',
    'set celltemplate "Taps w/ continuous diff"',
    'set hgrid 0.46', 'set vgrid 0.34', 'set rowheight 10',
    'set supplysize 0.48', 'set nwellpos 1.5', 'set nwellborder 0.33', 'set pnselborder 0.125',
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
    """SIZE of the foundry _1 macro, from the hd LEF."""
    name = netlist.hd_name(cell)
    lef = pdk.pdk_dir() / "libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
    text = lef.read_text()
    m = re.search(rf"^MACRO {name}\s*$.*?^\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;", text, re.S | re.M)
    if not m:
        raise AdapterError(f"{name} not found in {lef}")
    return float(m[1]), float(m[2])


def notes() -> list:
    sw = " ".join(f"{k}={v}" for k, v in checks.KLAYOUT_SWITCHES.items())
    return [f"klayout DRC deck switches: {sw}",
            "Astran cells include well taps and hd cells do not, so the area ratio is "
            "pessimistic for Astran by the tap area."]
