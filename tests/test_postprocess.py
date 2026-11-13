import pytest

import klayout.db as kdb

from helpers import load, make_gds, region, same
from pdks.common import AdapterError
from pdks.sky130.pdk import LAYERS
from pdks.sky130.postprocess import postprocess

CELL = (0, 0, 3.0, 3.4)
NW = LAYERS["nwell"]; DIFF = LAYERS["diff"]; TAP = LAYERS["tap"]; POLY = LAYERS["poly"]
LICON = LAYERS["licon1"]; NPC = LAYERS["npc"]; HVT = LAYERS["hvtp"]
NSDM = LAYERS["nsdm"]; PSDM = LAYERS["psdm"]


def run(tmp_path, shapes, cell=CELL):
    gds = make_gds(tmp_path, shapes, cell)
    out = tmp_path / "out.gds"
    postprocess(gds, out, "x")
    return load(out)


def bbox_um(r: kdb.Region):
    b = r.bbox()
    return tuple(round(v / 1000, 3) for v in (b.left, b.bottom, b.right, b.top))


def test_drawn_layers_untouched(generated_inv_raw, tmp_path):
    out = tmp_path / "o.gds"
    postprocess(generated_inv_raw, out, "inv")
    a, b = load(generated_inv_raw), load(out)
    for pair in [(66, 20), (66, 44), (67, 20), (67, 44), (68, 20)]:
        assert same(region(a, pair), region(b, pair)), pair
    # diff may only move to tap, never change shape
    assert same(region(a, (65, 20)), region(b, (65, 20)) + region(b, (65, 44)))


def test_top_cell_renamed(generated_inv_raw, tmp_path):
    out = tmp_path / "o.gds"
    postprocess(generated_inv_raw, out, "inv")
    ly = load(out)
    assert ly.top_cell().name == "astran_sky130__inv_1"
    assert ly.cells() == 1


def test_inv_gets_derived_layers(generated_inv_raw, tmp_path):
    out = tmp_path / "o.gds"
    postprocess(generated_inv_raw, out, "inv")
    ly = load(out)
    assert not region(ly, TAP).is_empty() and not region(ly, HVT).is_empty()
    assert not region(ly, NPC).is_empty()


def test_tap_reclassified(tmp_path):
    ly = run(tmp_path, {DIFF: [(0.5, 0.2, 2.5, 0.35)], PSDM: [(0.3, 0.0, 2.7, 0.55)]})
    assert region(ly, DIFF).is_empty()
    assert bbox_um(region(ly, TAP)) == (0.5, 0.2, 2.5, 0.35)


def test_n_tap_inside_nwell_reclassified(tmp_path):
    ly = run(tmp_path, {DIFF: [(0.5, 3.05, 2.5, 3.2)], NSDM: [(0.3, 2.9, 2.7, 3.4)], NW: [(-0.2, 1.5, 3.2, 3.6)]})
    assert region(ly, DIFF).is_empty() and not region(ly, TAP).is_empty()


def test_transistor_diff_stays_diff(tmp_path):
    ly = run(tmp_path, {DIFF: [(0.5, 0.2, 1.5, 0.85)], POLY: [(0.9, 0.0, 1.05, 1.0)],
                        NSDM: [(0.3, 0.0, 1.7, 1.0)]})
    assert bbox_um(region(ly, DIFF)) == (0.5, 0.2, 1.5, 0.85)
    assert region(ly, TAP).is_empty()


def test_npc_around_poly_contact(tmp_path):
    ly = run(tmp_path, {POLY: [(0.8, 0.8, 1.4, 1.4)], LICON: [(1.0, 1.0, 1.17, 1.17)]})
    assert bbox_um(region(ly, NPC)) == (0.9, 0.9, 1.27, 1.27)


def test_no_npc_for_diff_contact(tmp_path):
    ly = run(tmp_path, {DIFF: [(0.8, 0.8, 1.4, 1.4)], LICON: [(1.0, 1.0, 1.17, 1.17)]})
    assert region(ly, NPC).is_empty()


def test_close_npc_shapes_merge(tmp_path):
    ly = run(tmp_path, {POLY: [(0.8, 0.8, 2.4, 1.4)],
                        LICON: [(1.0, 1.0, 1.17, 1.17), (1.57, 1.0, 1.74, 1.17)]})   # edges 0.4 apart
    assert region(ly, NPC).count() == 1


def test_hvtp_over_pmos_only(tmp_path):
    ly = run(tmp_path, {
        DIFF: [(0.5, 0.2, 1.5, 0.85), (0.5, 2.0, 1.5, 3.0)],
        POLY: [(0.9, 0.0, 1.05, 3.4)], NW: [(-0.2, 1.4, 3.2, 3.6)],
        NSDM: [(0.3, 0.0, 1.7, 1.0)], PSDM: [(0.3, 1.9, 1.7, 3.1)]})
    hv = region(ly, HVT)
    gate_p = region(ly, POLY) & region(ly, DIFF) & region(ly, NW)
    gate_n = region(ly, POLY) & region(ly, DIFF) - region(ly, NW)
    assert (gate_p.sized(55) - hv).is_empty()          # >= 0.055 around the PMOS gate
    assert (hv & gate_n).is_empty() and not hv.is_empty()


def test_hvtp_spans_cell_width(tmp_path):
    ly = run(tmp_path, {DIFF: [(0.5, 2.0, 1.5, 3.0)], POLY: [(0.9, 1.8, 1.05, 3.2)], NW: [(-0.2, 1.4, 3.2, 3.6)]})
    b = region(ly, HVT).bbox()
    assert b.left == 0 and b.right == 3000


def test_implants_reach_cell_edge(tmp_path):
    ly = run(tmp_path, {NSDM: [(0.1, 0.0, 2.5, 1.0)]})
    b = region(ly, NSDM).bbox()
    assert b.left == 0


def test_npc_near_edge_raises(tmp_path):
    with pytest.raises(AdapterError, match="npc"):
        run(tmp_path, {POLY: [(0.0, 0.8, 0.6, 1.4)], LICON: [(0.05, 1.0, 0.22, 1.17)]})


def test_output_on_grid(generated_inv_raw, tmp_path):
    out = tmp_path / "o.gds"
    postprocess(generated_inv_raw, out, "inv")
    ly = load(out)
    top = ly.top_cell()
    for li in ly.layer_indexes():
        for p in kdb.Region(top.begin_shapes_rec(li)).each():
            for pt in p.each_point_hull():
                assert pt.x % 5 == 0 and pt.y % 5 == 0


def test_tap_implant_follows_tap_type(tmp_path):
    # Astran draws the main nsdm/psdm over the whole half cell, tap strips included, so the
    # implants overlap on the taps. The p-tap must end up in psdm only, the n-tap in nsdm only.
    ly = run(tmp_path, {
        DIFF: [(0.0, 0.0, 3.0, 0.29), (0.0, 3.11, 3.0, 3.4), (0.5, 0.7, 1.5, 1.3), (0.5, 2.0, 1.5, 2.6)],
        POLY: [(0.9, 0.5, 1.05, 1.5), (0.9, 1.8, 1.05, 2.8)],
        NW: [(-0.2, 1.5, 3.2, 3.6)],
        NSDM: [(-0.1, -0.1, 3.1, 1.5), (0.0, 3.0, 3.0, 3.5)],
        PSDM: [(-0.1, 1.5, 3.1, 3.5), (0.0, -0.1, 3.0, 0.4)]})
    ptap = region(ly, TAP) - region(ly, NW)
    ntap = region(ly, TAP) & region(ly, NW)
    assert not ptap.is_empty() and not ntap.is_empty()
    assert (ptap & region(ly, NSDM)).is_empty() and (ntap & region(ly, PSDM)).is_empty()
    assert (ptap - region(ly, PSDM)).is_empty() and (ntap - region(ly, NSDM)).is_empty()
    assert (ptap.sized(125) - region(ly, PSDM)).is_empty()       # psdm still encloses the p-tap by 0.125
    # transistor diffusion keeps its implant
    assert (region(ly, DIFF) - region(ly, NSDM) - region(ly, PSDM)).is_empty()
