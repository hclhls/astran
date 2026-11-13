"""gf180 derived layers: dualgate, the V5_Xtor device marker and the well labels.

May add or reclassify derived layers only. Drawn poly, diffusion, contacts, metal and the
wells are never moved or resized. All sizes are in database units (1 nm)."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError
from pdks.gf180.netlist import layout_name
from pdks.gf180.pdk import LAYERS

DUALGATE_CELL_MARGIN = 280  # as in the foundry cells: dualgate extends this far past the cell box
DUALGATE_ENCLOSE_COMP = 240  # DV.6: dualgate encloses COMP
DUALGATE_ENCLOSE_POLY = 400  # DV.8: dualgate encloses poly


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    ly = kdb.Layout()
    ly.read(str(gds_in))
    top = ly.top_cell()
    top.flatten(True)
    ly.dbu = 0.001

    def reg(name):
        return kdb.Region(top.shapes(ly.layer(*LAYERS[name]))).merged()

    def put(name, r):
        li = ly.layer(*LAYERS[name])
        top.shapes(li).clear()
        top.shapes(li).insert(r)

    box = reg("prBoundary")
    if box.is_empty():
        raise AdapterError(f"{gds_in}: no cell boundary (prBoundary) found")

    comp, poly = reg("comp"), reg("poly")
    nwell = reg("nwell")

    # 1. Dualgate: the 6 V devices need it; the foundry cells carry it over the whole cell.
    dg = box.sized(DUALGATE_CELL_MARGIN, 2) + comp.sized(DUALGATE_ENCLOSE_COMP, 2) + poly.sized(DUALGATE_ENCLOSE_POLY, 2)
    put("dualgate", reg("dualgate") + dg.merged())

    # 2. V5_Xtor marks the devices as 5 V ones (gate lengths 0.6 / 0.5); the foundry cells mark the whole cell.
    put("v5_xtor", reg("v5_xtor") + (box + comp).merged())

    # 3. Well labels, as in the foundry cells: VNW names the nwell, VPW the substrate (lvpwell) net.
    pwell = reg("pwell")
    outline = box.bbox()
    for text, layer, well, y in (("VNW", "nwell_label", nwell, outline.top), ("VPW", "pwell_label", pwell, outline.bottom)):
        if well.is_empty():
            raise AdapterError(f"{gds_in}: no {layer[:5]} to label {text}")
        # inside the cell box (not in a neighbour's area) and, like the foundry's, near its left edge
        top.shapes(ly.layer(*LAYERS[layer])).insert(kdb.Text(text, kdb.Trans(outline.left + 340, y)))

    top.name = layout_name(cell) if cell else top.name
    ly.write(str(gds_out))
