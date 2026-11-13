import pytest

import astran_pdk
from astran_pdk import main
from pdks.common import AdapterError


def row(out, cell):
    return next(l for l in out.splitlines() if l.startswith(cell))


def args(e, *cells, **kw):
    return ["fakepdk", *cells, "--out", str(e.out), "--astran", str(e.cli)]


def test_all_pass_exit_0(fake_env, capsys):
    assert main(args(fake_env, "good")) == 0
    out = capsys.readouterr().out
    r = row(out, "good")
    assert r.split()[1:5] == ["ok", "pass", "pass", "pass"]
    assert "6.000" in r and "3.000" in r and "2.00" in r        # area, ref area, ratio


def test_header_columns(fake_env, capsys):
    main(args(fake_env, "good"))
    header = capsys.readouterr().out.splitlines()[0].split()
    assert header[:5] == ["cell", "gen", "drc", "drc-abut", "lvs"]


# Review Focus 3
def test_failures_are_isolated_and_reported(fake_env, capsys):
    rc = main(args(fake_env))
    out = capsys.readouterr().out
    assert rc == 1
    assert row(out, "good").split()[1:5] == ["ok", "pass", "pass", "pass"]
    assert row(out, "nodrc").split()[2].startswith("FAIL(")
    assert row(out, "nogds").split()[1:5] == ["FAIL", "-", "-", "-"]
    assert row(out, "missing").split()[1] == "FAIL"
    assert "missing: gen: cell missing not in library" in out
    assert "nogds: gen:" in out


def test_failed_cells_are_not_abutment_neighbours(fake_env, monkeypatch):
    seen = []
    real = astran_pdk.build_abutment

    def spy(cell_gds, top, neighbours, boundary, out):
        seen.append((top, [n for _, n in neighbours]))
        return real(cell_gds, top, neighbours, boundary, out)

    monkeypatch.setattr(astran_pdk, "build_abutment", spy)
    main(args(fake_env))
    tops = {t for t, _ in seen}
    assert tops == {"fake_good", "fake_nodrc"}
    for t, ns in seen:
        assert "fake_nogds" not in ns and "fake_missing" not in ns and t not in ns
    assert dict(seen)["fake_good"] == ["fake_nodrc"]


def test_stage_exception_fails_only_that_cell(fake_env, capsys, monkeypatch):
    def lvs(gds, top, ref, wd):
        if "nodrc" in top:
            raise RuntimeError("tool exploded")
        return _ok(wd)

    monkeypatch.setattr(fake_env.adapter, "lvs", lvs)
    rc = main(args(fake_env, "good", "nodrc"))
    out = capsys.readouterr().out
    assert rc == 1
    assert row(out, "good").split()[4] == "pass"
    assert row(out, "nodrc").split()[4] == "FAIL"
    assert "nodrc: lvs: tool exploded" in out


def _ok(wd):
    from pdks.common import CheckResult
    from pathlib import Path
    return CheckResult(True, 0, Path(wd) / "r", "ok")


# Review Focus 4
def test_environment_error_exits_2_before_any_cell(fake_env, capsys, monkeypatch):
    def bad():
        raise AdapterError("PDK not found: tried /a, /b")
    monkeypatch.setattr(fake_env.adapter, "check_environment", bad)
    assert main(args(fake_env, "good")) == 2
    assert "PDK not found: tried /a, /b" in capsys.readouterr().err
    assert not (fake_env.out / "good").exists()


def test_unknown_pdk_exits_2(capsys):
    assert main(["nosuchpdk"]) == 2


def test_missing_astran_cli_exits_2(fake_env):
    assert main(["fakepdk", "good", "--out", str(fake_env.out), "--astran", "/nonexistent"]) == 2
    assert not fake_env.out.exists()


def test_notes_printed(fake_env, capsys):
    main(args(fake_env, "good"))
    assert "note: fake adapter" in capsys.readouterr().out


def test_driver_has_no_pdk_knowledge(repo_root):
    src = (repo_root / "astran_pdk.py").read_text().lower()
    assert all(w not in src for w in ["sky130", "li1", "magic", "netgen", "235"])
