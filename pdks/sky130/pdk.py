"""Locating the sky130A PDK, and its layer/datatype pairs."""
import os
from pathlib import Path

from pdks.common import AdapterError

PINNED_VERSION = "0fe599b2afb6708d281543108caf8310912f54af"

# From sky130A.lyp.
LAYERS = {
    "nwell": (64, 20), "diff": (65, 20), "tap": (65, 44), "poly": (66, 20),
    "licon1": (66, 44), "npc": (95, 20), "li1": (67, 20), "li1_pin": (67, 16),
    "li1_label": (67, 5), "mcon": (67, 44), "met1": (68, 20), "met1_pin": (68, 16),
    "met1_label": (68, 5), "via": (68, 44), "met2": (69, 20), "nsdm": (93, 44),
    "psdm": (94, 20), "hvtp": (78, 44), "prBoundary": (235, 4),
}


def _candidates() -> list:
    out = []
    if os.environ.get("ASTRAN_SKY130_DIR"):
        out.append(Path(os.environ["ASTRAN_SKY130_DIR"]))
    root = Path(os.environ.get("PDK_ROOT") or Path.home() / ".ciel")
    out.append(root / "sky130A")
    out.append(root / "ciel" / "sky130" / "versions" / PINNED_VERSION / "sky130A")
    return out


def pdk_dir() -> Path:
    tried = _candidates()
    for p in tried:
        if p.is_dir():
            return p
    raise AdapterError("sky130A PDK not found; tried: " + ", ".join(str(p) for p in tried) +
                       ". Set ASTRAN_SKY130_DIR or PDK_ROOT.")
