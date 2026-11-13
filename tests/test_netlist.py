import pytest

from pdks.common import AdapterError
from pdks.sky130 import netlist, pdk


def test_inv_astran_netlist(tmp_path):
    name = netlist.write_astran_netlist("inv", tmp_path / "inv.sp")
    text = (tmp_path / "inv.sp").read_text().upper().split("\n")
    assert name == "INV_1"
    assert text[0].split() == [".SUBCKT", "INV_1", "A", "Y", "VPWR", "VGND"] or \
           sorted(text[0].split()[2:]) == ["A", "VGND", "VPWR", "Y"]
    m = [l.split() for l in text if l.startswith("M")]
    assert len(m) == 2
    assert {l[5] for l in m} == {"NMOS", "PMOS"}
    assert all("VNB" not in l and "VPB" not in l for l in m)
    n = next(l for l in m if l[5] == "NMOS")
    assert "L=0.15U" in n and "W=0.65U" in n and n[4] == "VGND"


def test_a21oi_has_six_devices(tmp_path):
    netlist.write_astran_netlist("a21oi", tmp_path / "x.sp")
    assert sum(l.upper().startswith("M") for l in (tmp_path / "x.sp").read_text().splitlines()) == 6


def test_lvs_reference_uses_pdk_devices(tmp_path):
    netlist.write_lvs_netlist("nand2", tmp_path / "ref.spice")
    t = (tmp_path / "ref.spice").read_text()
    assert ".subckt astran_sky130__nand2_1" in t
    assert t.count("sky130_fd_pr__nfet_01v8") == 2 and t.count("sky130_fd_pr__pfet_01v8_hvt") == 2
    assert "VNB" not in t and "VPB" not in t


# Review Focus 5
def test_multiplicity_is_expanded():
    cdl = """.SUBCKT sky130_fd_sc_hd__fake_1 A VGND VNB VPB VPWR Y
MMN0 Y A VGND VNB nfet_01v8 m=2 w=0.65 l=0.15 mult=1
+ sa=0.265
MMP0 Y A VPWR VPB pfet_01v8_hvt m=1 w=1.0 l=0.15 mult=1
.ENDS
"""
    devs = netlist.parse_cdl_subckt(cdl, "sky130_fd_sc_hd__fake_1").devices
    assert len(devs) == 3


def test_unknown_model_is_an_error():
    cdl = ".SUBCKT sky130_fd_sc_hd__fake_1 A VGND VNB VPB VPWR Y\nMM0 Y A VGND VNB nfet_g5v0d10v5 m=1 w=1 l=0.5\n.ENDS\n"
    with pytest.raises(AdapterError, match="nfet_g5v0d10v5"):
        netlist.parse_cdl_subckt(cdl, "sky130_fd_sc_hd__fake_1")


def test_unknown_cell_is_an_error(tmp_path):
    with pytest.raises(AdapterError, match="nosuchcell"):
        netlist.write_astran_netlist("nosuchcell", tmp_path / "x.sp")


# Review Focus 4
def test_pdk_not_found_lists_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("PDK_ROOT", str(tmp_path))
    monkeypatch.delenv("ASTRAN_SKY130_DIR", raising=False)
    with pytest.raises(AdapterError) as e:
        pdk.pdk_dir()
    assert str(tmp_path) in str(e.value)
