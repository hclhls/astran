"""gf180 post-processing: legalisation of what Astran cannot express, then the derived layers
(dualgate, the V5_Xtor device marker, the well labels).

Poly and the transistors' diffusions, contacts and wiring are never moved relative to each other or resized.
Legalisation (`_legalize`, see the README) does four things, each a no-op on a cell that does not need it:
taps Astran dropped into a placement gap are removed (the library is tapless), metal1 notches narrower than
the spacing rule are filled, a cell generated with a raised n-well gets the library's well edge back at its
two sides, and such a cell is widened by whole grid tracks where that step would come too close to its
N diffusion. All sizes are in database units (1 nm)."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError
from pdks.gf180.netlist import layout_name
from pdks.gf180.pdk import LAYERS

DUALGATE_CELL_MARGIN = 280  # as in the foundry cells: dualgate extends this far past the cell box
DUALGATE_ENCLOSE_COMP = 240  # DV.6: dualgate encloses COMP
DUALGATE_ENCLOSE_POLY = 400  # DV.8: dualgate encloses poly


LIBRARY_WELL_Y = 1760       # the n-well edge every library cell (and the tap cell) presents to its neighbours
GRID = 560                  # placement pitch: a cell is widened by whole tracks
NCOMP_TO_NWELL = 600        # DF.8: N diffusion to n-well
M1_SPACE = 230              # M1.2a
POLY_SPACE = 240            # PL.3a
POLY_TO_COMP = 300          # PL.5a/PL.5b: field poly to diffusion
MAX_PAD_TRACKS = 2


def _legalize(ly: kdb.Layout, top: kdb.Cell, gds_in: Path) -> None:
    def L(name):
        return ly.layer(*LAYERS[name])

    def reg(name):
        return kdb.Region(top.shapes(L(name))).merged()

    def put(name, r):
        top.shapes(L(name)).clear()
        top.shapes(L(name)).insert(r.merged())

    # 1. Taps. Astran fills a gap in a transistor row with a tap on the rail; the library is tapless (the row's
    #    tap cells do that job), and a substrate tap would short VSS to the VPW pin.
    comp, nwell, nplus, pplus = reg("comp"), reg("nwell"), reg("nplus"), reg("pplus")
    taps = comp.interacting(((comp & pplus) - nwell) + ((comp & nplus) & nwell))
    if not taps.is_empty():
        put("comp", comp - taps)
        put("contact", reg("contact").not_interacting(taps))
        put("pplus", pplus - (pplus - nwell).interacting(taps))
        put("nplus", nplus - (nplus & nwell).interacting(taps))

    # 2. Metal1 notches: Astran's compaction has no same-net notch rule. Gaps below the spacing rule are closed;
    #    between different nets such a gap would be a spacing error already.
    m1 = reg("metal1")
    close = M1_SPACE // 2 - 1
    put("metal1", m1 + m1.sized(close).sized(-close))

    #    Poly the same way (PL.3a), but only away from diffusion: a fill must not make or change a gate.
    poly, comp = reg("poly"), reg("comp")
    close = POLY_SPACE // 2 - 1
    fill = poly.sized(close).sized(-close) - poly
    put("poly", poly + fill.not_interacting(comp.sized(POLY_TO_COMP)))

    # 3. Raised n-well (the adapter's well search): give both cell edges the library's well edge back.
    well_y = reg("nwell").bbox().bottom
    if well_y <= LIBRARY_WELL_Y:
        return
    big = 10 ** 7

    def strips():
        """The band between the library's and this cell's well edge, as far into the cell at each side as a
        neighbour's n-well reaches (our own overhang, the larger one)."""
        box, pw = reg("prBoundary").bbox(), reg("pwell").bbox()
        reach = box.left - pw.left
        r = kdb.Region(kdb.Box(pw.left, LIBRARY_WELL_Y, box.left + reach, well_y))
        return r, kdb.Region(kdb.Box(box.right - reach, LIBRARY_WELL_Y, pw.right, well_y))

    def too_close(strip):
        ncomp = reg("comp") - reg("nwell")
        return not (ncomp & strip).is_empty() or \
            ncomp.separation_check(strip, NCOMP_TO_NWELL, False, kdb.Region.Euclidian).count() > 0

    def pad(left: bool):
        """Widen the cell by one track on one side: everything that crosses that edge (rails, wells, implants,
        the boundary) is extended, and nothing else changes."""
        box = reg("prBoundary").bbox()
        x = box.left if left else box.right - 1
        for li in ly.layer_indexes():
            r = kdb.Region(top.shapes(li)).merged()
            for q in (r & kdb.Region(kdb.Box(x, -big, x + 1, big))).each():
                b = q.bbox()
                top.shapes(li).insert(kdb.Box(min(r.bbox().left, box.left) - GRID, b.bottom, box.left + 1, b.top) if left
                                      else kdb.Box(box.right - 1, b.bottom, max(r.bbox().right, box.right) + GRID, b.top))
        if left:                                      # keep the cell's origin at its lower left corner
            for li in ly.layer_indexes():
                top.shapes(li).transform(kdb.Trans(GRID, 0))
        put("prBoundary", reg("prBoundary"))

    for side in (0, 1):
        for _ in range(MAX_PAD_TRACKS):
            if not too_close(strips()[side]):
                break
            pad(left=side == 0)
        else:
            if too_close(strips()[side]):
                raise AdapterError(f"{gds_in}: N diffusion within {NCOMP_TO_NWELL} nm of the n-well step at the "
                                   f"{'left' if side == 0 else 'right'} edge even after {MAX_PAD_TRACKS} tracks of padding")
    left, right = strips()
    step = left + right
    nplus, pplus = reg("nplus"), reg("pplus")
    implant = step & kdb.Region(kdb.Box(nplus.bbox().left, -big, nplus.bbox().right, big))
    put("nwell", reg("nwell") + step)
    put("pwell", reg("pwell") - step)
    put("nplus", nplus - step)
    put("pplus", pplus + implant)


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

    if reg("prBoundary").is_empty():
        raise AdapterError(f"{gds_in}: no cell boundary (prBoundary) found")
    _legalize(ly, top, gds_in)
    box = reg("prBoundary")

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
