#!/usr/bin/env python3
"""Run the Astran flow for a PDK adapter and print a result table.

    python3 astran_pdk.py <pdk> [cell ...] [--out DIR] [--astran PATH]

This driver knows nothing about any PDK. It imports pdks.<pdk>.adapter and calls the
functions of the contract in pdks/README.md.

Exit status: 0 if every cell passed gen, drc, drc-abut and lvs; 1 if any cell failed;
2 if the environment is unusable (unknown PDK, missing tools or PDK, missing astran-cli).
"""
import argparse
import importlib
import subprocess
import sys
import traceback
from pathlib import Path

from pdks.common import AdapterError, build_abutment

HEADER = ["cell", "gen", "drc", "drc-abut", "lvs", "w×h", "ref w×h", "area", "ref area", "ratio"]
ASTRAN_TIMEOUT = 3600


class Row:
    def __init__(self, cell):
        self.cell = cell
        self.gen = self.drc = self.abut = self.lvs = "-"
        self.size = self.ref_size = self.area = self.ref_area = self.ratio = "-"
        self.reasons = []        # (stage, message)
        self.ok = True
        self.final = None        # final GDS, once generated
        self.top = None

    def fail(self, stage, message):
        self.ok = False
        self.reasons.append((stage, message))

    def cells(self):
        return [self.cell, self.gen, self.drc, self.abut, self.lvs, self.size,
                self.ref_size, self.area, self.ref_area, self.ratio]


def _describe(e: Exception) -> str:
    if isinstance(e, AdapterError):
        return str(e)
    traceback.print_exc(file=sys.stderr)
    return str(e) or type(e).__name__


def _check_summary(results):
    """(display, failures) for a list of (checker, CheckResult)."""
    bad = [(n, r) for n, r in results if not r.ok]
    if not bad:
        return "pass", []
    return "FAIL(" + ",".join(f"{n}:{r.count}" for n, r in bad) + ")", [f"{n}: {r.detail}" for n, r in bad]


def generate(adapter, cell: str, cell_dir: Path, astran_cli: Path, row: Row) -> bool:
    """netlists -> script -> astran-cli -> postprocess. Returns True on success."""
    try:
        cell_dir.mkdir(parents=True, exist_ok=True)
        sp, ref, run, log = (cell_dir / n for n in ("astran.sp", "ref.spice", "cell.run", "astran.log"))
        raw, final = cell_dir / "raw.gds", cell_dir / "final.gds"
        astran_cell = adapter.write_astran_netlist(cell, sp)
        adapter.write_lvs_netlist(cell, ref)
        run.write_text(adapter.astran_script(astran_cell, sp, raw))
        with open(log, "w") as f:
            try:
                rc = subprocess.run([str(astran_cli), run.name], cwd=cell_dir, stdout=f,
                                    stderr=subprocess.STDOUT, timeout=ASTRAN_TIMEOUT,
                                    stdin=subprocess.DEVNULL).returncode
            except subprocess.TimeoutExpired:
                raise AdapterError(f"astran-cli timed out after {ASTRAN_TIMEOUT}s, see {log}")
        if rc != 0:
            raise AdapterError(f"astran-cli failed (exit code {rc}), see {log}")
        if not raw.exists() or raw.stat().st_size == 0:
            raise AdapterError(f"astran-cli produced no GDS, see {log}")
        row.top = adapter.layout_name(cell)
        adapter.postprocess(raw, final, cell)
        row.final = final
        row.gen = "ok"
        return True
    except Exception as e:
        row.gen = "FAIL"
        row.fail("gen", _describe(e))
        return False


def check_cell(adapter, cell: str, cell_dir: Path, row: Row) -> None:
    try:
        display, why = _check_summary(adapter.drc(row.final, row.top, cell_dir))
        row.drc = display
        for w in why:
            row.fail("drc", w)
    except Exception as e:
        row.drc = "FAIL"
        row.fail("drc", _describe(e))
    try:
        r = adapter.lvs(row.final, row.top, cell_dir / "ref.spice", cell_dir)
        row.lvs = "pass" if r.ok else "FAIL"
        if not r.ok:
            row.fail("lvs", r.detail)
    except Exception as e:
        row.lvs = "FAIL"
        row.fail("lvs", _describe(e))
    try:
        w, h = adapter.cell_size(row.final, row.top)
        rw, rh = adapter.reference_size(cell)
        row.size, row.ref_size = f"{w:.3f}×{h:.3f}", f"{rw:.3f}×{rh:.3f}"
        row.area, row.ref_area = f"{w * h:.3f}", f"{rw * rh:.3f}"
        row.ratio = f"{(w * h) / (rw * rh):.2f}"
    except Exception as e:
        row.fail("size", _describe(e))


def check_abutment(adapter, row: Row, others: list, cell_dir: Path) -> None:
    try:
        arr = cell_dir / "abut.gds"
        name = build_abutment(row.final, row.top, [(o.final, o.top) for o in others],
                              adapter.BOUNDARY_LAYER, arr)
        display, why = _check_summary(adapter.drc(arr, name, cell_dir / "abut"))
        row.abut = display
        for w in why:
            row.fail("drc-abut", w)
    except Exception as e:
        row.abut = "FAIL"
        row.fail("drc-abut", _describe(e))


def print_table(rows):
    table = [HEADER] + [r.cells() for r in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(HEADER))]
    for line in table:
        print("  ".join(c.ljust(w) for c, w in zip(line, widths)).rstrip())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="astran_pdk.py", description=__doc__.split("\n\n")[0])
    p.add_argument("pdk")
    p.add_argument("cells", nargs="*")
    p.add_argument("--out", default=None)
    p.add_argument("--astran", default=None)
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)

    try:
        adapter = importlib.import_module(f"pdks.{a.pdk}.adapter")
    except ImportError as e:
        print(f"error: no adapter for PDK '{a.pdk}' ({e})", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parent
    cli = Path(a.astran) if a.astran else root / "Astran/build/bin/astran-cli"
    if not cli.is_file():
        print(f"error: astran-cli not found at {cli} (build it: make -C Astran -f cli.mk)", file=sys.stderr)
        return 2
    try:
        adapter.check_environment()
    except Exception as e:
        print(f"error: {_describe(e)}", file=sys.stderr)
        return 2

    out = Path(a.out) if a.out else Path("out") / a.pdk
    out = out.resolve()
    rows = []
    for cell in (a.cells or adapter.DEFAULT_CELLS):
        row = Row(cell)
        rows.append(row)
        if generate(adapter, cell, out / cell, cli.resolve(), row):
            check_cell(adapter, cell, out / cell, row)
    good = [r for r in rows if r.final is not None]
    for r in good:
        check_abutment(adapter, r, [o for o in good if o is not r], out / r.cell)

    print_table(rows)
    for r in rows:
        for stage, message in r.reasons:
            print(f"{r.cell}: {stage}: {message}")
    for line in adapter.notes():
        print(line)
    return 0 if all(r.ok for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
