"""gf180 derived layers: implants on taps, dualgate and the V5_Xtor device marker.

May add or reclassify derived layers only. Drawn poly, diffusion, contacts, metal and the
wells are never moved or resized. All sizes are in database units (1 nm)."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError
from pdks.gf180.netlist import layout_name
from pdks.gf180.pdk import LAYERS

IMPLANT_ENCLOSE = 230      # NP.5a / PP.5a: implant around the diffusion it types
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
    nwell, nplus, pplus = reg("nwell"), reg("nplus"), reg("pplus")

    # 1. Implants on taps. Astran draws the main n and p implants over each half cell, tap strips
    # included, so they overlap there. A tap in the nwell is n+ only, a tap outside it p+ only.
    taps = comp.not_interacting(poly & comp)
    zone_n = taps.overlapping(nwell).sized(IMPLANT_ENCLOSE, 2)
    zone_p = taps.not_overlapping(nwell).sized(IMPLANT_ENCLOSE, 2)
    put("nplus", ((nplus - zone_p) + zone_n).merged())
    put("pplus", ((pplus - zone_n) + zone_p).merged())

    # 2. Dualgate: the 6 V devices need it; the foundry cells carry it over the whole cell.
    dg = box.sized(DUALGATE_CELL_MARGIN, 2) + comp.sized(DUALGATE_ENCLOSE_COMP, 2) + poly.sized(DUALGATE_ENCLOSE_POLY, 2)
    put("dualgate", reg("dualgate") + dg.merged())

    # 3. V5_Xtor marks the devices as 5 V ones (gate lengths 0.6 / 0.5); the foundry cells mark the whole cell.
    put("v5_xtor", reg("v5_xtor") + (box + comp).merged())

    # 4. Well labels, as in the foundry cells: VNW names the nwell, VPW the substrate (lvpwell) net.
    pwell = reg("pwell")
    for text, layer, well in (("VNW", "nwell_label", nwell), ("VPW", "pwell_label", pwell)):
        if well.is_empty():
            raise AdapterError(f"{gds_in}: no {layer[:5]} to label {text}")
        box = well.bbox()
        inside = well & kdb.Region(kdb.Box(box.left, box.bottom, box.left + 2 * DUALGATE_CELL_MARGIN, box.top))
        p = inside.bbox()
        # a point well inside the well, near the cell's left edge and its boundary-side edge
        y = p.top - 1 if text == "VNW" else p.bottom + 1
        top.shapes(ly.layer(*LAYERS[layer])).insert(kdb.Text(text, kdb.Trans(max(p.left, box.left) + DUALGATE_CELL_MARGIN, y)))

    top.name = layout_name(cell) if cell else top.name
    ly.write(str(gds_out))
