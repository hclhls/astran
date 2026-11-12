# sky130 PDK Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Astran generates INV, NAND2, NOR2 and a21oi in sky130 from the hd library's netlists, and one command reports DRC (alone and abutted), LVS and area against `sky130_fd_sc_hd`.

**Architecture:** Astran's C++ gets only technology-neutral fixes (a wx-free command-line build, GDS layer/datatype and correct units, a label layer). Everything sky130-specific lives in `pdks/sky130/` as a Python adapter module plus a rule file; a PDK-neutral Python driver calls the adapter through a fixed contract. Derived layers (npc, hvtp, tap) are added by a klayout post-processing step, never by the generator.

**Tech Stack:** C++14 (g++), Python 3 with `klayout.db` and pytest, magic, netgen, klayout, HiGHS, Nix flake on top of the librelane dev shell.

**Spec:** `docs/superpowers/specs/2026-11-12-sky130-pdk-adapter-design.md`

## Global Constraints

- No sky130-specific name or branch in `Astran/src` (no `sky130`, `npc`, `hvtp`, `licon`, `li1`, `mcon`, `tap` layer names; no `if tech == ...`).
- Never waive, filter or edit DRC rules; never loosen LVS (no ignored device parameters, no black-boxing). The only switched-off checks are klayout's `seal` and `floating_met` (and density, which is a separate deck we do not run), and the driver prints which switches it used.
- No hand-edited layout. Every polygon in a checked GDS comes from Astran or the post-processing script.
- Post-processing may add or reclassify derived layers only. It must not move or resize poly, diffusion, contacts or metal.
- All output geometry on the 0.005 µm grid.
- Existing rule files (`Astran/build/Work/tech_035.rul`, `tech_0065.rul`, `tech_freePDK45.rul`) must keep loading; a bare number in the GDSII column keeps meaning datatype 0.
- Nothing from the PDK is copied into the repo. No personal absolute paths in committed files.
- The driver contains no sky130 knowledge.
- If conservative rule values cannot keep a derived layer legal, **stop and report** (cell, rule, what was tried, options). Do not teach the compactor about derived layers.
- All commands below run inside `nix develop` from the repo root `/mnt/home3/Work/astran` unless stated.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Work stays on branch `sky130-pdk-adapter`.

## Review Focus

Each line is pinned by a test in the task named in brackets.

1. A malformed GDSII value in a rule file (`67/`, `a/b`, `67/20/3`, `300/0`) raises an `AstranError` naming the file line; it must not silently become layer 0. [Task 2]
2. A checker that crashes, times out, or leaves no report is a **fail**, never "0 errors". [Task 7]
3. A requested cell that is not in the hd library, or for which Astran produces no GDS (solver missing, time limit, generator error), shows as failed in its row with the reason; the other cells still run; exit status is non-zero. [Task 9]
4. The PDK cannot be found (no `PDK_ROOT`, wrong version): one clear message naming the paths tried, exit status 2, before any cell is processed. [Task 4, Task 9]
5. An hd netlist device with `m`/`mult`/`nf` greater than 1, or a device model the adapter does not know: multiplicity is expanded into that many transistors; an unknown model is an error naming the model, not a silently dropped device. [Task 4]

## File Structure

```
flake.nix                           dev shell
.gitignore                          add out/, Astran/build/bin/astran-cli, Astran/build/obj-cli/
Astran/cli.mk                       builds the wx-free binary and C++ tests
Astran/src/main_cli.cpp             wx-free entry point (new)
Astran/src/util.h, router.h         wx includes guarded by ASTRAN_CLI
Astran/src/rules.h, rules.cpp       GdsLayer parsing, MET1L label layer
Astran/src/gds.h, gds.cpp           BOUNDARY/TEXT with datatype
Astran/src/designmng.cpp            export uses the above, nm scaling
Astran/tests/test_rules.cpp         C++ unit tests (assert-based)
astran_pdk.py                       driver (PDK-neutral)
pdks/README.md                      adapter contract
pdks/common.py                      CheckResult, run_tool, build_abutment, gds helpers
pdks/sky130/__init__.py
pdks/sky130/adapter.py              the contract's functions, delegating to the files below
pdks/sky130/pdk.py                  locating the PDK, layer constants
pdks/sky130/netlist.py              hd CDL -> Astran SPICE and LVS reference
pdks/sky130/tech.rul                Astran rules and layer map
pdks/sky130/postprocess.py          derived layers
pdks/sky130/checks.py               magic DRC, klayout DRC, netgen LVS
tests/conftest.py                   fixtures: pdk dir, astran-cli path, tmp workdir
tests/test_cli.py  test_gds_export.py  test_netlist.py  test_generate.py
tests/test_postprocess.py  test_checks.py  test_abutment.py  test_driver.py
tests/test_acceptance.py            the four cells, marked slow
```

---

### Task 1: Dev shell and wx-free command-line build

**Files:**
- Create: `flake.nix`, `Astran/cli.mk`, `Astran/src/main_cli.cpp`, `tests/conftest.py`, `tests/test_cli.py`
- Modify: `Astran/src/util.h:18-20,88-125`, `Astran/src/router.h:20`, `.gitignore`

**Interfaces:**
- Produces: binary `Astran/build/bin/astran-cli`. Usage `astran-cli <script.run>`. It runs each non-comment line through `DesignMng::readCommand`, echoing `astran> <line>`. It exits 1 at the first line whose `readCommand` returns false (printing `ERROR: <script>:<line no>`), exits 0 at end of file or on `EXIT`, and exits 2 if the script cannot be opened. It does not read `astran.cfg` and has no interactive mode.
- Produces: `make -C Astran -f cli.mk` (binary) and `make -C Astran -f cli.mk test` (builds and runs every `Astran/tests/test_*.cpp`; non-zero exit if any fails).
- Produces: pytest fixtures in `tests/conftest.py`: `astran_cli() -> pathlib.Path` (builds via make if missing), `workdir(tmp_path) -> pathlib.Path`, `repo_root() -> pathlib.Path`, and `run_astran(script_text: str, cwd: Path) -> subprocess.CompletedProcess`.
- Produces: dev shell in which these all succeed: `magic --version`, `netgen -batch quit`, `klayout -v`, `highs --version`, `python3 -c "import klayout.db, pytest"`, `g++ --version`, `make --version`.

- [ ] **Step 1: Write `flake.nix`.** Input `librelane.url = "github:librelane/librelane"` (same as `/home/jesse/Work/FlexRAM/third_party/dffram/flake.nix`; copy that directory's `flake.lock` pin for librelane so tool versions match). Output a `devShells.<system>.default` that carries everything in librelane's default shell plus `highs`, `gnumake`, `gcc`, and Python packages `pytest` and `klayout`. How the two are combined is your choice.

- [ ] **Step 2: Verify the shell**

Run: `nix develop -c sh -c 'magic --version && klayout -v && highs --version && python3 -c "import klayout.db, pytest" && g++ --version'`
Expected: five version lines, exit 0.

- [ ] **Step 3: Write the failing tests** in `tests/test_cli.py`

```python
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
```

- [ ] **Step 4: Run to see them fail**

Run: `pytest tests/test_cli.py -v`
Expected: errors because `astran-cli` does not exist.

- [ ] **Step 5: Make the sources build without wx.** In `util.h`, wrap the three `<wx/...>` includes, `icpdExecute` and the `Redirector` class in `#ifndef ASTRAN_CLI`. In `router.h`, wrap `#include <wx/process.h>` the same way. If any non-GUI `.cpp` calls `icpdExecute` or uses `Redirector`, provide a `std::system`-based `icpdExecute` under `#ifdef ASTRAN_CLI`. The GUI build must be left compiling as before (no wx code removed).

- [ ] **Step 6: Write `Astran/src/main_cli.cpp` and `Astran/cli.mk`.** `cli.mk` compiles every `src/*.cpp` except `wx*.cpp`, `icpdApp.cpp`, `icpdfrm.cpp`, with `-std=c++14 -O2 -DASTRAN_CLI -Wno-deprecated -fpermissive`, objects in `build/obj-cli/`, output `build/bin/astran-cli`. The `test` target links each `tests/test_*.cpp` against the same objects minus `main_cli.o`. `set lpsolve "highs"` must resolve through `PATH` (the solver command is passed to the shell, see `compaction.cpp:556-565`, and solver choice is a regex on the name ending in `highs`).

- [ ] **Step 7: Run the tests**

Run: `make -C Astran -f cli.mk && pytest tests/test_cli.py -v`
Expected: 4 passed. If `test_legacy_flow_generates_cell` fails inside Astran (not the build), treat it as a generator defect: debug it with the systematic-debugging skill; fixes to the generator are in scope (spec, "Generator fixes found on the way").

- [ ] **Step 8: Commit**

```bash
git add flake.nix flake.lock .gitignore Astran/cli.mk Astran/src/main_cli.cpp Astran/src/util.h Astran/src/router.h tests/conftest.py tests/test_cli.py
git commit -m "Add Nix dev shell and wx-free astran-cli build"
```

---

### Task 2: Rule file accepts GDS layer/datatype and a label layer

**Files:**
- Modify: `Astran/src/rules.h` (enum `layer_name`, `layer_labels_lst`, class `Rules`), `Astran/src/rules.cpp:69-76,130-150`
- Test: `Astran/tests/test_rules.cpp`, fixtures in `Astran/tests/data/*.rul`

**Interfaces:**
- Produces, in `rules.h`:
  ```cpp
  struct GdsLayer { int layer; int datatype; bool set; };
  GdsLayer Rules::getGDSIILayer(layer_name name);   // set==false when the column is empty
  GdsLayer Rules::getLabelGDSIILayer();             // MET1L if set, else MET1 drawing
  ```
- Produces: new `layer_name` entry `MET1L` ("Metal 1 Label", purpose `L_OTHER`), inserted directly after `MET3P` and before `TECHNAME`, with a matching row in `layer_labels_lst`.
- Rule-file syntax: the GDSII column is `<layer>` or `<layer>/<datatype>`, both integers 0–255. `getGDSIIVal` keeps returning the raw string.
- `saveGDSIILayerTable` writes the parsed layer and datatype in its two stream columns (today it writes the raw string and a literal `0`).

- [ ] **Step 1: Write the failing tests** in `Astran/tests/test_rules.cpp` (plain `main()` with a small `CHECK(cond)` macro that prints file:line and counts failures; return non-zero if any failed). Fixture `data/dt.rul` contains `MINSTEP 0.005`, `MET1 CMF 67/20 li1`, `MET1P CPF 67/16 li1`, `MET1L CLF 67/5 li1`, `POLY CPG 9 poly`.

```cpp
Rules r; r.readRules("tests/data/dt.rul");
CHECK(r.getGDSIILayer(MET1).layer == 67 && r.getGDSIILayer(MET1).datatype == 20);
CHECK(r.getGDSIILayer(POLY).layer == 9  && r.getGDSIILayer(POLY).datatype == 0);
CHECK(r.getGDSIILayer(CONT).set == false);
CHECK(r.getLabelGDSIILayer().layer == 67 && r.getLabelGDSIILayer().datatype == 5);

Rules legacy; legacy.readRules("build/Work/tech_freePDK45.rul");
CHECK(legacy.getGDSIILayer(MET1).layer == 11 && legacy.getGDSIILayer(MET1).datatype == 0);
CHECK(legacy.getLabelGDSIILayer().layer == 11 && legacy.getLabelGDSIILayer().datatype == 0);
Rules a, b; a.readRules("build/Work/tech_035.rul"); b.readRules("build/Work/tech_0065.rul");   // must not throw

// Review Focus 1: each of these files has one bad GDSII value on line 3
for (const char* f : {"bad_trailing.rul" /* 67/ */, "bad_alpha.rul" /* a/b */,
                      "bad_three.rul" /* 67/20/3 */, "bad_range.rul" /* 300/0 */}) {
    bool threw = false; string msg;
    try { Rules x; x.readRules(string("tests/data/") + f); }
    catch (AstranError& e) { threw = true; msg = e.what(); }
    CHECK(threw); CHECK(msg.find("3") != string::npos);
}
```

- [ ] **Step 2: Run to see it fail**

Run: `make -C Astran -f cli.mk test`
Expected: compile error, `getGDSIILayer` not declared.

- [ ] **Step 3: Implement** the enum entry, the table row, the two getters, validation while reading (throw `AstranError` with the file line number and the offending text), and the `saveGDSIILayerTable` change. Check how `AstranError` exposes its message (`util.h`) and use that accessor in the test if it is not `what()`.

- [ ] **Step 4: Run the tests**

Run: `make -C Astran -f cli.mk test && pytest tests/test_cli.py -q`
Expected: C++ tests report 0 failures; 4 passed.

- [ ] **Step 5: Commit**

```bash
git add Astran/src/rules.h Astran/src/rules.cpp Astran/tests
git commit -m "Parse GDS layer/datatype pairs and a label layer in rule files"
```

---

### Task 3: GDS export writes datatypes, real polygons and correct units

Three defects in today's exporter, all technology-neutral. (a) It writes no datatype. (b) It writes GDS `BOX` elements with no `BOXTYPE` record; DRC/extraction tools ignore or reject these, so shapes must be `BOUNDARY` elements. (c) Units are hardcoded to 1 nm database units while coordinates are written as `2 × internal`, which is only correct when `MINSTEP` is 0.002. sky130 uses 0.005.

**Files:**
- Modify: `Astran/src/gds.h`, `Astran/src/gds.cpp:272-345`, `Astran/src/designmng.cpp:335-376`
- Test: `tests/test_gds_export.py`, fixture `tests/data/mini.rul`

**Interfaces:**
- Consumes: `Rules::getGDSIILayer`, `Rules::getLabelGDSIILayer`, `Rules::getScale()` (Task 2).
- Produces, replacing `generateBox`/`generateLabel`:
  ```cpp
  void Gds::generateBoundary(int layer, int datatype, long x1, long y1, long x2, long y2);
  void Gds::generateText(int layer, int texttype, long x, long y, const char* text);
  ```
- Export rule: database unit stays 1 nm. A coordinate `v` in internal units is written as `v * 1000 / getScale()` nm; if `1000 % getScale() != 0` the export throws `AstranError` saying the resolution cannot be represented in nm. Layers whose `GdsLayer.set` is false are skipped with one `-> WARNING` line naming the layer. Zero-area boxes stay skipped. Labels go on `getLabelGDSIILayer()`.
- Behaviour change to record in the commit message: for rule files whose `MINSTEP` is not 0.002, exported coordinates change (they were physically wrong before), and shapes change from BOX to BOUNDARY.

- [ ] **Step 1: Write the failing tests.** `tests/data/mini.rul` is a copy of `Astran/build/Work/tech_0065.rul` with the layer map's GDSII column given datatypes (`MET1 … 67/20`, `MET1P … 67/16`, `MET1L … 67/5`, the rest `<n>/20`). The tests reuse the script from `test_legacy_flow_generates_cell` with this rule file.

```python
import klayout.db as kdb

def load(path):
    ly = kdb.Layout(); ly.read(str(path)); return ly

def test_datatypes_and_boundaries(generated_mini_gds):
    ly = load(generated_mini_gds)
    pairs = {(i.layer, i.datatype) for i in ly.layer_infos()}
    assert (67, 20) in pairs and (67, 16) in pairs
    assert all(dt != 0 for (_, dt) in pairs)
    top = ly.top_cell()
    assert sum(top.shapes(l).size() for l in ly.layer_indexes()) > 0   # readable as polygons

def test_labels_on_label_layer(generated_mini_gds):
    ly = load(generated_mini_gds); top = ly.top_cell()
    texts = [s.text.string for s in top.shapes(ly.layer(67, 5)).each() if s.is_text()]
    assert "VDD" in [t.upper() for t in texts] or len(texts) >= 2

@pytest.mark.parametrize("minstep", ["0.002", "0.005"])
def test_units_follow_minstep(minstep, run_astran, workdir, repo_root):
    # mini.rul with its MINSTEP line replaced; export INV0 as both .gds and .cif
    ly = load(workdir / "INV0.gds")
    bbox = kdb.Region(ly.top_cell().begin_shapes_rec(ly.layer(235, 20))).bbox()      # CELLBOX in mini.rul
    w_um, h_um = cif_cellbox_um(workdir / "INV0.cif", scale=float(minstep))            # helper in this file
    assert abs(bbox.width() * ly.dbu - w_um) < 0.001
    assert abs(bbox.height() * ly.dbu - h_um) < 0.001

def test_legacy_bare_numbers_export_datatype_0(run_astran, workdir, repo_root):
    # tech_0065.rul unchanged -> every (layer, datatype) has datatype 0
```

`cif_cellbox_um` gives the expected size independently of the GDS path: it reads the `CBX` box from the CIF export and converts to µm. Read `Astran/src/cif.cpp` for how CIF coordinates relate to the resolution (the C2C script uses scale `0.5/resolution`) and derive the conversion from that, not from the GDS code.

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_gds_export.py -v`
Expected: FAIL, datatypes are all 0 / shapes unreadable.

- [ ] **Step 3: Implement.** GDS records: BOUNDARY `0x0800`, LAYER `0x0D02`, DATATYPE `0x0E02`, XY `0x1003` with five points (closed), ENDEL `0x1100`; TEXT `0x0C00`, LAYER, TEXTTYPE `0x1602`, XY, STRING `0x1906` (pad to even length). Write layer and datatype as 2-byte big-endian. Remove `add_Boxtype`, `generateBox`, `generateLabel` if nothing else uses them.

- [ ] **Step 4: Run the tests**

Run: `make -C Astran -f cli.mk && pytest tests/test_gds_export.py tests/test_cli.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add Astran/src/gds.h Astran/src/gds.cpp Astran/src/designmng.cpp tests/test_gds_export.py tests/data/mini.rul tests/conftest.py
git commit -m "Export GDS boundaries with datatypes and resolution-correct units"
```

---

### Task 4: Adapter contract, PDK lookup, and sky130 netlist conversion

**Files:**
- Create: `pdks/README.md`, `pdks/__init__.py`, `pdks/common.py`, `pdks/sky130/__init__.py`, `pdks/sky130/pdk.py`, `pdks/sky130/netlist.py`, `pdks/sky130/adapter.py`
- Test: `tests/test_netlist.py`

**Interfaces:**
- Produces `pdks/common.py`:
  ```python
  class AdapterError(Exception): ...          # message is shown to the user as-is
  @dataclass
  class CheckResult:
      ok: bool; count: int; report: Path; detail: str   # detail: one line for the table
  def run_tool(argv: list[str], cwd: Path, log: Path, timeout: int = 600) -> int   # returns exit code; -1 on timeout or missing binary
  ```
- Produces the adapter contract. Every `pdks/<name>/adapter.py` defines exactly these (document them in `pdks/README.md`; later tasks fill in the sky130 bodies):
  ```python
  DEFAULT_CELLS: list[str]                                   # sky130: ["inv", "nand2", "nor2", "a21oi"]
  def check_environment() -> None                            # raises AdapterError if PDK/tools missing
  def layout_name(cell: str) -> str                          # top cell name of the final GDS
  def write_astran_netlist(cell: str, out: Path) -> str      # returns the Astran cell name
  def write_lvs_netlist(cell: str, out: Path) -> None
  def astran_script(astran_cell: str, netlist: Path, gds_out: Path) -> str
  def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None
  def drc(gds: Path, top: str, workdir: Path) -> list[tuple[str, CheckResult]]   # [("magic", r), ("klayout", r)]
  def lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult
  def cell_size(gds: Path, top: str) -> tuple[float, float]  # CELLBOX width, height in µm
  def reference_size(cell: str) -> tuple[float, float]       # foundry cell width, height in µm
  def notes() -> list[str]                                   # lines printed under the table
  ```
- Produces `pdks/sky130/pdk.py`: `pdk_dir() -> Path` and layer constants `LAYERS: dict[str, tuple[int, int]]` with exactly the pairs listed in the spec ("sky130 layer/datatype pairs"). `pdk_dir()` tries, in order: `$ASTRAN_SKY130_DIR`; `${PDK_ROOT:-~/.ciel}/sky130A`; `${PDK_ROOT:-~/.ciel}/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130A`. If none exists it raises `AdapterError` listing all three paths.
- Naming: cell `inv` ↔ hd `sky130_fd_sc_hd__inv_1` ↔ Astran cell `INV_1` ↔ final top cell `astran_sky130__inv_1` (`layout_name`). Supply nets `VPWR`/`VGND`.
- Netlist source: `libs.ref/sky130_fd_sc_hd/cdl/sky130_fd_sc_hd.cdl` (M lines, microns, `+` continuations, `*.PININFO` comments).
- Astran netlist format (one cell per file):
  ```
  .subckt INV_1 A Y VPWR VGND
  M0 Y A VGND VGND NMOS L=0.15U W=0.65U
  M1 Y A VPWR VPWR PMOS L=0.15U W=1U
  .ends
  ```
  Bulk is rewritten to the supply (`VNB`→`VGND`, `VPB`→`VPWR`); `VNB`/`VPB` are dropped from the ports. Model map: `nfet_01v8`→`NMOS`, `pfet_01v8_hvt`→`PMOS`.
- LVS reference format: `.subckt astran_sky130__inv_1 A Y VPWR VGND`, devices as `X<n> d g s b sky130_fd_pr__nfet_01v8 w=0.65 l=0.15` (and `sky130_fd_pr__pfet_01v8_hvt`), bulk tied as above, port and net names upper-case to match Astran's labels.

- [ ] **Step 1: Write the failing tests** in `tests/test_netlist.py`

```python
from pdks.sky130 import netlist, pdk
from pdks.common import AdapterError

def test_inv_astran_netlist(tmp_path):
    name = netlist.write_astran_netlist("inv", tmp_path / "inv.sp")
    text = (tmp_path / "inv.sp").read_text().upper().split("\n")
    assert name == "INV_1"
    assert text[0].split() == [".SUBCKT", "INV_1", "A", "Y", "VPWR", "VGND"] or \
           sorted(text[0].split()[2:]) == ["A", "VGND", "VPWR", "Y"]
    m = [l.split() for l in text if l.startswith("M")]
    assert len(m) == 2
    assert {l[5] for l in m} == {"NMOS", "PMOS"}
    assert all("VNB" not in l and "VPB" not in l for l in m)
    n = next(l for l in m if l[5] == "NMOS")
    assert "L=0.15U" in n and "W=0.65U" in n and n[4] == "VGND"

def test_a21oi_has_six_devices(tmp_path):
    netlist.write_astran_netlist("a21oi", tmp_path / "x.sp")
    assert sum(l.upper().startswith("M") for l in (tmp_path / "x.sp").read_text().splitlines()) == 6

def test_lvs_reference_uses_pdk_devices(tmp_path):
    netlist.write_lvs_netlist("nand2", tmp_path / "ref.spice")
    t = (tmp_path / "ref.spice").read_text()
    assert ".subckt astran_sky130__nand2_1" in t
    assert t.count("sky130_fd_pr__nfet_01v8") == 2 and t.count("sky130_fd_pr__pfet_01v8_hvt") == 2
    assert "VNB" not in t and "VPB" not in t

# Review Focus 5
def test_multiplicity_is_expanded():
    cdl = """.SUBCKT sky130_fd_sc_hd__fake_1 A VGND VNB VPB VPWR Y
MMN0 Y A VGND VNB nfet_01v8 m=2 w=0.65 l=0.15 mult=1
+ sa=0.265
MMP0 Y A VPWR VPB pfet_01v8_hvt m=1 w=1.0 l=0.15 mult=1
.ENDS
"""
    devs = netlist.parse_cdl_subckt(cdl, "sky130_fd_sc_hd__fake_1").devices
    assert len(devs) == 3

def test_unknown_model_is_an_error():
    cdl = ".SUBCKT sky130_fd_sc_hd__fake_1 A VGND VNB VPB VPWR Y\nMM0 Y A VGND VNB nfet_g5v0d10v5 m=1 w=1 l=0.5\n.ENDS\n"
    with pytest.raises(AdapterError, match="nfet_g5v0d10v5"):
        netlist.parse_cdl_subckt(cdl, "sky130_fd_sc_hd__fake_1")

def test_unknown_cell_is_an_error(tmp_path):
    with pytest.raises(AdapterError, match="nosuchcell"):
        netlist.write_astran_netlist("nosuchcell", tmp_path / "x.sp")

# Review Focus 4
def test_pdk_not_found_lists_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("PDK_ROOT", str(tmp_path)); monkeypatch.delenv("ASTRAN_SKY130_DIR", raising=False)
    with pytest.raises(AdapterError) as e: pdk.pdk_dir()
    assert str(tmp_path) in str(e.value)
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_netlist.py -v`
Expected: import errors.

- [ ] **Step 3: Implement** `common.py`, `pdk.py`, `netlist.py` (public: `parse_cdl_subckt(text: str, name: str) -> Subckt` with `.ports: list[str]` and `.devices: list[Device]`, `write_astran_netlist`, `write_lvs_netlist`), and `adapter.py` with `DEFAULT_CELLS`, `layout_name`, the two netlist functions delegating, `check_environment` (PDK dir plus `shutil.which` for `magic`, `netgen`, `klayout`, `highs`), and the remaining functions raising `NotImplementedError`. Write `pdks/README.md`: the contract above, the naming rule, and the rule that the driver knows nothing PDK-specific.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_netlist.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pdks tests/test_netlist.py
git commit -m "Add PDK adapter contract and sky130 netlist conversion"
```

---

### Task 5: sky130 rule file and Astran script; first generated cell

**Files:**
- Create: `pdks/sky130/tech.rul`
- Modify: `pdks/sky130/adapter.py` (`astran_script`, `cell_size`)
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: `astran-cli` (Task 1), layer/datatype rule syntax and `MET1L` (Task 2), `write_astran_netlist` (Task 4).
- Produces: `astran_script(astran_cell, netlist, gds_out) -> str`, a complete `.run` text ending in `export layout <CELL> <gds_out>`; `cell_size(gds, top) -> (w, h)` from the bounding box of layer 235/4.
- Produces: fixture `generated_inv_raw(tmp_path_factory) -> Path` in `tests/conftest.py` (session-scoped): the raw Astran GDS of `inv`.

`tech.rul` header: `TECHNAME sky130A`, `MINSTEP 0.005`, `MLAYERS 3`, `SOI NO` if the reader needs it.

Layer map (name, CIF, GDSII, tech):

| Astran | CIF | GDSII | tech |
|---|---|---|---|
| CONT | CCG | 66/44 | licon1 |
| POLY | CPG | 66/20 | poly |
| NDIF | CAN | 65/20 | diff |
| PDIF | CAP | 65/20 | diff |
| NSEL | CSN | 93/44 | nsdm |
| PSEL | CSP | 94/20 | psdm |
| NWEL | CWN | 64/20 | nwell |
| VIA1 | CVA | 67/44 | mcon |
| VIA2 | CVS | 68/44 | via |
| MET1 | CMF | 67/20 | li1 |
| MET2 | CMS | 68/20 | met1 |
| MET3 | CMT | 69/20 | met2 |
| MET1P | CPF | 67/16 | li1 |
| MET2P | CPS | 68/16 | met1 |
| MET3P | CPT | 69/16 | met2 |
| MET1L | CLF | 67/5 | li1 |
| CELLBOX | CBX | 235/4 | prBoundary |

PWEL has no GDSII value (sky130 has no drawn pwell); the exporter skips it with a warning (Task 3).

Starting rule values in µm. Every value must be cross-checked against `libs.tech/magic/sky130A.tech` before use; where sky130 has several conditional rules, use the conservative one and say so in a `*` comment. Rules not listed start at 0, as in `tech_freePDK45.rul`. All 95 rule names must be present.

| Rule | Value | sky130 source |
|---|---|---|
| W2P1 | 0.15 | poly.1a |
| S1P1P1, S3P1P1 | 0.21 | poly.2 |
| S2P1P1 | 0.21, raise if a licon sits between gates | poly.2, licon.11 |
| S1DFP1, S2DFP1 | 0.075 | poly.4 |
| E1P1DF, E2P1DF | 0.13 | poly.8 |
| E1DFP1 | 0.25 | poly.7 |
| W2DF | 0.15 | difftap.1 |
| S1DFDF, S2DFDF | 0.27 | difftap.3 |
| W2CT | 0.17 | licon.1 |
| S1CTCT, S2CTCT, S3CTCT | 0.17 | licon.2 |
| E1DFCT | 0.04 | licon.5a |
| E2DFCT | 0.06 | licon.5c |
| E1P1CT | 0.05 | licon.8 |
| E2P1CT, E3P1CT | 0.08 | licon.8a |
| S1CTP1 | 0.055 | licon.11 |
| S1CTDF | 0.19 | licon.14 (poly licon to diff) |
| W1M1 | 0.17 | li.1 |
| S1M1M1, S2M1M1, S3M1M1 | 0.17 | li.3 |
| E1M1CT | 0 | li.5 |
| E2M1CT, E3M1CT | 0.08 | li.5 |
| A1M1 | 0.0561 | li.6 |
| W2VI | 0.17 | ct.1 (mcon) |
| S1VIVI | 0.19 | ct.2 |
| E1M1VI, E2M1VI | 0 | ct.4 |
| E1M2VI | 0.06 | m1.4/m1.5 conservative |
| W1M2 | 0.14 | m1.1 |
| S1M2M2, S2M2M2 | 0.14 (0.28 wide) | m1.2, m1.3a |
| W2V2 | 0.15 | via.1a |
| S1V2V2 | 0.17 | via.2 |
| E1M2V2 | 0.085 | via.5a conservative |
| E1M3V2 | 0.085 | m2.5 conservative |
| W1M3 | 0.14 | m2.1 |
| S1M3M3 | 0.14 | m2.2 |
| E1INDF, E1IPDF | 0.125 | nsd.5 / psd.5 |
| S1ININ, S1IPIP | 0.38 | nsd.2 / psd.2 |
| E1WNDP | 0.18 | difftap.8 |
| S1DNWN | 0.34 | difftap.9 |

Starting circuit settings in `astran_script` (tuned in Task 10): `set lpsolve "highs"`, `set vddnet VPWR`, `set gndnet VGND`, `set celltemplate "Taps w/ continuous diff"`, `set hgrid 0.46`, `set vgrid 0.34`, `set rowheight 10`, `set supplysize 0.48`, `set nwellborder 0.18`, `set pnselborder 0.125`, then `cellgen select`, `cellgen fold 2 0`, `cellgen place 150 3 3 4 1 4 2`, `cellgen route 1 0 1 1`, `cellgen compact 1 0 50 2 1 1 0 0 0 600`, `export layout`. Check each `set` command's parameter type in `Astran/src/designmng.h:171-184`.

- [ ] **Step 1: Write the failing tests** in `tests/test_generate.py`

```python
def test_inv_generates(generated_inv_raw):
    assert generated_inv_raw.stat().st_size > 0

def test_inv_uses_sky130_layers(generated_inv_raw):
    ly = load(generated_inv_raw)
    pairs = {(i.layer, i.datatype) for i in ly.layer_infos()}
    for need in [(66, 20), (65, 20), (66, 44), (67, 20), (64, 20), (93, 44), (94, 20), (235, 4), (67, 16), (67, 5)]:
        assert need in pairs, need

def test_inv_on_grid(generated_inv_raw):
    ly = load(generated_inv_raw); top = ly.top_cell()
    for li in ly.layer_indexes():
        for s in top.shapes(li).each():
            b = s.bbox()
            assert all(v % 5 == 0 for v in (b.left, b.bottom, b.right, b.top))   # dbu = 1 nm

def test_inv_has_two_gates_and_labels(generated_inv_raw):
    ly = load(generated_inv_raw); top = ly.top_cell()
    poly = kdb.Region(top.begin_shapes_rec(ly.layer(66, 20)))
    diff = kdb.Region(top.begin_shapes_rec(ly.layer(65, 20)))
    assert (poly & diff).merged().count() == 2
    texts = {s.text.string for s in top.shapes(ly.layer(67, 5)).each() if s.is_text()}
    assert {"A", "Y", "VPWR", "VGND"} <= texts

def test_cell_size_reads_cellbox(generated_inv_raw):
    w, h = adapter.cell_size(generated_inv_raw, "INV_1")
    assert 0.5 < w < 5 and 2 < h < 6
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_generate.py -v`
Expected: `NotImplementedError` from `astran_script`.

- [ ] **Step 3: Write `tech.rul`, `astran_script`, `cell_size`, the fixture.**

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_generate.py -v`
Expected: all pass. If supply pins are not labelled (the generator labels I/O geometries at `autocell2.cpp:828-835`), that is a generator matter: fix it generally so that rails carry a label for the vdd and gnd net names.

- [ ] **Step 5: Commit**

```bash
git add pdks/sky130/tech.rul pdks/sky130/adapter.py tests/test_generate.py tests/conftest.py
git commit -m "Add sky130 rule file and Astran script generation"
```

---

### Task 6: sky130 post-processing

**Files:**
- Create: `pdks/sky130/postprocess.py`
- Modify: `pdks/sky130/adapter.py` (`postprocess` delegates)
- Test: `tests/test_postprocess.py`

**Interfaces:**
- Consumes: `LAYERS` from `pdks/sky130/pdk.py`; raw GDS from Task 5.
- Produces: `postprocess(gds_in: Path, gds_out: Path, cell: str) -> None`. Output has a single top cell named `adapter.layout_name(cell)`.

What it does, using `klayout.db` regions (values to be cross-checked against `sky130A.tech`):

1. **tap:** diffusion not touching any gate (`diff` interacting with no `poly ∩ diff`) that is p+ outside nwell or n+ inside nwell moves from 65/20 to 65/44.
2. **npc:** licon overlapping poly and not diff, sized by 0.10, merged; gaps under 0.27 closed (size up then down); result on 95/20.
3. **hvtp:** PMOS gates (`poly ∩ diff ∩ nwell`) sized by 0.055, then extended to the full cell width across the PMOS row so abutting cells merge it; minimum width 0.38; on 78/44.
4. **implants:** nsdm and psdm merged; notches and gaps under 0.38 closed; each must still enclose its diff/tap by 0.125.
5. **cell edge:** nwell, hvtp, nsdm and psdm that reach within their own spacing of the CELLBOX left/right edge are extended to exactly that edge, so a neighbour's shape merges instead of leaving a sub-minimum gap. npc is kept at least 0.135 inside the left/right edges; if it cannot be, raise `AdapterError("npc too close to cell edge at x=…")`. This is a stop-and-report condition, not something to fix by moving contacts.
6. Rename the top cell; write with dbu 0.001.

- [ ] **Step 1: Write the failing tests.** Build inputs with `klayout.db` in the test file through a helper `make_gds(tmp_path, shapes: dict[tuple[int,int], list[tuple[float,float,float,float]]], cellbox) -> Path` (µm boxes, top cell `X_1`).

```python
def test_drawn_layers_untouched(generated_inv_raw, tmp_path):
    out = tmp_path / "o.gds"; postprocess(generated_inv_raw, out, "inv")
    a, b = load(generated_inv_raw), load(out)
    for pair in [(66, 20), (66, 44), (67, 20), (67, 44), (68, 20)]:
        assert region(a, pair) == region(b, pair)             # merged-region XOR is empty
    # diff may only move to tap, never change shape
    assert region(a, (65, 20)) == region(b, (65, 20)) + region(b, (65, 44))

def test_top_cell_renamed(...):       assert load(out).top_cell().name == "astran_sky130__inv_1"
def test_tap_reclassified(...):       # synthetic: p+ diff strip outside nwell with no poly -> on 65/44, absent from 65/20
def test_transistor_diff_stays_diff(...):   # synthetic: diff crossed by poly stays on 65/20
def test_npc_around_poly_contact(...):      # licon on poly at (1,1)-(1.17,1.17) -> npc bbox == (0.9,0.9)-(1.27,1.27)
def test_no_npc_for_diff_contact(...):      # licon on diff only -> 95/20 empty
def test_close_npc_shapes_merge(...):       # two poly licons 0.4 apart -> one npc polygon
def test_hvtp_over_pmos_only(...):          # hvtp covers the nwell gate by >= 0.055, does not touch the NMOS gate
def test_hvtp_spans_cell_width(...):        # hvtp bbox left == cellbox left, right == cellbox right
def test_implants_reach_cell_edge(...):     # nsdm drawn to 0.1 from the edge -> output touches the edge
def test_npc_near_edge_raises(...):         # poly licon 0.05 from the cell edge -> AdapterError matching "npc"
def test_output_on_grid(...):               # every vertex % 5 == 0
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_postprocess.py -v`
Expected: import error.

- [ ] **Step 3: Implement `postprocess.py`.**

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_postprocess.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pdks/sky130/postprocess.py pdks/sky130/adapter.py tests/test_postprocess.py
git commit -m "Add sky130 post-processing for derived layers"
```

---

### Task 7: DRC and LVS runners

Validated against the foundry's own cell, so this task does not depend on Astran's output being clean.

**Files:**
- Create: `pdks/sky130/checks.py`
- Modify: `pdks/sky130/adapter.py` (`drc`, `lvs`, `reference_size`, `notes`)
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `CheckResult`, `run_tool` (Task 4), `pdk_dir()`.
- Produces:
  ```python
  def magic_drc(gds: Path, top: str, workdir: Path) -> CheckResult
  def klayout_drc(gds: Path, top: str, workdir: Path) -> CheckResult
  def netgen_lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult
  KLAYOUT_SWITCHES = {"feol": "true", "beol": "true", "offgrid": "true", "seal": "false", "floating_met": "false"}
  ```
  `adapter.drc` returns `[("magic", …), ("klayout", …)]`; `adapter.notes()` returns the klayout switch line and the tap-area caveat from the spec ("Astran cells include well taps and hd cells do not, so the ratio is pessimistic for Astran by the tap area"); `adapter.reference_size(cell)` reads `SIZE w BY h` of `sky130_fd_sc_hd__<cell>_1` from `libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef`.
- magic DRC: `magic -dnull -noconsole -rcfile <pdk>/libs.tech/magic/sky130A.magicrc` with a generated Tcl script: `gds read`, `load <top>`, `select top cell`, `drc style drc(full)`, `drc check`, `drc catchup`, then write `drc listall why` and `drc count total` to `<workdir>/magic_drc.rpt`. `count` is the total; `ok` is `count == 0`.
- netgen LVS: magic `extract all`, `ext2spice lvs`, `ext2spice -o layout.spice`; then `netgen -batch lvs "layout.spice <top>" "<ref> <top>" <pdk>/libs.tech/netgen/sky130A_setup.tcl lvs.rpt`. `ok` only if the report contains `Circuits match uniquely.` and no property-error line.
- klayout DRC: `klayout -b -r <pdk>/libs.tech/klayout/drc/sky130A_mr.drc -rd input=… -rd topcell=… -rd report=… ` plus `KLAYOUT_SWITCHES` as `-rd`. Confirm the exact variable names at the top of the deck. `count` is the number of `<item>` elements in the report database.
- Failure rule (Review Focus 2): a tool exit code other than 0, a timeout, a missing or empty report, or a report that cannot be parsed gives `CheckResult(ok=False, count=-1, detail="<tool> did not complete: <reason>")`.

- [ ] **Step 1: Write the failing tests** in `tests/test_checks.py`. Fixture `hd_inv(tmp_path)` extracts `sky130_fd_sc_hd__inv_1` from `libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds` into its own file with klayout, and writes its subcircuit from `libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice` as the reference.

```python
def test_magic_drc_passes_foundry_inv(hd_inv, tmp_path):
    r = checks.magic_drc(hd_inv.gds, "sky130_fd_sc_hd__inv_1", tmp_path)
    assert r.ok and r.count == 0 and r.report.exists()

def test_klayout_drc_passes_foundry_inv(hd_inv, tmp_path):
    assert checks.klayout_drc(hd_inv.gds, "sky130_fd_sc_hd__inv_1", tmp_path).ok

def test_lvs_matches_foundry_inv(hd_inv, tmp_path):
    assert checks.netgen_lvs(hd_inv.gds, "sky130_fd_sc_hd__inv_1", hd_inv.spice, tmp_path).ok

def test_drc_catches_li_spacing(tmp_path):
    gds = make_gds(tmp_path, {(67, 20): [(0, 0, 0.17, 1.0), (0.22, 0, 0.39, 1.0)]}, cellbox=(0, 0, 1, 1))  # 0.05 gap < 0.17
    m = checks.magic_drc(gds, "X_1", tmp_path / "m"); k = checks.klayout_drc(gds, "X_1", tmp_path / "k")
    assert not m.ok and m.count > 0
    assert not k.ok and k.count > 0

def test_lvs_catches_wrong_width(hd_inv, tmp_path):
    bad = tmp_path / "bad.spice"
    bad.write_text(hd_inv.spice.read_text().replace("w=650000u", "w=900000u"))
    assert not checks.netgen_lvs(hd_inv.gds, "sky130_fd_sc_hd__inv_1", bad, tmp_path).ok

# Review Focus 2
def test_missing_tool_is_a_failure(monkeypatch, hd_inv, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))            # no magic, no klayout, no netgen
    for r in (checks.magic_drc(hd_inv.gds, "x", tmp_path), checks.klayout_drc(hd_inv.gds, "x", tmp_path),
              checks.netgen_lvs(hd_inv.gds, "x", hd_inv.spice, tmp_path)):
        assert not r.ok and r.count == -1 and "did not complete" in r.detail

def test_unreadable_gds_is_a_failure(tmp_path):
    g = tmp_path / "junk.gds"; g.write_bytes(b"not a gds")
    assert not checks.magic_drc(g, "x", tmp_path).ok
    assert not checks.klayout_drc(g, "x", tmp_path).ok

def test_reference_size():
    assert adapter.reference_size("inv") == (1.38, 2.72)
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_checks.py -v`
Expected: import error.

- [ ] **Step 3: Implement `checks.py` and the adapter functions.** If a foundry-cell test fails because of how the tool is invoked, fix the invocation; the foundry cell is the reference for a correct setup.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_checks.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pdks/sky130/checks.py pdks/sky130/adapter.py tests/test_checks.py
git commit -m "Add sky130 DRC and LVS runners validated on the foundry inverter"
```

---

### Task 8: Abutment arrays

**Files:**
- Modify: `pdks/common.py`
- Test: `tests/test_abutment.py`

**Interfaces:**
- Produces:
  ```python
  def build_abutment(cell_gds: Path, top: str, neighbours: list[tuple[Path, str]],
                     boundary: tuple[int, int], out: Path) -> str     # returns the array's top cell name
  ```
  `boundary` is the layer/datatype of the cell box (passed in by the driver from the adapter, see Task 9: adapters expose `BOUNDARY_LAYER: tuple[int, int]`, sky130 `(235, 4)`; add it to `pdks/README.md` and `pdks/sky130/adapter.py`). The array's top cell is `<top>__abut`. It contains cell instances only, placed by their boundary boxes with no gap:
  - row 0: `cell`, `cell` mirrored in x, `cell`, then each neighbour once, each followed by `cell` again;
  - row 1: the same sequence flipped vertically and stacked on row 0 so the top rails coincide;
  - row 2: row 0 again, flipped so its bottom rail coincides with row 1's bottom rail.
  Cells of different height raise `AdapterError`.

- [ ] **Step 1: Write the failing tests** with synthetic cells from `make_gds` (cell A 1.0 × 3.0, cell B 2.0 × 3.0, each with one off-centre marker shape so orientation is observable).

```python
def test_self_abutment_counts(tmp_path):
    name = build_abutment(a, "A", [], (235, 4), tmp_path / "arr.gds")
    ly = load(tmp_path / "arr.gds"); top = ly.cell(name)
    assert name == "A__abut"
    assert top.child_instances() == 9                       # 3 per row, 3 rows
    assert top.bbox().width() == 3000 and top.bbox().height() == 9000

def test_no_gaps_or_overlaps_between_boundaries(tmp_path):   # merged boundary region is one rectangle; sum of areas == bbox area
def test_mirrored_and_flipped_instances_present(tmp_path):   # at least one instance with trans.is_mirror(); marker positions prove x-mirror and y-flip both occur
def test_neighbours_are_included(tmp_path):                  # with [(b, "B")]: row has 5 instances, bbox width == 1+1+1+2+1 µm
def test_different_heights_raise(tmp_path):                  # AdapterError
def test_original_cell_geometry_is_unchanged(tmp_path):      # region of cell "A" inside arr.gds equals the input
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_abutment.py -v`
Expected: `build_abutment` not defined.

- [ ] **Step 3: Implement `build_abutment`.**

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_abutment.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pdks/common.py pdks/README.md pdks/sky130/adapter.py tests/test_abutment.py
git commit -m "Add abutment array builder"
```

---

### Task 9: Driver

**Files:**
- Create: `astran_pdk.py`
- Test: `tests/test_driver.py`, `tests/fakepdk/adapter.py`

**Interfaces:**
- Consumes: the adapter contract (Tasks 4, 7, 8), `astran-cli`.
- Produces: `python3 astran_pdk.py <pdk> [cell ...] [--out DIR] [--astran PATH]`. No cells means `DEFAULT_CELLS`. `--out` defaults to `out/<pdk>`; `--astran` defaults to `Astran/build/bin/astran-cli`. Importable entry `main(argv: list[str]) -> int`.
- Per cell, in `out/<pdk>/<cell>/`: `astran.sp`, `ref.spice`, `cell.run`, `astran.log`, `raw.gds`, `final.gds`, `abut.gds`, and one subdirectory per check. Stages: netlists → script → `astran-cli` → `postprocess` → `drc(final)` → `lvs(final)` → sizes. After all cells have a `final.gds`, each one's `abut.gds` is built with every other successfully generated cell as neighbour and run through `drc`.
- Table columns, in this order: `cell`, `gen`, `drc`, `drc-abut`, `lvs`, `w×h`, `ref w×h`, `area`, `ref area`, `ratio`. `drc` and `drc-abut` show `pass` only if every checker returned `ok`; otherwise `FAIL(<checker>:<count>)`. A stage that could not run because an earlier one failed shows `-`. A failed stage shows `FAIL` and the row's reason is printed under the table as `<cell>: <stage>: <message>`. Then the adapter's `notes()` lines.
- Exit status: 0 if every cell passed gen, drc, drc-abut and lvs; 1 if any cell failed; 2 if `check_environment()` raised, the PDK name has no adapter, or `astran-cli` is missing (message on stderr, nothing processed).
- An exception from one cell's stage (`AdapterError` or anything else) fails that cell only.

- [ ] **Step 1: Write the failing tests.** `tests/fakepdk/adapter.py` implements the contract in memory: `DEFAULT_CELLS = ["good", "nodrc", "nogds", "missing"]`; `write_astran_netlist("missing", …)` raises `AdapterError("cell missing not in library")`; `astran_script` returns a script the fake `astran-cli` understands; `drc` fails for `nodrc`; sizes are fixed (`cell_size` 2.0×3.0, `reference_size` 1.0×3.0). A fake `astran-cli` shell script (created in a fixture) writes an empty-but-valid GDS unless the script contains `nogds`, in which case it exits 1. The driver takes the adapter module from `pdks.<name>.adapter`; the test puts `fakepdk` on that path with `monkeypatch`.

```python
def test_all_pass_exit_0(fake_env, capsys):
    assert main(["fakepdk", "good", "--out", str(fake_env.out), "--astran", str(fake_env.cli)]) == 0
    out = capsys.readouterr().out
    row = next(l for l in out.splitlines() if l.startswith("good"))
    assert row.split()[1:5] == ["ok", "pass", "pass", "pass"]
    assert "6.000" in row and "3.000" in row and "2.00" in row        # area, ref area, ratio

def test_header_columns(fake_env, capsys):
    main([...]); header = capsys.readouterr().out.splitlines()[0].split()
    assert header[:5] == ["cell", "gen", "drc", "drc-abut", "lvs"]

# Review Focus 3
def test_failures_are_isolated_and_reported(fake_env, capsys):
    rc = main(["fakepdk", "--out", str(fake_env.out), "--astran", str(fake_env.cli)])
    out = capsys.readouterr().out
    assert rc == 1
    assert row(out, "good").split()[1:5] == ["ok", "pass", "pass", "pass"]
    assert row(out, "nodrc").split()[2].startswith("FAIL(")
    assert row(out, "nogds").split()[1:5] == ["FAIL", "-", "-", "-"]
    assert row(out, "missing").split()[1] == "FAIL"
    assert "missing: gen: cell missing not in library" in out
    assert "nogds: gen:" in out

def test_failed_cells_are_not_abutment_neighbours(fake_env):   # fake adapter records neighbour lists; "nogds" never appears

# Review Focus 4
def test_environment_error_exits_2_before_any_cell(fake_env, capsys, monkeypatch):
    monkeypatch.setattr(fakepdk_adapter, "check_environment", lambda: (_ for _ in ()).throw(AdapterError("PDK not found: tried /a, /b")))
    assert main(["fakepdk", "good", "--out", str(fake_env.out), "--astran", str(fake_env.cli)]) == 2
    assert "PDK not found: tried /a, /b" in capsys.readouterr().err
    assert not (fake_env.out / "good").exists()

def test_unknown_pdk_exits_2(capsys):          assert main(["nosuchpdk"]) == 2
def test_missing_astran_cli_exits_2(fake_env): assert main(["fakepdk", "good", "--astran", "/nonexistent"]) == 2
def test_notes_printed(fake_env, capsys):      # adapter.notes() lines appear after the table
def test_driver_has_no_pdk_knowledge(repo_root):
    src = (repo_root / "astran_pdk.py").read_text().lower()
    assert all(w not in src for w in ["sky130", "li1", "magic", "netgen", "235"])
```

- [ ] **Step 2: Run to see them fail**

Run: `pytest tests/test_driver.py -v`
Expected: `astran_pdk` not importable.

- [ ] **Step 3: Implement `astran_pdk.py`.**

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_driver.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add astran_pdk.py tests/test_driver.py tests/fakepdk
git commit -m "Add PDK-neutral driver with result table"
```

---

### Task 10: Make the four cells clean

This task is a loop, not a single test cycle. It ends when the acceptance test passes or a stop-and-report condition is hit.

**Files:**
- Create: `tests/test_acceptance.py`
- Modify (as findings require): `pdks/sky130/tech.rul`, `pdks/sky130/adapter.py` (circuit settings), `pdks/sky130/postprocess.py` (derived layers only), `Astran/src/autocell2.cpp`, `Astran/src/compaction.cpp`, `Astran/src/rules.h` (generic rule slots only)

**Interfaces:**
- Consumes: everything above.
- Produces: `python3 astran_pdk.py sky130` exits 0.

- [ ] **Step 1: Write the acceptance test**

```python
@pytest.mark.slow
def test_four_cells_clean(repo_root, tmp_path, capsys):
    rc = astran_pdk.main(["sky130", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    for cell in ["inv", "nand2", "nor2", "a21oi"]:
        assert row(out, cell).split()[1:5] == ["ok", "pass", "pass", "pass"], out
    assert rc == 0

@pytest.mark.slow
def test_no_pdk_names_in_generator(repo_root):
    hits = subprocess.run(["grep", "-rniE", r"sky130|\bnpc\b|hvtp|licon|\bli1\b|mcon", str(repo_root / "Astran/src")],
                          capture_output=True, text=True).stdout
    assert hits == ""
```

Register the `slow` marker in a `pytest.ini` at the repo root.

- [ ] **Step 2: Run it and read the reports**

Run: `python3 astran_pdk.py sky130 inv; cat out/sky130/inv/*/magic_drc.rpt`
Expected at first: failures. Start with `inv` alone; add cells one at a time in the order inv, nand2, nor2, a21oi.

- [ ] **Step 3: Fix one violation class at a time, in this order of preference.** Use the systematic-debugging skill for each class.

  1. A wrong or missing value in `tech.rul` or a circuit setting: correct it, with a `*` comment naming the sky130 rule.
  2. A derived-layer problem (npc, hvtp, tap, implants, cell edge): fix `postprocess.py`, with a new test in `tests/test_postprocess.py` first.
  3. A drawn-geometry violation Astran can express but gets wrong, or a general rule it lacks (same-net spacing from `Astran/build/ISSUES.txt`; minimum li1 area via `A1M1`; pins or rails unlabelled): fix the generator generally, with a C++ or pytest test first. A new slot in `rule_name` must be a generic concept with a generic name, added to all three existing rule files' semantics as default 0.
  4. LVS mismatch: check the reference netlist and labels before touching layout. Parallel-device merging for folded transistors is normal netgen behaviour; anything that changes netgen's setup file is not allowed.

  After each fix rerun the whole fast suite: `make -C Astran -f cli.mk test && pytest -m "not slow" -q`.

- [ ] **Step 4: Stop-and-report conditions.** Stop and write up cell, rule, what was tried and the options, without working around it, if: a derived layer cannot be made legal by conservative rule values or edge handling (`AdapterError` from post-processing counts); a fix would need a sky130 name or branch in `Astran/src`; a check can only pass by switching off or editing a rule; or the solver cannot find a feasible layout for a cell after the row height and grids have been loosened.

- [ ] **Step 5: Tune for area only after all four are clean.** Reduce `rowheight`, grids and conservative rule values one at a time, keeping the acceptance test green. Stop when a reduction breaks a check.

- [ ] **Step 6: Run everything**

Run: `make -C Astran -f cli.mk test && pytest -q`
Expected: all pass, including `slow`.

- [ ] **Step 7: Commit** (commit after each fixed violation class as well, with a message naming the rule)

```bash
git add -A pdks Astran/src Astran/tests tests pytest.ini
git commit -m "Make sky130 inv, nand2, nor2 and a21oi DRC/LVS clean"
```

---

### Task 11: Documentation and final verification

**Files:**
- Modify: `README.md`, `pdks/README.md`
- Create: `pdks/sky130/README.md`

**Interfaces:**
- Consumes: the finished flow.

- [ ] **Step 1: Write the docs.** `README.md` gets a short "Open PDKs" section: `nix develop`, `make -C Astran -f cli.mk`, `python3 astran_pdk.py sky130`, and a pasted copy of the real table from Task 10. `pdks/sky130/README.md` records: the Astran-to-sky130 layer mapping; that rails are li1 and cells carry taps (not drop-in with hd); which rule values are conservative and why; the klayout switches; the tap-area caveat on the ratio. `pdks/README.md` gains a "Adding a PDK" checklist built from the contract.

- [ ] **Step 2: Verify from a clean checkout**

Commit or confirm the working tree is clean first (`git status --short` prints nothing), then:

Run: `git clone . "$SCRATCH/astran-verify" && cd "$SCRATCH/astran-verify" && nix develop -c sh -c 'make -C Astran -f cli.mk test && pytest -q && python3 astran_pdk.py sky130'; echo exit=$?`
Expected: tests pass; table shows `ok pass pass pass` for all four cells; `exit=0`. `$SCRATCH` is a scratch directory of your own; delete the clone afterwards.

- [ ] **Step 3: Verify the legacy rule files still work**

Run: `pytest tests/test_cli.py tests/test_gds_export.py -v`
Expected: all pass (these use `tech_0065.rul` and bare-number layer maps).

- [ ] **Step 4: Commit**

```bash
git add README.md pdks/README.md pdks/sky130/README.md
git commit -m "Document the sky130 adapter and how to add a PDK"
```
