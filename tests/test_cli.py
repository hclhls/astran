import subprocess


def test_bad_command_exits_1(run_astran, workdir):
    r = run_astran("load technology \"/nonexistent.rul\"\n", workdir)
    assert r.returncode == 1
    assert "ERROR:" in r.stdout and ":1" in r.stdout


def test_missing_script_exits_2(astran_cli, workdir):
    r = subprocess.run([astran_cli, "nope.run"], cwd=workdir, capture_output=True, text=True)
    assert r.returncode == 2


def test_comment_and_exit(run_astran, workdir):
    r = run_astran("* a comment\nexit\nload technology \"/nonexistent.rul\"\n", workdir)
    assert r.returncode == 0


def test_legacy_flow_generates_cell(run_astran, workdir, repo_root):
    work = repo_root / "Astran/build/Work"
    script = f'''set lpsolve "highs"
load technology "{work}/tech_0065.rul"
load netlist "{work}/lib65.sp"
cellgen select INV0
cellgen fold 2 0
cellgen place 150 3 3 4 1 4 2
cellgen route 1 0 1 1
cellgen compact 1 0 50 2 1 1 0 0 0 600
export layout INV0 INV0.gds
'''
    r = run_astran(script, workdir)
    assert r.returncode == 0, r.stdout
    assert (workdir / "INV0.gds").stat().st_size > 0
