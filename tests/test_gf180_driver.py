import pytest

import astran_pdk
from helpers import make_gds
from pdks.common import build_abutment
from pdks.gf180 import adapter


def row(out, cell):
    return next(l for l in out.splitlines() if l.startswith(cell))


@pytest.mark.slow
def test_driver_runs_gf180_inv_and_prints_a_table_row(astran_cli, gf180_pdk, tmp_path, capsys):
    rc = astran_pdk.main(["gf180", "inv", "--out", str(tmp_path), "--astran", str(astran_cli)])
    out = capsys.readouterr().out
    assert rc in (0, 1)                       # a result, never a traceback
    assert "Traceback" not in out
    assert out.splitlines()[0].split() == astran_pdk.HEADER[:5] + ["w×h", "ref", "w×h", "area", "ref", "area", "ratio"]
    assert len(row(out, "inv").split()) == 10
    assert "2.240×3.920" in row(out, "inv")   # reference size


# Review Focus 2
def test_missing_pdk_exits_2_with_fetch_hint(monkeypatch, tmp_path, capsys, astran_cli):
    monkeypatch.delenv("ASTRAN_GF180_DIR", raising=False)
    monkeypatch.setenv("PDK_ROOT", str(tmp_path / "root"))
    rc = astran_pdk.main(["gf180", "--out", str(tmp_path), "--astran", str(astran_cli)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "ciel enable --pdk-family gf180mcu" in err and "Traceback" not in err


def test_bad_pdk_directory_variable_exits_2_naming_it(monkeypatch, tmp_path, capsys, astran_cli):
    monkeypatch.setenv("ASTRAN_GF180_DIR", str(tmp_path / "typo"))
    rc = astran_pdk.main(["gf180", "--out", str(tmp_path), "--astran", str(astran_cli)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "ASTRAN_GF180_DIR" in err and "Traceback" not in err


# Review Focus 1
@pytest.mark.slow
def test_abutment_catches_violation_that_only_exists_when_abutted(gf180_pdk, tmp_path):
    # metal1 bars 0.10 um from each side of the cell edge: legal alone, 0.20 < 0.23 apart at every interface.
    # y 1.43-1.69 is the band between the tap cell's two rails (so the bars never meet its metal), 0.6 um wide
    # for the minimum area; the wells are drawn so the neighbouring tap cells' wells join up.
    cell = make_gds(tmp_path, {(34, 0): [(0.10, 1.43, 0.70, 1.69), (1.30, 1.43, 1.90, 1.69)],
                               (21, 0): [(-0.43, 1.76, 2.43, 4.35)], (204, 0): [(-0.43, -0.43, 2.43, 1.76)]},
                    cellbox=(0, 0, 2.0, 3.92), cellbox_pair=(0, 0), name="X_1", filename="cell.gds")
    alone = adapter.drc(cell, "X_1", tmp_path / "alone")
    assert all(r.ok for _, r in alone), [(n, r.detail) for n, r in alone]
    name = build_abutment(cell, "X_1", [], adapter.BOUNDARY_LAYER, tmp_path / "arr.gds")
    arr = adapter.drc(tmp_path / "arr.gds", name, tmp_path / "arr")
    assert all(not r.ok and r.count > 0 for _, r in arr), [(n, r.detail) for n, r in arr]
