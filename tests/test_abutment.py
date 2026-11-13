import pytest

import klayout.db as kdb

from helpers import load, make_gds, region, same
from pdks.common import AdapterError, build_abutment

B = (235, 4)
MARK = (1, 0)


@pytest.fixture
def cells(tmp_path):
    # A is 1.0 x 3.0, B is 2.0 x 3.0; the marker is off-centre so orientation is observable
    a = make_gds(tmp_path, {MARK: [(0.1, 0.2, 0.3, 0.4)], (66, 20): [(0.2, 0.2, 0.4, 2.0)]}, (0, 0, 1.0, 3.0), name="A", filename="a.gds")
    b = make_gds(tmp_path, {MARK: [(0.1, 0.2, 0.3, 0.4)]}, (0, 0, 2.0, 3.0), name="B", filename="b.gds")
    return a, b


def instances(top):
    return [(i.cell.name, i.trans) for i in top.each_inst()]


def test_self_abutment_counts(tmp_path, cells):
    a, _ = cells
    name = build_abutment(a, "A", [], B, tmp_path / "arr.gds")
    ly = load(tmp_path / "arr.gds")
    top = ly.cell(name)
    assert name == "A__abut"
    assert top.child_instances() == 9                       # 3 per row, 3 rows
    assert top.bbox().width() == 3000 and top.bbox().height() == 9000


def test_no_gaps_or_overlaps_between_boundaries(tmp_path, cells):
    a, b = cells
    name = build_abutment(a, "A", [(b, "B")], B, tmp_path / "arr.gds")
    ly = load(tmp_path / "arr.gds")
    top = ly.cell(name)
    li = ly.find_layer(*B)
    total = 0
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        total += it.shape().polygon.transformed(it.trans()).area()
        it.next()
    merged = kdb.Region(top.begin_shapes_rec(li)).merged()
    assert merged.count() == 1 and merged.is_box()
    assert total == merged.area() == top.bbox().width() * top.bbox().height()


def test_mirrored_and_flipped_instances_present(tmp_path, cells):
    a, _ = cells
    name = build_abutment(a, "A", [], B, tmp_path / "arr.gds")
    ly = load(tmp_path / "arr.gds")
    top = ly.cell(name)
    # marker boxes of every instance, in array coordinates
    marks = set()
    li = ly.find_layer(*MARK)
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        b = it.shape().bbox().transformed(it.trans())
        marks.add((b.left, b.bottom))
        it.next()
    xs = {m[0] for m in marks}
    ys = {m[1] for m in marks}
    # marker (0.1,0.2)-(0.3,0.4) in a 1.0 x 3.0 cell
    assert 100 in xs and 1700 in xs       # slot 0 normal; slot 1 mirrored in x: 1 + (1 - 0.3)
    assert 200 in ys and 5600 in ys       # row 0 normal; row 1 flipped in y: 3 + (3 - 0.4)
    assert any(t.is_mirror() for _, t in instances(top))


def test_neighbours_are_included(tmp_path, cells):
    a, b = cells
    name = build_abutment(a, "A", [(b, "B")], B, tmp_path / "arr.gds")
    ly = load(tmp_path / "arr.gds")
    top = ly.cell(name)
    assert top.child_instances() == 15                        # 5 per row
    assert top.bbox().width() == 6000                         # 1+1+1+2+1 um
    assert {n for n, _ in instances(top)} == {"A", "B"}


def test_different_heights_raise(tmp_path, cells):
    a, _ = cells
    tall = make_gds(tmp_path, {}, (0, 0, 1.0, 4.0), name="T", filename="t.gds")
    with pytest.raises(AdapterError, match="height"):
        build_abutment(a, "A", [(tall, "T")], B, tmp_path / "arr.gds")


def test_original_cell_geometry_is_unchanged(tmp_path, cells):
    a, _ = cells
    name = build_abutment(a, "A", [], B, tmp_path / "arr.gds")
    src, arr = load(a), load(tmp_path / "arr.gds")
    for pair in [MARK, (66, 20), B]:
        assert same(region(src, pair), region(arr, pair, arr.cell("A")))


def test_missing_boundary_raises(tmp_path):
    g = make_gds(tmp_path, {MARK: [(0, 0, 1, 1)]}, (0, 0, 1, 1), name="A", filename="nb.gds", cellbox_pair=(9, 9))
    with pytest.raises(AdapterError, match="boundary"):
        build_abutment(g, "A", [], B, tmp_path / "arr.gds")
