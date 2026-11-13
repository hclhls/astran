import pytest

from helpers import make_gds
from pdks.sky130 import adapter, checks

INV = "sky130_fd_sc_hd__inv_1"


def test_magic_drc_passes_foundry_inv(hd_inv, tmp_path):
    r = checks.magic_drc(hd_inv.drc_gds, hd_inv.drc_top, tmp_path)
    assert r.ok and r.count == 0 and r.report.exists()


def test_magic_drc_flags_tapless_foundry_inv(hd_inv, tmp_path):
    # no waiver: a lone hd cell has no taps, and full DRC says so
    r = checks.magic_drc(hd_inv.gds, INV, tmp_path)
    assert not r.ok and r.count > 0


def test_klayout_drc_passes_foundry_inv(hd_inv, tmp_path):
    r = checks.klayout_drc(hd_inv.gds, INV, tmp_path)
    assert r.ok and r.count == 0


def test_lvs_matches_foundry_inv(hd_inv, tmp_path):
    r = checks.netgen_lvs(hd_inv.gds, INV, hd_inv.spice, tmp_path)
    assert r.ok, r.detail


def test_drc_catches_li_spacing(tmp_path):
    gds = make_gds(tmp_path, {(67, 20): [(0, 0, 0.17, 1.0), (0.22, 0, 0.39, 1.0)]}, cellbox=(0, 0, 1, 1))  # 0.05 gap < 0.17
    m = checks.magic_drc(gds, "X_1", tmp_path / "m")
    k = checks.klayout_drc(gds, "X_1", tmp_path / "k")
    assert not m.ok and m.count > 0
    assert not k.ok and k.count > 0


def test_lvs_catches_wrong_width(hd_inv, tmp_path):
    bad = tmp_path / "bad.spice"
    bad.write_text(hd_inv.spice.read_text().replace("w=650000u", "w=900000u"))
    assert bad.read_text() != hd_inv.spice.read_text()
    assert not checks.netgen_lvs(hd_inv.gds, INV, bad, tmp_path / "l").ok


# Review Focus 2
def test_missing_tool_is_a_failure(monkeypatch, hd_inv, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))            # no magic, no klayout, no netgen
    for r in (checks.magic_drc(hd_inv.gds, "x", tmp_path / "a"), checks.klayout_drc(hd_inv.gds, "x", tmp_path / "b"),
              checks.netgen_lvs(hd_inv.gds, "x", hd_inv.spice, tmp_path / "c")):
        assert not r.ok and r.count == -1 and "did not complete" in r.detail


def test_unreadable_gds_is_a_failure(tmp_path):
    g = tmp_path / "junk.gds"
    g.write_bytes(b"not a gds")
    for r in (checks.magic_drc(g, "x", tmp_path / "a"), checks.klayout_drc(g, "x", tmp_path / "b"),
              checks.netgen_lvs(g, "x", g, tmp_path / "c")):
        assert not r.ok and r.count == -1


def test_wrong_cell_name_is_a_failure(hd_inv, tmp_path):
    assert not checks.magic_drc(hd_inv.gds, "nosuchcell", tmp_path / "a").ok


def test_reference_size():
    assert adapter.reference_size("inv") == (1.38, 2.72)


def test_notes_state_switches_and_tap_caveat():
    text = "\n".join(adapter.notes())
    assert "seal=false" in text and "floating_met=false" in text and "tap" in text.lower()


def test_wrong_cell_name_is_a_failure_everywhere(hd_inv, tmp_path):
    k = checks.klayout_drc(hd_inv.gds, "nosuchcell", tmp_path / "k")
    n = checks.netgen_lvs(hd_inv.gds, "nosuchcell", hd_inv.spice, tmp_path / "n")
    assert not k.ok and not n.ok


def test_drc_catches_violation_that_only_exists_when_abutted(tmp_path):
    # li1 bars 0.05 um from each side of the cell edge: legal alone, 0.10 < 0.17 apart at every interface
    from pdks.common import build_abutment
    cell = make_gds(tmp_path, {(67, 20): [(0.05, 0.0, 0.22, 1.0), (0.58, 0.0, 0.75, 1.0)]},
                    cellbox=(0, 0, 0.8, 1.0), name="X_1", filename="cell.gds")
    assert checks.magic_drc(cell, "X_1", tmp_path / "alone_m").ok
    assert checks.klayout_drc(cell, "X_1", tmp_path / "alone_k").ok
    name = build_abutment(cell, "X_1", [], (235, 4), tmp_path / "arr.gds")
    assert not checks.magic_drc(tmp_path / "arr.gds", name, tmp_path / "arr_m").ok
    assert not checks.klayout_drc(tmp_path / "arr.gds", name, tmp_path / "arr_k").ok
