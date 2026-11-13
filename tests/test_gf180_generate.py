import subprocess

import klayout.db as kdb
import pytest

from pdks.common import AdapterError
from pdks.gf180 import adapter, pdk

REF = {"inv": (2.24, 3.92), "nand2": (2.80, 3.92), "nor2": (3.36, 3.92), "aoi21": (4.48, 3.92)}


def test_check_environment_reports_missing_tools(gf180_pdk, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(AdapterError) as e:
        adapter.check_environment()
    for tool in ("magic", "netgen", "klayout", "highs"):
        assert tool in str(e.value)


def test_reference_sizes(gf180_pdk):
    for cell, (w, h) in REF.items():
        got = adapter.reference_size(cell)
        assert got == pytest.approx((w, h), abs=1e-6), cell


def test_astran_script_is_complete(tmp_path):
    text = adapter.astran_script("INV_1", tmp_path / "n.sp", tmp_path / "o.gds")
    assert "load technology" in text and "cellgen compact" in text
    assert text.strip().splitlines()[-1].startswith("export layout INV_1 ")


@pytest.fixture(scope="module")
def inv_raw(astran_cli, tmp_path_factory, gf180_pdk):
    wd = tmp_path_factory.mktemp("gf180_inv_raw")
    name = adapter.write_astran_netlist("inv", wd / "astran.sp")
    gds = wd / "raw.gds"
    (wd / "cell.run").write_text(adapter.astran_script(name, wd / "astran.sp", gds))
    r = subprocess.run([str(astran_cli), "cell.run"], cwd=wd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout
    return gds


def test_inv_generates_raw_gds(inv_raw):
    ly = kdb.Layout()
    ly.read(str(inv_raw))
    top = ly.top_cell()
    for name in ("contact", "poly", "comp", "metal1"):
        li = ly.find_layer(*pdk.LAYERS[name])
        assert li is not None and not kdb.Region(top.begin_shapes_rec(li)).is_empty(), name
