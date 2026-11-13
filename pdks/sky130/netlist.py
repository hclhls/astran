"""hd library CDL -> Astran SPICE and LVS reference."""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pdks.common import AdapterError
from pdks.sky130 import pdk

PREFIX = "sky130_fd_sc_hd__"
SUPPLY = {"VNB": "VGND", "VPB": "VPWR"}
# hd CDL model -> (Astran model, PDK device model for the LVS reference)
MODELS = {
    "nfet_01v8": ("NMOS", "sky130_fd_pr__nfet_01v8"),
    "pfet_01v8_hvt": ("PMOS", "sky130_fd_pr__pfet_01v8_hvt"),
}


@dataclass
class Device:
    name: str
    d: str
    g: str
    s: str
    b: str
    model: str      # hd CDL model name
    w: float        # um
    l: float        # um


@dataclass
class Subckt:
    name: str
    ports: list
    devices: list


def hd_name(cell: str) -> str:
    """'inv' -> 'sky130_fd_sc_hd__inv_1'; 'inv_2' is kept."""
    if not re.search(r"_\d+$", cell):
        cell += "_1"
    return PREFIX + cell


def astran_name(cell: str) -> str:
    return hd_name(cell)[len(PREFIX):].upper()


def layout_name(cell: str) -> str:
    return "astran_sky130__" + hd_name(cell)[len(PREFIX):]


def _num(v: str) -> float:
    return float(v.rstrip("uU"))


def _logical_lines(text: str):
    cur = None
    for raw in text.splitlines():
        if raw.startswith("+"):
            if cur is not None:
                cur += " " + raw[1:].strip()
            continue
        if cur is not None:
            yield cur
        cur = None if raw.startswith("*") or not raw.strip() else raw.strip()
    if cur is not None:
        yield cur


def parse_cdl_subckt(text: str, name: str) -> Subckt:
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
        if not inside or not head.startswith("M"):
            continue
        d, g, s, b, model = tok[1:6]
        if model not in MODELS:
            raise AdapterError(f"{name}: device {tok[0]} uses unsupported model {model}")
        par = dict(t.lower().split("=", 1) for t in tok[6:] if "=" in t)
        mult = round(_num(par.get("m", "1")) * _num(par.get("mult", "1")) * _num(par.get("nf", "1")))
        if mult < 1:
            raise AdapterError(f"{name}: device {tok[0]} has multiplicity {mult}")
        for k in range(mult):
            nm = tok[0] if mult == 1 else f"{tok[0]}_{k}"
            devices.append(Device(nm, d, g, s, b, model, _num(par["w"]), _num(par["l"])))
    raise AdapterError(f"cell {name} not found in the hd library")


@lru_cache(maxsize=None)
def _cdl_text() -> str:
    path = pdk.pdk_dir() / "libs.ref/sky130_fd_sc_hd/cdl/sky130_fd_sc_hd.cdl"
    try:
        return path.read_text()
    except OSError as e:
        raise AdapterError(f"cannot read {path}: {e}")


def _load(cell: str) -> Subckt:
    return parse_cdl_subckt(_cdl_text(), hd_name(cell))


def _signal_ports(sc: Subckt) -> list:
    return [p.upper() for p in sc.ports if p not in ("VGND", "VNB", "VPB", "VPWR")]


def _net(n: str) -> str:
    n = SUPPLY.get(n, n)
    return n.upper()


def _fmt(v: float) -> str:
    return f"{v:g}"


def write_astran_netlist(cell: str, out: Path) -> str:
    sc = _load(cell)
    name = astran_name(cell)
    lines = [f".subckt {name} " + " ".join(_signal_ports(sc) + ["VPWR", "VGND"])]
    for i, dev in enumerate(sc.devices):
        lines.append(f"M{i} {_net(dev.d)} {_net(dev.g)} {_net(dev.s)} {_net(dev.b)} "
                     f"{MODELS[dev.model][0]} L={_fmt(dev.l)}U W={_fmt(dev.w)}U")
    lines.append(".ends")
    Path(out).write_text("\n".join(lines) + "\n")
    return name


def write_lvs_netlist(cell: str, out: Path) -> None:
    sc = _load(cell)
    lines = [f".subckt {layout_name(cell)} " + " ".join(_signal_ports(sc) + ["VPWR", "VGND"])]
    for i, dev in enumerate(sc.devices):
        lines.append(f"X{i} {_net(dev.d)} {_net(dev.g)} {_net(dev.s)} {_net(dev.b)} "
                     f"{MODELS[dev.model][1]} w={_fmt(dev.w)} l={_fmt(dev.l)}")
    lines.append(".ends")
    Path(out).write_text("\n".join(lines) + "\n")
