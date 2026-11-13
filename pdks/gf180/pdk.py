"""Locating the gf180mcuD PDK, and its layer/datatype pairs."""
import os
from pathlib import Path

from pdks.common import AdapterError

PINNED_VERSION = "0fe599b2afb6708d281543108caf8310912f54af"

# From gf180mcu.lyp.
LAYERS = {
    "nwell": (21, 0), "pwell": (204, 0), "nwell_label": (21, 10), "pwell_label": (204, 10), "comp": (22, 0), "poly": (30, 0),
    "contact": (33, 0), "metal1": (34, 0), "metal1_label": (34, 10),
    "via1": (35, 0), "metal2": (36, 0), "via2": (38, 0), "metal3": (42, 0),
    "nplus": (32, 0), "pplus": (31, 0), "dualgate": (55, 0), "v5_xtor": (112, 1), "prBoundary": (0, 0),
}


def _candidates() -> list:
    out = []
    if os.environ.get("ASTRAN_GF180_DIR"):
        out.append(Path(os.environ["ASTRAN_GF180_DIR"]))
    root = Path(os.environ.get("PDK_ROOT") or Path.home() / ".ciel")
    out.append(root / "gf180mcuD")
    out.append(root / "ciel" / "gf180mcu" / "versions" / PINNED_VERSION / "gf180mcuD")
    return out


def pdk_dir() -> Path:
    tried = _candidates()
    for p in tried:
        if p.is_dir():
            return p
    raise AdapterError("gf180mcuD PDK not found; tried: " + ", ".join(str(p) for p in tried) +
                       ". Set ASTRAN_GF180_DIR or PDK_ROOT, or fetch it with "
                       f"`ciel enable --pdk-family gf180mcu {PINNED_VERSION}`.")
