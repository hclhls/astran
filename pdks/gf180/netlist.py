"""gf180mcu 7t library SPICE -> Astran SPICE and LVS reference."""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pdks.common import AdapterError, logical_lines as _logical_lines
from pdks.gf180 import pdk

PREFIX = "gf180mcu_fd_sc_mcu7t5v0__"
SUPPLIES = ("VDD", "VSS")
BODY = {"VNW": "VDD", "VPW": "VSS"}
# library model -> Astran model (the library model name is also the LVS device name)
MODELS = {"nfet_06v0": "NMOS", "pfet_06v0": "PMOS"}


@dataclass
class Device:
    name: str
    d: str
    g: str
    s: str
    b: str
    model: str
    w: float        # um
    l: float        # um


@dataclass
class Subckt:
    name: str
    ports: list
    devices: list


def ref_name(cell: str) -> str:
    """'inv' -> 'gf180mcu_fd_sc_mcu7t5v0__inv_1'; 'inv_2' is kept."""
    if not re.search(r"_\d+$", cell):
        cell += "_1"
    return PREFIX + cell


def astran_name(cell: str) -> str:
    return ref_name(cell)[len(PREFIX):].upper()


def layout_name(cell: str) -> str:
    return "astran_gf180__" + ref_name(cell)[len(PREFIX):]


def _meters_to_um(v: str) -> float:
    return float(v) * 1e6


def parse_spice_subckt(text: str, name: str) -> Subckt:
    inside, ports, devices = False, [], []
    for line in _logical_lines(text):
        tok = line.split()
        head = tok[0].upper()
        if head == ".SUBCKT":
            if tok[1] == name:
                inside, ports = True, tok[2:]
            continue
        if head == ".ENDS":
            if inside:
                return Subckt(name, ports, devices)
            continue
        if not inside or not head.startswith("X"):
            continue
        d, g, s, b, model = tok[1:6]
        if model not in MODELS:
            raise AdapterError(f"{name}: device {tok[0]} uses unsupported model {model}")
        par = dict(t.lower().split("=", 1) for t in tok[6:] if "=" in t)
        devices.append(Device(tok[0], d, g, s, b, model, _meters_to_um(par["w"]), _meters_to_um(par["l"])))
    raise AdapterError(f"cell {name} not found in the gf180mcu 7t library")


@lru_cache(maxsize=None)
def _spice_text() -> str:
    path = pdk.pdk_dir() / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
    try:
        return path.read_text()
    except OSError as e:
        raise AdapterError(f"cannot read {path}: {e}")


def _load(cell: str) -> Subckt:
    return parse_spice_subckt(_spice_text(), ref_name(cell))


def _signal_ports(sc: Subckt) -> list:
    return [p.upper() for p in sc.ports if p not in ("VDD", "VSS", "VNW", "VPW")]


def _net(n: str) -> str:
    return BODY.get(n, n).upper()


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def write_astran_netlist(cell: str, out: Path) -> str:
    sc = _load(cell)
    name = astran_name(cell)
    lines = [f".subckt {name} " + " ".join(_signal_ports(sc) + list(SUPPLIES))]
    for i, dev in enumerate(sc.devices):
        lines.append(f"M{i} {_net(dev.d)} {_net(dev.g)} {_net(dev.s)} {_net(dev.b)} "
                     f"{MODELS[dev.model]} L={_fmt(dev.l)}U W={_fmt(dev.w)}U")
    lines.append(".ends")
    Path(out).write_text("\n".join(lines) + "\n")
    return name


def write_lvs_netlist(cell: str, out: Path) -> None:
    """LVS reference. Bodies stay on VNW / VPW as in the library: the cells are tapless and the
    wells are named by labels in the layout, like the foundry's."""
    sc = _load(cell)
    lines = [f".subckt {layout_name(cell)} " + " ".join(_signal_ports(sc) + ["VDD", "VNW", "VPW", "VSS"])]
    for i, dev in enumerate(sc.devices):
        lines.append(f"X{i} {dev.d.upper()} {dev.g.upper()} {dev.s.upper()} {dev.b.upper()} "
                     f"{dev.model} w={_fmt(dev.w)}u l={_fmt(dev.l)}u")
    lines.append(".ends")
    Path(out).write_text("\n".join(lines) + "\n")
