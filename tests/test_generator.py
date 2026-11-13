"""Generic generator behaviour (technology neutral, uses the legacy 65 nm library)."""
import klayout.db as kdb

from helpers import load


def generate(run_astran, repo_root, workdir, template):
    work = repo_root / "Astran/build/Work"
    script = f'''set lpsolve "highs"
load technology "{repo_root}/tests/data/mini.rul"
load netlist "{work}/lib65.sp"
set celltemplate "{template}"
cellgen select INV0
cellgen fold 2 0
cellgen place 150 3 3 4 1 4 2
cellgen route 1 0 1 1
cellgen compact 1 0 50 2 1 1 0 0 0 600
export layout INV0 INV0.gds
'''
    r = run_astran(script, workdir)
    assert r.returncode == 0, r.stdout
    return load(workdir / "INV0.gds")


def boxes(ly, pair):
    li = ly.find_layer(*pair)
    return [] if li is None else [s.bbox() for s in ly.top_cell().shapes(li).each()]


CONT, MET1, CELLBOX = (1, 20), (67, 20), (235, 20)


def test_continuous_diff_taps_are_contacted(run_astran, repo_root, workdir):
    ly = generate(run_astran, repo_root, workdir, "Taps w/ continuous diff")
    cell = kdb.Region(ly.top_cell().begin_shapes_rec(ly.layer(*CELLBOX))).bbox()
    conts = boxes(ly, CONT)
    # a row of contacts centred on each cell boundary (bottom and top)
    assert any(b.bottom < cell.bottom < b.top for b in conts), "no contact on the bottom strip"
    assert any(b.bottom < cell.top < b.top for b in conts), "no contact on the top strip"


def test_continuous_diff_rails_are_centred_on_the_boundary(run_astran, repo_root, workdir):
    ly = generate(run_astran, repo_root, workdir, "Taps w/ continuous diff")
    cell = kdb.Region(ly.top_cell().begin_shapes_rec(ly.layer(*CELLBOX))).bbox()
    m1 = boxes(ly, MET1)
    assert any(b.bottom < cell.bottom < b.top and b.width() >= cell.width() for b in m1)
    assert any(b.bottom < cell.top < b.top and b.width() >= cell.width() for b in m1)


def test_tapless_template_is_unchanged(run_astran, repo_root, workdir):
    ly = generate(run_astran, repo_root, workdir, "Tapless")
    cell = kdb.Region(ly.top_cell().begin_shapes_rec(ly.layer(*CELLBOX))).bbox()
    # inner-half rails only: nothing of the rails below the cell box
    assert all(b.bottom >= cell.bottom for b in boxes(ly, MET1))
