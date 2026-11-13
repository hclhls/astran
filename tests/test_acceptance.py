import subprocess

import pytest

import astran_pdk


def row(out, cell):
    return next(l for l in out.splitlines() if l.startswith(cell))


@pytest.mark.slow
def test_four_cells_clean(astran_cli, tmp_path, capsys):
    rc = astran_pdk.main(["sky130", "--out", str(tmp_path), "--astran", str(astran_cli)])
    out = capsys.readouterr().out
    for cell in ["inv", "nand2", "nor2", "a21oi"]:
        assert row(out, cell).split()[1:5] == ["ok", "pass", "pass", "pass"], out
    assert rc == 0


@pytest.mark.slow
def test_flow_is_deterministic(astran_cli, tmp_path, capsys):
    sizes = []
    for i in range(2):
        astran_pdk.main(["sky130", "inv", "nor2", "--out", str(tmp_path / str(i)), "--astran", str(astran_cli)])
        out = capsys.readouterr().out
        sizes.append([row(out, c).split()[5] for c in ("inv", "nor2")])
    assert sizes[0] == sizes[1]


@pytest.mark.slow
def test_no_pdk_names_in_generator(repo_root):
    hits = subprocess.run(["grep", "-rniE", r"sky130|gf180|dualgate|\bnpc\b|hvtp|\blicon|\bli1\b|\bmcon\b", str(repo_root / "Astran/src")],
                          capture_output=True, text=True).stdout
    assert hits == ""
