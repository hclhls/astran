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
