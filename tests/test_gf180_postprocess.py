import klayout.db as kdb

from helpers import load, region, same
from pdks.gf180.pdk import LAYERS
from pdks.gf180.postprocess import postprocess

L = LAYERS


def run(raw, tmp_path):
    out = tmp_path / "out.gds"
    postprocess(raw, out, "inv")
    return load(raw), load(out)


def test_top_cell_renamed_and_flat(gf180_inv_raw, tmp_path):
    _, b = run(gf180_inv_raw, tmp_path)
    assert b.top_cell().name == "astran_gf180__inv_1" and b.cells() == 1


def test_boundary_matches_cell_box(gf180_inv_raw, tmp_path):
    a, b = run(gf180_inv_raw, tmp_path)
    assert same(region(a, L["prBoundary"]), region(b, L["prBoundary"]))
    assert region(b, L["prBoundary"]).bbox().height() * b.dbu == 3.92


def test_drawn_geometry_untouched(gf180_inv_raw, tmp_path):
    a, b = run(gf180_inv_raw, tmp_path)
    for name in ("poly", "comp", "contact", "metal1", "via1", "metal2", "nwell", "pwell"):
        assert same(region(a, L[name]), region(b, L[name])), name


def test_dualgate_covers_every_gate_and_nothing_far_from_the_cell(gf180_inv_raw, tmp_path):
    _, b = run(gf180_inv_raw, tmp_path)
    dg = region(b, L["dualgate"])
    gates = region(b, L["poly"]) & region(b, L["comp"])
    assert not gates.is_empty() and (gates - dg).is_empty()
    comp = region(b, L["comp"])
    assert (comp.sized(240) - dg).is_empty()                      # DV.6: encloses COMP by 0.24
    near = (region(b, L["prBoundary"]) + comp + region(b, L["poly"])).sized(400)
    assert (dg - near).is_empty()                                  # nothing out in the field


def test_implant_types_match_diffusion_types(gf180_inv_raw, tmp_path):
    _, b = run(gf180_inv_raw, tmp_path)
    comp, poly = region(b, L["comp"]), region(b, L["poly"])
    nwell, nplus, pplus = region(b, L["nwell"]), region(b, L["nplus"]), region(b, L["pplus"])
    assert (nplus & pplus).is_empty()
    for part in comp.each():
        r = kdb.Region(part)
        in_well = not (r & nwell).is_empty()
        # NMOS (outside nwell, gated) and n-taps (inside nwell, no gate) are n+; PMOS and p-taps are p+
        gated = not (r & poly).is_empty()
        n_type = (gated and not in_well) or (not gated and in_well)
        assert (r - (nplus if n_type else pplus)).is_empty(), part
        assert (r & (pplus if n_type else nplus)).is_empty(), part


def test_postprocess_is_deterministic(gf180_inv_raw, tmp_path):
    (tmp_path / "1").mkdir()
    (tmp_path / "2").mkdir()
    _, a = run(gf180_inv_raw, tmp_path / "1")
    _, b = run(gf180_inv_raw, tmp_path / "2")
    for pair in L.values():
        assert same(region(a, pair), region(b, pair)), pair


def test_v5_xtor_marker_covers_every_device(gf180_inv_raw, tmp_path):
    # the deck takes a gate for a 6 V one (L = 0.7 / 0.55) unless V5_Xtor (112/1) marks it, as in the foundry cells
    _, b = run(gf180_inv_raw, tmp_path)
    marker = region(b, L["v5_xtor"])
    assert not marker.is_empty()
    assert (region(b, L["comp"]) - marker).is_empty()
    assert (region(b, L["prBoundary"]) - marker).is_empty()


def test_wells_are_labelled_like_the_foundry_cells(gf180_inv_raw, tmp_path):
    # VNW on the nwell label layer (21/10), VPW on the pwell one (204/10), each inside its well
    _, b = run(gf180_inv_raw, tmp_path)
    for text, layer, well in (("VNW", L["nwell_label"], L["nwell"]), ("VPW", L["pwell_label"], L["pwell"])):
        pts = [s.text.position() for s in b.top_cell().shapes(b.layer(*layer)).each() if s.is_text() and s.text.string == text]
        assert len(pts) == 1, text
        assert not (region(b, well) & kdb.Region(kdb.Box(pts[0].x - 1, pts[0].y - 1, pts[0].x + 1, pts[0].y + 1))).is_empty(), text
        cell = region(b, L["prBoundary"]).bbox()               # and inside the cell box, not in a neighbour's area
        assert cell.left <= pts[0].x <= cell.right and cell.bottom <= pts[0].y <= cell.top, text


# --- legalisation of a cell generated with a raised n-well (oai21 at 1.92 um) ---

def legal(raw, tmp_path):
    out = tmp_path / "out.gds"
    postprocess(raw, out, "oai21")
    return load(raw), load(out)


def box(ly):
    return region(ly, L["prBoundary"]).bbox()


def test_raised_well_cell_keeps_its_transistors(gf180_oai21_raw, tmp_path):
    a, b = legal(gf180_oai21_raw, tmp_path)
    pad = box(b).width() - box(a).width()
    assert pad in (0, 560, 1120) and box(b).left == 0 and box(b).height() == box(a).height()
    gates = lambda ly: region(ly, L["poly"]) & region(ly, L["comp"])
    moved = [dx for dx in (0, 560) if same(gates(a).moved(dx, 0), gates(b))]
    assert moved, "gates changed"
    assert same(region(a, L["poly"]).moved(moved[0], 0), region(b, L["poly"]))


def test_raised_well_cell_presents_the_library_well_edge(gf180_oai21_raw, tmp_path):
    a, b = legal(gf180_oai21_raw, tmp_path)
    assert region(a, L["nwell"]).bbox().bottom == 1920
    bx, nwell, pwell = box(b), region(b, L["nwell"]), region(b, L["pwell"])
    for x in (bx.left, bx.right - 1):                                    # at both edges: nwell from 1.76 um up
        col = kdb.Region(kdb.Box(x, bx.bottom, x + 1, bx.top))
        assert (nwell & col).bbox().bottom == 1760 and (pwell & col).bbox().top == 1760
    mid = kdb.Region(kdb.Box(bx.center().x, bx.bottom, bx.center().x + 1, bx.top))
    assert (nwell & mid).bbox().bottom == 1920                            # and where Astran put it inside
    assert (nwell & pwell).is_empty()
    assert (region(b, L["nplus"]) & region(b, L["pplus"])).is_empty()
    ncomp = region(b, L["comp"]) - nwell
    assert ncomp.separation_check(nwell, 600, False, kdb.Region.Euclidian).count() == 0     # DF.8


def test_raised_well_cell_has_no_taps_and_no_metal1_notch(gf180_oai21_raw, tmp_path):
    a, b = legal(gf180_oai21_raw, tmp_path)
    taps = lambda ly: ((region(ly, L["comp"]) & region(ly, L["pplus"])) - region(ly, L["nwell"])) + \
        ((region(ly, L["comp"]) & region(ly, L["nplus"])) & region(ly, L["nwell"]))
    assert not taps(a).is_empty() and taps(b).is_empty()
    assert (region(b, L["contact"]) - region(b, L["comp"]) - region(b, L["poly"])).is_empty()
    m1 = region(b, L["metal1"])
    assert m1.notch_check(230).count() == 0 and m1.space_check(230).count() == 0
    assert (region(a, L["metal1"]).moved(box(b).width() - box(a).width(), 0) - m1).is_empty()   # metal only added
