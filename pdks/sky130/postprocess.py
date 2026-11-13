"""sky130 derived layers: tap, npc, hvtp, implant clean-up, cell-edge handling.

May add or reclassify derived layers only. Drawn poly, diffusion, contacts and
metal are never moved or resized (diff may move to tap, unchanged in shape).
All sizes are in database units (1 nm)."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError
from pdks.sky130.netlist import layout_name
from pdks.sky130.pdk import LAYERS

NPC_ENCLOSE = 100        # npc around poly licon
NPC_SPACE = 270          # npc spacing (npc.2)
NPC_EDGE = 135           # npc stays this far inside the left/right cell edges
IMPLANT_SPACE = 380      # nsdm / psdm spacing and notch width
HVT_ENCLOSE = 55         # hvtp around the PMOS gate
HVT_MIN_WIDTH = 380
# Shapes of these layers that come within this distance of a left/right cell edge are
# extended to the edge so that an abutting neighbour merges instead of leaving a gap.
EDGE_SPACING = {"nwell": 1270, "nsdm": 380, "psdm": 380, "hvtp": 380}


def _close(r: kdb.Region, gap: int) -> kdb.Region:
    """Fill gaps and notches narrower than `gap`."""
    d = gap // 2
    return r.sized(d, 2).sized(-d, 2)


def _extend_to_edges(r: kdb.Region, left: int, right: int, spacing: int) -> kdb.Region:
    out = r.dup()
    for p in r.merged().each():
        b = p.bbox()
        single = kdb.Region(p)
        if left < b.left < left + spacing:
            for q in (single & kdb.Region(kdb.Box(b.left, b.bottom, b.left + 5, b.top))).each():
                out.insert(kdb.Box(left, q.bbox().bottom, b.left, q.bbox().top))
        if right - spacing < b.right < right:
            for q in (single & kdb.Region(kdb.Box(b.right - 5, b.bottom, b.right, b.top))).each():
                out.insert(kdb.Box(b.right, q.bbox().bottom, right, q.bbox().top))
    return out.merged()


def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None:
    ly = kdb.Layout()
    ly.read(str(gds_in))
    top = ly.top_cell()
    top.flatten(True)
    ly.dbu = 0.001

    def li(name):
        return ly.layer(*LAYERS[name])

    def reg(name):
        return kdb.Region(top.shapes(li(name))).merged()

    def put(name, r):
        top.shapes(li(name)).clear()
        top.shapes(li(name)).insert(r)

    box = reg("prBoundary").bbox()
    if box.empty():
        raise AdapterError(f"{gds_in}: no cell boundary (prBoundary) found")
    left, right = box.left, box.right

    diff, poly, licon = reg("diff"), reg("poly"), reg("licon1")
    nwell, nsdm, psdm = reg("nwell"), reg("nsdm"), reg("psdm")

    # 1. tap: diffusion without a gate that is p+ outside nwell or n+ inside nwell
    gate = poly & diff
    gateless = diff.not_interacting(gate)
    tap = gateless.not_overlapping(nwell).overlapping(psdm) + gateless.overlapping(nwell).overlapping(nsdm)
    tap = tap.merged()
    put("diff", diff - tap)
    put("tap", reg("tap") + tap)

    # 2. npc around licons on poly (not on diffusion)
    poly_cont = licon.overlapping(poly).not_overlapping(diff)
    npc = _close(poly_cont.sized(NPC_ENCLOSE, 2).merged(), NPC_SPACE)
    put("npc", reg("npc") + npc)

    # 3. hvtp over the PMOS gates, spanning the cell width
    hv = kdb.Region()
    for p in ((gate & nwell).merged().sized(HVT_ENCLOSE, 2)).merged().each():
        y1, y2 = p.bbox().bottom, p.bbox().top
        if y2 - y1 < HVT_MIN_WIDTH:
            grow = (HVT_MIN_WIDTH - (y2 - y1) + 1) // 2
            grow += (-grow) % 5
            y1, y2 = y1 - grow, y2 + grow
        hv.insert(kdb.Box(left, y1, right, y2))
    put("hvtp", reg("hvtp") + hv.merged())

    # 4. implants: close notches and gaps narrower than the implant spacing
    put("nsdm", _close(nsdm, IMPLANT_SPACE))
    put("psdm", _close(psdm, IMPLANT_SPACE))

    # 5. cell edge
    for name, spacing in EDGE_SPACING.items():
        put(name, _extend_to_edges(reg(name), left, right, spacing))
    for p in reg("npc").each():
        b = p.bbox()
        for x in (b.left, b.right):
            if x < left + NPC_EDGE or x > right - NPC_EDGE:
                raise AdapterError(f"npc too close to cell edge at x={x / 1000:g}")

    # 6. rename; write
    top.name = layout_name(cell) if cell else top.name
    ly.write(str(gds_out))
