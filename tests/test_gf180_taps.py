import klayout.db as kdb
import pytest

from helpers import make_gds
from pdks.common import AdapterError, build_abutment
from pdks.gf180 import adapter, taps
from pdks.gf180.pdk import LAYERS

TIE = "gf180mcu_fd_sc_mcu7t5v0__filltie"


def tie_instances(gds, top):
    ly = kdb.Layout()
    ly.read(str(gds))
    cell = ly.cell(top)
    return [i for i in cell.each_inst() if i.cell.name == TIE], ly


def test_end_taps_put_a_tap_cell_on_each_side_of_a_lone_cell(ref_inv, tmp_path):
    name = taps.add_end_taps(ref_inv.gds, ref_inv.top, tmp_path / "t.gds")
    ties, ly = tie_instances(tmp_path / "t.gds", name)
    assert len(ties) == 2
    boxes = sorted(i.bbox().left for i in ties)
    cell_box = kdb.Region(ly.cell(ref_inv.top).begin_shapes_rec(ly.layer(*LAYERS["prBoundary"]))).bbox()
    assert boxes[0] < cell_box.left and boxes[1] >= cell_box.right - 430   # one left of the cell, one right of it


def test_lone_foundry_inv_passes_klayout_drc_once_it_has_end_taps(ref_inv, tmp_path):
    results = adapter.drc(ref_inv.gds, ref_inv.top, tmp_path)
    assert all(r.ok for _, r in results), [(n, r.detail) for n, r in results]


def test_every_row_of_an_array_gets_its_own_taps_flipped_with_the_row(ref_inv, tmp_path):
    arr = build_abutment(ref_inv.gds, ref_inv.top, [], adapter.BOUNDARY_LAYER, tmp_path / "arr.gds")
    name = taps.add_end_taps(tmp_path / "arr.gds", arr, tmp_path / "t.gds")
    ties, _ = tie_instances(tmp_path / "t.gds", name)
    assert len(ties) == 6                                  # 3 rows x 2 ends
    assert sum(1 for i in ties if i.trans.is_mirror()) == 2   # only the middle row is flipped


def test_layout_without_boundary_is_an_error(tmp_path, gf180_pdk):
    gds = make_gds(tmp_path, {(34, 0): [(0, 0, 1, 1)]}, cellbox=(0, 0, 1, 1), cellbox_pair=(1, 1))
    with pytest.raises(AdapterError):
        taps.add_end_taps(gds, "X_1", tmp_path / "t.gds")


def test_long_row_gets_taps_along_it_so_no_cell_is_far_from_one(ref_inv, tmp_path):
    # DF.13_MV / DF.14_MV: a tap within 15 um; a 50 um row with taps only at its ends breaks that
    arr = build_abutment(ref_inv.gds, ref_inv.top, [(ref_inv.gds, ref_inv.top)] * 10, adapter.BOUNDARY_LAYER,
                         tmp_path / "arr.gds")
    name = taps.add_end_taps(tmp_path / "arr.gds", arr, tmp_path / "t.gds")
    ties, ly = tie_instances(tmp_path / "t.gds", name)
    by_row = {}
    for i in ties:
        by_row.setdefault(round((i.bbox().bottom + i.bbox().top) / 2, -3), []).append(i.bbox())
    for row, boxes in by_row.items():
        xs = sorted(b.left for b in boxes)
        gaps = [(b - a) * ly.dbu for a, b in zip(xs, xs[1:])]
        assert len(xs) >= 3 and max(gaps) <= 30, (row, gaps)        # <= 15 um either side of a tap


def test_inserting_taps_does_not_overlap_or_move_cells_relative_to_each_other(ref_inv, tmp_path):
    arr = build_abutment(ref_inv.gds, ref_inv.top, [(ref_inv.gds, ref_inv.top)] * 10, adapter.BOUNDARY_LAYER,
                         tmp_path / "arr.gds")
    name = taps.add_end_taps(tmp_path / "arr.gds", arr, tmp_path / "t.gds")
    ly = kdb.Layout()
    ly.read(str(tmp_path / "t.gds"))
    pieces = kdb.Region()
    li = ly.layer(*LAYERS["prBoundary"])
    it = kdb.RecursiveShapeIterator(ly, ly.cell(name), li)
    total, n = 0, 0
    while not it.at_end():
        b = it.trans() * it.shape().bbox()
        pieces.insert(b)
        total += b.area()
        n += 1
        it.next()
    assert pieces.merged().area() == total                          # boundaries abut, none overlaps another
    assert pieces.merged().count() == 1                             # three equally long rows stacked: one rectangle, no gaps


def test_tap_insertion_keeps_every_neighbour_pair_adjacent_somewhere(ref_inv, tmp_path):
    # Review finding I1: a tap cell dropped between two cells removes that interface from the abutment check
    import klayout.db as kdb
    others = []
    for k in range(8):                       # eight uniquely named neighbours: every interface occurs exactly once
        ly = kdb.Layout()
        ly.read(str(ref_inv.gds))
        ly.cell(ref_inv.top).name = f"other_{k}"
        ly.write(str(tmp_path / f"other_{k}.gds"))
        others.append((tmp_path / f"other_{k}.gds", f"other_{k}"))
    arr = build_abutment(ref_inv.gds, ref_inv.top, others, adapter.BOUNDARY_LAYER, tmp_path / "arr.gds")
    name = taps.add_end_taps(tmp_path / "arr.gds", arr, tmp_path / "t.gds")

    def pairs(gds, top):
        lay = kdb.Layout()
        lay.read(str(gds))
        li = lay.layer(*LAYERS["prBoundary"])
        it = kdb.RecursiveShapeIterator(lay, lay.cell(top), li)
        rows = {}
        while not it.at_end():
            leaf = it.cell().name.split("$")[0]
            if leaf != "gf180mcu_fd_sc_mcu7t5v0__filltie":
                tr = it.trans()
                rows.setdefault((tr * it.shape().bbox()).bottom, []).append(((tr * it.shape().bbox()), leaf, tr.is_mirror()))
            it.next()
        out = set()
        for items in rows.values():
            items.sort(key=lambda t: t[0].left)
            out |= {(a[1:], b[1:]) for a, b in zip(items, items[1:]) if a[0].right == b[0].left}
        return out

    before, after = pairs(tmp_path / "arr.gds", arr), pairs(tmp_path / "t.gds", name)
    assert before and before <= after, before - after
