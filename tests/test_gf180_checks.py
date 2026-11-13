import stat

import pytest

from helpers import make_gds
from pdks.gf180 import checks


def test_magic_drc_passes_foundry_inv(ref_inv, tmp_path):
    r = checks.magic_drc(ref_inv.gds, ref_inv.top, tmp_path)
    assert r.ok and r.count == 0 and r.report.exists(), r.detail


def test_klayout_drc_passes_foundry_inv_next_to_a_tap_cell(ref_inv, tmp_path):
    r = checks.klayout_drc(ref_inv.drc_gds, ref_inv.drc_top, tmp_path)
    assert r.ok and r.count == 0, r.detail


def test_klayout_drc_flags_tapless_foundry_inv_alone(ref_inv, tmp_path):
    # no waiver: a lone 7t cell has no taps and DF.13_MV / DF.14_MV say so
    r = checks.klayout_drc(ref_inv.gds, ref_inv.top, tmp_path)
    assert not r.ok and r.count > 0


def test_lvs_matches_foundry_inv(ref_inv, tmp_path):
    r = checks.netgen_lvs(ref_inv.gds, ref_inv.top, ref_inv.spice, tmp_path)
    assert r.ok, r.detail


def test_violation_is_reported_by_both_drc_checkers(tmp_path):
    # two metal1 bars 0.05 um apart (< 0.23)
    gds = make_gds(tmp_path, {(34, 0): [(0, 0, 0.3, 1.0), (0.35, 0, 0.65, 1.0)]},
                   cellbox=(0, 0, 1, 1), cellbox_pair=(0, 0))
    m = checks.magic_drc(gds, "X_1", tmp_path / "m")
    k = checks.klayout_drc(gds, "X_1", tmp_path / "k")
    assert not m.ok and m.count > 0, m.detail
    assert not k.ok and k.count > 0, k.detail


def test_lvs_detects_wrong_circuit(ref_inv, tmp_path, gf180_pdk):
    import re
    text = (gf180_pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice").read_text()
    m = re.search(r"^\.SUBCKT gf180mcu_fd_sc_mcu7t5v0__nand2_1 .*?^\.ENDS\n", text, re.S | re.M)
    wrong = tmp_path / "wrong.spice"
    wrong.write_text(m.group(0).replace("nand2_1", "inv_1"))
    assert not checks.netgen_lvs(ref_inv.gds, ref_inv.top, wrong, tmp_path / "l").ok


def fake_tools(tmp_path, body):
    d = tmp_path / "bin"
    d.mkdir()
    for t in ("magic", "klayout", "netgen"):
        p = d / t
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return d


# Review Focus 3
@pytest.mark.parametrize("body", ["exit 1\n", "exit 0\n"])
def test_crashing_or_silent_tool_is_a_failure(monkeypatch, ref_inv, tmp_path, body):
    monkeypatch.setenv("PATH", str(fake_tools(tmp_path, body)))
    for r in (checks.magic_drc(ref_inv.gds, "x", tmp_path / "a"), checks.klayout_drc(ref_inv.gds, "x", tmp_path / "b"),
              checks.netgen_lvs(ref_inv.gds, "x", ref_inv.spice, tmp_path / "c")):
        assert not r.ok and r.count == -1 and "did not complete" in r.detail


def test_timeout_is_a_failure(monkeypatch, ref_inv, tmp_path):
    import pdks.common as common
    monkeypatch.setenv("PATH", str(fake_tools(tmp_path, "sleep 30\n")))
    orig = common.run_tool
    monkeypatch.setattr(checks, "run_tool", lambda argv, cwd, log, timeout=600, env=None: orig(argv, cwd, log, timeout=1, env=env))
    for r in (checks.magic_drc(ref_inv.gds, "x", tmp_path / "a"), checks.klayout_drc(ref_inv.gds, "x", tmp_path / "b"),
              checks.netgen_lvs(ref_inv.gds, "x", ref_inv.spice, tmp_path / "c")):
        assert not r.ok and r.count == -1


def test_wrong_cell_name_is_a_failure_everywhere(ref_inv, tmp_path):
    assert not checks.magic_drc(ref_inv.gds, "nosuchcell", tmp_path / "m").ok
    assert not checks.klayout_drc(ref_inv.gds, "nosuchcell", tmp_path / "k").ok
    assert not checks.netgen_lvs(ref_inv.gds, "nosuchcell", ref_inv.spice, tmp_path / "n").ok


def test_unreadable_gds_is_a_failure(tmp_path):
    g = tmp_path / "junk.gds"
    g.write_bytes(b"not a gds")
    for r in (checks.magic_drc(g, "x", tmp_path / "a"), checks.klayout_drc(g, "x", tmp_path / "b"),
              checks.netgen_lvs(g, "x", g, tmp_path / "c")):
        assert not r.ok and r.count == -1
