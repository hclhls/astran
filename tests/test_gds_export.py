import re

import klayout.db as kdb
import pytest


def load(path):
    ly = kdb.Layout()
    ly.read(str(path))
    return ly


def cif_cellbox_um(cif, scale):
    """CBX box (w, h) in um from a CIF export. Astran writes CIF boxes as twice the
    internal integer, and an internal unit is MINSTEP (= scale) um, so one CIF unit
    is scale/2 um (the same relation the C2C script uses: scale 0.5/resolution)."""
    lines = cif.read_text().splitlines()
    for i, l in enumerate(lines):
        if l.strip() == "L CBX;":
            m = re.match(r"B (\d+) (\d+) (\d+) (\d+);", lines[i + 1].strip())
            return int(m[1]) * scale / 2, int(m[2]) * scale / 2
    raise AssertionError("no CBX layer in CIF")


def test_datatypes_and_boundaries(generated_mini_gds):
    ly = load(generated_mini_gds)
    pairs = {(i.layer, i.datatype) for i in ly.layer_infos()}
    assert (67, 20) in pairs and (67, 16) in pairs
    assert all(dt != 0 for (_, dt) in pairs)
    top = ly.top_cell()
    assert sum(top.shapes(l).size() for l in ly.layer_indexes()) > 0   # readable as polygons


def test_labels_on_label_layer(generated_mini_gds):
    ly = load(generated_mini_gds)
    top = ly.top_cell()
    texts = [s.text.string for s in top.shapes(ly.layer(67, 5)).each() if s.is_text()]
    assert "VDD" in [t.upper() for t in texts] or len(texts) >= 2


@pytest.mark.parametrize("minstep", ["0.002", "0.005"])
def test_units_follow_minstep(minstep, legacy_flow, workdir, repo_root):
    rul = workdir / "m.rul"
    text = (repo_root / "tests/data/mini.rul").read_text()
    rul.write_text(re.sub(r"^MINSTEP.*$", f"MINSTEP {minstep}", text, flags=re.M))
    legacy_flow(rul, workdir, exports=("export layout INV0 INV0.gds", "export layout INV0 INV0.cif"))
    ly = load(workdir / "INV0.gds")
    bbox = kdb.Region(ly.top_cell().begin_shapes_rec(ly.layer(235, 20))).bbox()
    w_um, h_um = cif_cellbox_um(workdir / "INV0.cif", scale=float(minstep))
    assert w_um > 0 and h_um > 0
    assert abs(bbox.width() * ly.dbu - w_um) < 0.001
    assert abs(bbox.height() * ly.dbu - h_um) < 0.001


def test_legacy_bare_numbers_export_datatype_0(legacy_flow, workdir, repo_root):
    legacy_flow(repo_root / "Astran/build/Work/tech_0065.rul", workdir)
    ly = load(workdir / "INV0.gds")
    pairs = {(i.layer, i.datatype) for i in ly.layer_infos()}
    assert pairs and all(dt == 0 for (_, dt) in pairs)
    assert (13, 0) in pairs        # MET1 keeps its bare layer number
