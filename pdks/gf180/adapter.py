"""gf180 adapter: the contract documented in pdks/README.md."""
import shutil

import klayout.db as kdb
from pathlib import Path

from pdks.common import AdapterError, CheckResult
from pdks.gf180 import checks, netlist, pdk, taps
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

# Astran circuit settings, tuned until all four cells were DRC and LVS clean (see README).
SETTINGS = [
    'set vddnet VDD', 'set gndnet VSS',
    'set celltemplate "Taps close to the boundary"',
    'set hgrid 0.56', 'set vgrid 0.56', 'set rowheight 7',
    'set supplysize 0.6', 'set nwellborder 0.6', 'set pnselborder 0.2',
]
# n-well boundary heights (um) tried in turn, the first that yields a layout wins. Where it sits splits the
# 3.92 um between the N and the P region: a cell whose N region needs a stack of M1 tracks that does not fit
# is infeasible at 1.76 and fits higher, while others (xnor2: 1.92 only) fail higher up, so there is no one value.
NWELLPOS = (1.76, 1.92, 2.0, 2.08, 2.16)


def astran_script(astran_cell: str, netlist: Path, gds_out: Path, nwellpos: float = NWELLPOS[0]) -> str:
    lines = ['set lpsolve "highs"',
             f'load technology "{TECH_RUL}"',
             f'load netlist "{Path(netlist).resolve()}"']
    lines += SETTINGS + [f'set nwellpos {nwellpos}']
    lines += [f'cellgen select {astran_cell}',
              'cellgen fold 2 0',
              'cellgen place 150 3 3 4 1 4 2',
              'cellgen route 1 0 1 1',
              'cellgen compact 1 1 50 2 1 1 0 0 0 600',
              f'export layout {astran_cell} {Path(gds_out).resolve()}']
    return "\n".join(lines) + "\n"


def astran_script_variants(astran_cell: str, netlist: Path, gds_out: Path) -> list:
    """One script per n-well height, in the order they are tried (see NWELLPOS)."""
    return [astran_script(astran_cell, netlist, gds_out, h) for h in NWELLPOS]


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    postprocess_mod.postprocess(gds_in, gds_out, cell)


def drc(gds: Path, top: str, workdir: Path) -> list:
    """DRC with the library's tap cell on both ends of every row (the cells themselves are tapless)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tapped = workdir / "with_taps.gds"
    name = taps.add_end_taps(gds, top, tapped)
    return [("magic", checks.magic_drc(tapped, name, workdir / "drc_magic")),
            ("klayout", checks.klayout_drc(tapped, name, workdir / "drc_klayout"))]


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
    return [f"klayout DRC (gf180 deck) switches: {sw}",
            "Cells are tapless like the reference; DRC is run with the library tap cell at the row ends. "
            "The area ratio is against the reference prBoundary."]
