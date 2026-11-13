"""sky130 adapter: the contract documented in pdks/README.md."""
import shutil
from pathlib import Path

from pdks.common import AdapterError, CheckResult
from pdks.sky130 import netlist, pdk

DEFAULT_CELLS = ["inv", "nand2", "nor2", "a21oi"]
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


def astran_script(astran_cell: str, netlist: Path, gds_out: Path) -> str:
    raise NotImplementedError


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    raise NotImplementedError


def drc(gds: Path, top: str, workdir: Path) -> list:
    raise NotImplementedError


def lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult:
    raise NotImplementedError


def cell_size(gds: Path, top: str) -> tuple:
    raise NotImplementedError


def reference_size(cell: str) -> tuple:
    raise NotImplementedError


def notes() -> list:
    raise NotImplementedError
