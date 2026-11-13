import klayout.db as kdb

from pdks.sky130 import adapter


def load(path):
    ly = kdb.Layout()
    ly.read(str(path))
    return ly


def test_inv_generates(generated_inv_raw):
    assert generated_inv_raw.stat().st_size > 0


def test_inv_uses_sky130_layers(generated_inv_raw):
    ly = load(generated_inv_raw)
    pairs = {(i.layer, i.datatype) for i in ly.layer_infos()}
    for need in [(66, 20), (65, 20), (66, 44), (67, 20), (64, 20), (93, 44), (94, 20), (235, 4), (67, 16), (67, 5)]:
        assert need in pairs, need


def test_inv_on_grid(generated_inv_raw):
    ly = load(generated_inv_raw)
    top = ly.top_cell()
    for li in ly.layer_indexes():
        for s in top.shapes(li).each():
            b = s.bbox()
            assert all(v % 5 == 0 for v in (b.left, b.bottom, b.right, b.top))   # dbu = 1 nm


def test_inv_has_two_gates_and_labels(generated_inv_raw):
    ly = load(generated_inv_raw)
    top = ly.top_cell()
    poly = kdb.Region(top.begin_shapes_rec(ly.layer(66, 20)))
    diff = kdb.Region(top.begin_shapes_rec(ly.layer(65, 20)))
    assert (poly & diff).merged().count() == 2
    texts = {s.text.string for s in top.shapes(ly.layer(67, 5)).each() if s.is_text()}
    assert {"A", "Y", "VPWR", "VGND"} <= texts


def test_cell_size_reads_cellbox(generated_inv_raw):
    w, h = adapter.cell_size(generated_inv_raw, "INV_1")
    assert 0.5 < w < 5 and 2 < h < 6
