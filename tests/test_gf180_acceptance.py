from pathlib import Path

import klayout.db as kdb
import pytest

import astran_pdk
from helpers import load, region
from pdks.gf180.pdk import LAYERS


def row(out, cell):
    return next(l for l in out.splitlines() if l.startswith(cell))


@pytest.mark.slow
def test_four_cells_clean(astran_cli, gf180_pdk, tmp_path, capsys):
    rc = astran_pdk.main(["gf180", "--out", str(tmp_path), "--astran", str(astran_cli)])
    out = capsys.readouterr().out
    for cell in ["inv", "nand2", "nor2", "aoi21"]:
        assert row(out, cell).split()[1:5] == ["ok", "pass", "pass", "pass"], out
    assert rc == 0


@pytest.mark.slow
def test_flow_is_deterministic(astran_cli, gf180_pdk, tmp_path, capsys):
    sizes = []
    for i in range(2):
        astran_pdk.main(["gf180", "inv", "nor2", "--out", str(tmp_path / str(i)), "--astran", str(astran_cli)])
        out = capsys.readouterr().out
        sizes.append([row(out, c).split()[5] for c in ("inv", "nor2")])
    assert sizes[0] == sizes[1]


@pytest.mark.slow
def test_gate_lengths_match_reference_netlist(astran_cli, gf180_pdk, tmp_path, capsys):
    astran_pdk.main(["gf180", "nand2", "--out", str(tmp_path), "--astran", str(astran_cli)])
    capsys.readouterr()
    ly = load(tmp_path / "nand2" / "final.gds")
    gates = region(ly, LAYERS["poly"]) & region(ly, LAYERS["comp"])
    nwell = region(ly, LAYERS["nwell"])
    n = (gates - nwell).merged()
    p = (gates & nwell).merged()
    assert {q.bbox().width() for q in n.each()} == {600}      # nfet_06v0 L = 0.6 um
    assert {q.bbox().width() for q in p.each()} == {500}      # pfet_06v0 L = 0.5 um


README = Path(__file__).resolve().parent.parent / "pdks/gf180/README.md"


def test_klayout_switches_are_documented():
    from pdks.gf180 import checks
    text = README.read_text()
    for key, value in checks.KLAYOUT_SWITCHES.items():
        if value == "false":
            line = next((l for l in text.splitlines() if key in l and "off" in l.lower()), None)
            assert line and len(line.split()) > 6, f"switch {key}=false needs a reason in pdks/gf180/README.md"


def test_readme_lists_every_layer_of_the_adapter():
    text = README.read_text()
    for name, (layer, datatype) in LAYERS.items():
        assert f"{layer}/{datatype}" in text, f"{name} ({layer}/{datatype}) missing from pdks/gf180/README.md"
