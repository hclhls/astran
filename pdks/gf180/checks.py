"""DRC (magic, klayout) and LVS (magic extraction + netgen) runners for gf180.

A checker that crashes, times out, or leaves no usable report is a failure
(ok=False, count=-1), never "0 errors"."""
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pdks.common import CheckResult, run_tool
from pdks.gf180 import pdk

# The PDK's own runner (libs.tech/klayout/drc/run_drc.py) assembles the rule deck: main.drc alone is only a
# template and runs no rules. Variant C is the PDK default stack (5 metal layers, 9K top metal).
# Switched off, each for a cell-level check:
#   connectivity: needs a full netlist context (nwell/lvpwell/dnwell connectivity), not one standard cell
#   density, antenna: chip-level checks; a single cell cannot meet a die-wide density
KLAYOUT_SWITCHES = {"variant": "C", "connectivity": "false", "density": "false", "antenna": "false"}


def _fail(tool: str, reason: str, report: Path) -> CheckResult:
    return CheckResult(False, -1, report, f"{tool} did not complete: {reason}")


def _magic_env(workdir: Path) -> dict:
    """magicrc looks for $PDK_ROOT/gf180mcuD; give it exactly that."""
    root = workdir / "pdk_root"
    root.mkdir(parents=True, exist_ok=True)
    link = root / "gf180mcuD"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(pdk.pdk_dir())
    return {"PDK_ROOT": str(root)}


def _run_magic(script: str, workdir: Path, log: Path, name: str) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / f"{name}.tcl").write_text(script)
    env = _magic_env(workdir)
    (workdir / f"{name}.rc").write_text(
        f"source {pdk.pdk_dir()}/libs.tech/magic/gf180mcuD.magicrc\nsource {workdir}/{name}.tcl\n")
    return run_tool(["magic", "-dnull", "-noconsole", "-rcfile", workdir / f"{name}.rc"],
                    workdir, log, env=env)


def magic_drc(gds: Path, top: str, workdir: Path) -> CheckResult:
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    report, why, log = workdir / "magic_drc.rpt", workdir / "magic_drc_why.txt", workdir / "magic_drc.log"
    for f in (report, why):
        f.unlink(missing_ok=True)
    script = f"""gds read {Path(gds).resolve()}
if {{[lsearch [cellname list allcells] {top}] < 0}} {{ puts "ASTRAN_NOCELL"; quit -noprompt }}
load {top}
select top cell
drc style drc(full)
drc check
drc catchup
puts "ASTRAN_DRC_BEGIN"
drc count total
puts "ASTRAN_DRC_END"
set f [open {why} w]
puts $f [drc listall why]
close $f
quit -noprompt
"""
    rc = _run_magic(script, workdir, log, "magic_drc")
    if rc != 0:
        return _fail("magic", f"exit code {rc}, see {log}", report)
    text = log.read_text(errors="replace")
    m = re.search(r"ASTRAN_DRC_BEGIN(.*?)ASTRAN_DRC_END", text, re.S)
    n = re.search(r"Total DRC errors found:\s*(\d+)", m.group(1)) if m else None
    if "ASTRAN_NOCELL" in text or not why.exists() or not n:
        return _fail("magic", f"no DRC result for cell {top}, see {log}", report)
    count = int(n.group(1))
    report.write_text(f"TOTAL {count}\n{why.read_text()}")
    return CheckResult(count == 0, count, report, f"magic: {count} errors")


def klayout_drc(gds: Path, top: str, workdir: Path) -> CheckResult:
    workdir = Path(workdir).resolve()
    run_dir = workdir / "run"
    shutil.rmtree(run_dir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    log = workdir / "klayout_drc.log"
    gds = Path(gds).resolve()
    report = run_dir / f"{gds.stem}_main.lyrdb"
    argv = [sys.executable, pdk.pdk_dir() / "libs.tech/klayout/drc/run_drc.py", f"--path={gds}",
            f"--variant={KLAYOUT_SWITCHES['variant']}", f"--topcell={top}", f"--run_dir={run_dir}",
            "--no_connectivity"]
    rc = run_tool(argv, workdir, log)
    if rc not in (0, 1):
        return _fail("klayout", f"exit code {rc}, see {log}", report)
    text = log.read_text(errors="replace")
    if "Executing rule" not in text:
        return _fail("klayout", f"the deck ran no rules, see {log}", report)
    try:
        items = ET.parse(report).getroot().find("items")
        if items is None:
            raise ValueError("no <items> element")
        count = len(items.findall("item"))
    except (OSError, ET.ParseError, ValueError) as e:
        return _fail("klayout", f"unusable report {report}: {e}", report)
    return CheckResult(count == 0, count, report, f"klayout: {count} violations")


def netgen_lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult:
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    report, spice = workdir / "lvs.rpt", workdir / "layout.spice"
    for f in (report, spice):
        f.unlink(missing_ok=True)
    script = f"""gds read {Path(gds).resolve()}
if {{[lsearch [cellname list allcells] {top}] < 0}} {{ puts "ASTRAN_NOCELL"; quit -noprompt }}
load {top}
select top cell
extract all
ext2spice lvs
ext2spice -o {spice}
quit -noprompt
"""
    rc = _run_magic(script, workdir, workdir / "extract.log", "extract")
    if rc != 0 or not spice.exists() or spice.stat().st_size == 0:
        return _fail("magic extraction", f"exit code {rc}, no netlist for cell {top}, see {workdir / 'extract.log'}", report)
    rc = run_tool(["netgen", "-batch", "lvs", f"{spice} {top}", f"{Path(ref).resolve()} {top}",
                   pdk.pdk_dir() / "libs.tech/netgen/gf180mcuD_setup.tcl", report],
                  workdir, workdir / "netgen.log")
    if rc != 0 or not report.exists() or report.stat().st_size == 0:
        return _fail("netgen", f"exit code {rc}, no report, see {workdir / 'netgen.log'}", report)
    text = report.read_text(errors="replace")
    if "property error" in text.lower():
        return CheckResult(False, 1, report, "netgen: property errors")
    if "Circuits match uniquely." in text:
        return CheckResult(True, 0, report, "netgen: circuits match")
    final = re.search(r"Final result:\s*(.*)", text)
    return CheckResult(False, 1, report, "netgen: " + (final.group(1).strip() if final else "no match reported"))
