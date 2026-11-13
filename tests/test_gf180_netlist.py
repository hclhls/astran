import pytest

from pdks.common import AdapterError
from pdks.gf180 import netlist, pdk


def test_pdk_dir_missing_names_every_path_and_fetch_command(monkeypatch, tmp_path):
    a, root = tmp_path / "nowhere", tmp_path / "root"
    monkeypatch.setenv("ASTRAN_GF180_DIR", str(a))
    monkeypatch.setenv("PDK_ROOT", str(root))
    with pytest.raises(AdapterError) as e:
        pdk.pdk_dir()
    msg = str(e.value)
    assert str(a) in msg and str(root) in msg
    assert "ciel enable --pdk-family gf180mcu " + pdk.PINNED_VERSION in msg


def test_cell_naming():
    assert netlist.ref_name("inv") == "gf180mcu_fd_sc_mcu7t5v0__inv_1"
    assert netlist.ref_name("aoi21") == "gf180mcu_fd_sc_mcu7t5v0__aoi21_1"
    assert netlist.ref_name("inv_2") == "gf180mcu_fd_sc_mcu7t5v0__inv_2"
    assert netlist.astran_name("aoi21") == "AOI21_1"
    assert netlist.layout_name("aoi21") == "astran_gf180__aoi21_1"


def test_parse_nand2_devices(gf180_pdk):
    sc = netlist.parse_spice_subckt(netlist._spice_text(), netlist.ref_name("nand2"))
    assert len(sc.devices) == 4
    kinds = {(d.model, round(d.w, 3), round(d.l, 3)) for d in sc.devices}
    assert kinds == {("nfet_06v0", 0.82, 0.6), ("pfet_06v0", 1.13, 0.5)}


def test_astran_netlist_maps_models_and_supplies(gf180_pdk, tmp_path):
    name = netlist.write_astran_netlist("nand2", tmp_path / "a.sp")
    text = (tmp_path / "a.sp").read_text()
    assert name == "NAND2_1"
    head = text.splitlines()[0].split()
    assert head[:2] == [".subckt", "NAND2_1"]
    assert set(head[2:]) == {"A1", "A2", "ZN", "VDD", "VSS"}
    assert text.count(" NMOS ") == 2 and text.count(" PMOS ") == 2
    assert "VNW" not in text and "VPW" not in text


def test_lvs_reference_keeps_the_library_body_pins(gf180_pdk, tmp_path):
    # the cells are tapless and labelled VNW / VPW like the foundry's, so the reference keeps four supply pins
    netlist.write_lvs_netlist("nand2", tmp_path / "r.sp")
    text = (tmp_path / "r.sp").read_text()
    head = text.splitlines()[0].split()
    assert head[:2] == [".subckt", "astran_gf180__nand2_1"]
    assert head[2:] == ["A1", "A2", "ZN", "VDD", "VNW", "VPW", "VSS"]
    lines = [l.split() for l in text.splitlines() if l.startswith("X")]
    assert len(lines) == 4
    for t in lines:
        assert t[4] == ("VPW" if t[5] == "nfet_06v0" else "VNW")
    assert {(t[5], t[6], t[7]) for t in lines} == {("nfet_06v0", "w=0.82u", "l=0.6u"), ("pfet_06v0", "w=1.13u", "l=0.5u")}


def test_unknown_cell_raises_adapter_error(gf180_pdk, tmp_path):
    with pytest.raises(AdapterError):
        netlist.write_astran_netlist("nosuchcell", tmp_path / "x.sp")
