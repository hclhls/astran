# gf180mcu PDK adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python3 astran_pdk.py gf180` generates INV, NAND2, NOR2 and AOI21 in gf180mcuD from the 7t library's netlists and reports DRC (alone and abutted), LVS and area against `gf180mcu_fd_sc_mcu7t5v0`.

**Architecture:** A new `pdks/gf180/` adapter implements the existing contract in `pdks/README.md`; the driver, `pdks/common.py` and `Astran/src` stay technology-neutral. gf180 has no local interconnect, so Astran's CONT/MET1/VIA1/MET2/VIA2/MET3 map to contact/metal1/via1/metal2/via2/metal3. The one known core risk (different N and P gate lengths) is probed first.

**Tech Stack:** Python 3 + klayout.db, magic, netgen, klayout DRC, Astran C++ (`astran-cli`), pytest, the nix dev shell (`nix develop`).

**Spec:** `docs/superpowers/specs/2026-11-13-gf180-pdk-adapter-design.md`

## Global Constraints

- All gf180 content lives in `pdks/gf180/` and its tests; no gf180 names, layer numbers or rule values in `Astran/src/` or `pdks/common.py` or `astran_pdk.py`. Any core change is technology-neutral, tested in `tests/` or `Astran/tests/`, and listed in the final report.
- Checks: magic `drc(full)`, klayout DRC (`main.drc`), magic extraction + netgen LVS with `gf180mcuD_setup.tcl`. A crash, timeout or missing report is a failure (`ok=False, count=-1`), never "0 errors".
- Never weaken a check to pass: every klayout switch turned off is recorded with a reason in `pdks/gf180/README.md`; sky130 baseline is `seal=false`, `floating_met=false`.
- Cells must draw dualgate (55/0), as the reference cells do; the LVS reference merges `VNW`→`VDD`, `VPW`→`VSS`.
- Reference size is the prBoundary (layer 0/0): inv_1 2.24×3.92, nand2_1 2.80×3.92, nor2_1 3.36×3.92, aoi21_1 4.48×3.92 µm. Area ratio is reported, never gated.
- PDK path: `ASTRAN_GF180_DIR`, then `$PDK_ROOT/ciel/gf180mcu/versions/0fe599b2afb6708d281543108caf8310912f54af/gf180mcuD`, then `~/.ciel/...` same suffix. Missing PDK → `AdapterError` naming every path tried and the fetch command `ciel enable --pdk-family gf180mcu 0fe599b2afb6708d281543108caf8310912f54af`.
- Deterministic output; the sky130 table and the whole existing suite must stay green.
- Work on branch `gf180-pdk-adapter`; do not push or merge without being asked.
- If DRC-clean cells need a core change that is not neutral, stop and report with evidence.

## Review Focus

1. Lone cell vs abutted: the reference wells extend 0.43 µm past the cell box; two cells side by side must not create well spacing/merge violations (pinned in Task 6).
2. Missing PDK or tool: clear `AdapterError`, exit 2, no traceback (Task 2, Task 3).
3. A checker that crashes or times out is a failure, not "0" (Task 4).
4. N and P gate lengths differ (0.6 / 0.5 µm): the drawn poly must match each, and LVS must see the same W/L as the reference (Tasks 1 and 7).
5. Cells whose netlist has body pins distinct from supplies: the LVS reference must not change a device's body connection other than merging into the supplies (Task 2).

## File Structure

- `pdks/gf180/__init__.py` — empty.
- `pdks/gf180/pdk.py` — PDK location, `LAYERS` (layer/datatype pairs).
- `pdks/gf180/netlist.py` — 7t SPICE → Astran netlist + LVS reference; cell naming.
- `pdks/gf180/tech.rul` — Astran rule file (hand-written, commented with gf180 rule names).
- `pdks/gf180/adapter.py` — the contract; Astran script; sizes; notes.
- `pdks/gf180/postprocess.py` — derived layers with klayout.db.
- `pdks/gf180/checks.py` — magic DRC, klayout DRC, netgen LVS.
- `pdks/gf180/README.md` — mapping and judgement calls.
- `tests/test_gate_length.py`, `tests/test_gf180_netlist.py`, `tests/test_gf180_generate.py`, `tests/test_gf180_checks.py`, `tests/test_gf180_postprocess.py`, `tests/test_gf180_driver.py`, `tests/test_gf180_acceptance.py`; fixtures in `tests/conftest.py`.
- Modify: `pdks/README.md` (corrections found), `README.md` (second table), `tests/test_acceptance.py` (`test_no_pdk_names_in_generator` also forbids gf180 names).

---

### Task 1: Gate-length probe (can end the project)

**Files:**
- Create: `tests/test_gate_length.py`
- Modify (only if the probe fails): `Astran/src/autocell2.cpp` near line 994 and whatever else it needs; neutral only.

**Interfaces:**
- Consumes: the `astran_cli` fixture and `tests/data/mini.rul` (exist; see `tests/test_generate.py` for how a netlist is run through `astran-cli` and the GDS read back with klayout).
- Produces: a documented fact (in the ledger and later `pdks/gf180/README.md`): whether the drawn poly width over diffusion follows each transistor's own L, and for which units.

- [ ] **Step 1: Write the failing test** `test_poly_width_follows_each_transistors_length`: a one-inverter netlist with NMOS `L=0.6U` and PMOS `L=0.5U` (use the same netlist syntax the sky130 adapter writes), run through `astran-cli` with `mini.rul`, read the GDS, and assert that the poly width across the NMOS diffusion is 600 nm and across the PMOS diffusion 500 nm (poly ∩ each diffusion's bbox width). Use whatever layer numbers `mini.rul` assigns; read them from the file.
- [ ] **Step 2: Run** `pytest tests/test_gate_length.py -v`. Expected: FAIL on the assertion with the measured widths printed (both equal, or neither equal the L values) — or PASS, which means the core already honours L; then the test stays as a regression test and Step 3 is skipped.
- [ ] **Step 3: If it failed, make the generator draw poly width = transistor length** (`Astran/src/autocell2.cpp`, where `transLength` is computed). Neutral change only; keep sky130 output identical (`tests/test_acceptance.py` result table unchanged).
- [ ] **Step 4: Run** `pytest tests/test_gate_length.py -v` then the full existing suite (`pytest -q`, plus the C++ tests the sky130 plan used). Expected: all pass. If the probe cannot be made to pass without a non-neutral change, **stop and report with the measured widths**; do not continue to Task 2.
- [ ] **Step 5: Commit** `git commit -m "Test that poly width follows each transistor's length"` (add the core change in the same commit if one was needed).

---

### Task 2: gf180 PDK lookup, layers and netlist conversion

**Files:**
- Create: `pdks/gf180/__init__.py`, `pdks/gf180/pdk.py`, `pdks/gf180/netlist.py`, `tests/test_gf180_netlist.py`
- Modify: `tests/conftest.py` (add `gf180_pdk` fixture: skips when `pdk.pdk_dir()` raises)

**Interfaces:**
- Produces in `pdks/gf180/pdk.py`: `PINNED_VERSION: str`; `LAYERS: dict[str, tuple[int,int]]` with at least `nwell (21,0)`, `pwell (204,0)`, `comp (22,0)`, `poly (30,0)`, `contact (33,0)`, `metal1 (34,0)`, `metal1_label (34,10)`, `via1 (35,0)`, `metal2 (36,0)`, `via2 (38,0)`, `metal3 (42,0)`, `nplus (32,0)`, `pplus (31,0)`, `dualgate (55,0)`, `prBoundary (0,0)` (confirm each against `gf180mcuD-GDS.tech` / `gf180mcu.map`; fix this list if one is wrong); `pdk_dir() -> Path` (raises `AdapterError`, message per Global Constraints).
- Produces in `pdks/gf180/netlist.py`: `PREFIX = "gf180mcu_fd_sc_mcu7t5v0__"`; `ref_name(cell) -> str` (`"inv"` → `...__inv_1`; `"aoi21"` → `...__aoi21_1`); `astran_name(cell) -> str`; `layout_name(cell) -> str`; `parse_spice_subckt(text: str, name: str) -> Subckt`; `write_astran_netlist(cell, out: Path) -> str`; `write_lvs_netlist(cell, out: Path) -> None`. `Device`/`Subckt` mirror `pdks/sky130/netlist.py`.

- [ ] **Step 1: Write failing tests** in `tests/test_gf180_netlist.py`: `test_pdk_dir_missing_names_every_path_and_fetch_command` (set `ASTRAN_GF180_DIR` and `PDK_ROOT` to nonexistent dirs; `AdapterError` message contains both paths and `ciel enable --pdk-family gf180mcu`); `test_parse_nand2_devices` (uses `gf180_pdk`; 4 devices; N `nfet_06v0` W=0.82 L=0.6, P `pfet_06v0` W=1.13 L=0.5); `test_astran_netlist_maps_models_and_supplies` (NMOS/PMOS, `VDD`/`VSS` as supply nets, no `VNW`/`VPW` pins); `test_lvs_reference_merges_bodies_into_supplies` (every device body is `VDD`/`VSS`; device model names are the gf180 ones `nfet_06v0`/`pfet_06v0`, W/L unchanged from the reference); `test_unknown_cell_raises_adapter_error`.
- [ ] **Step 2: Run** `pytest tests/test_gf180_netlist.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement** `pdk.py` and `netlist.py`. Parse `libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice` (format: `X_i_1 d g s b model W= L=`, upper-case `.SUBCKT`). Copy `_num`/`_logical_lines` from sky130's `netlist.py`; if they end up identical, move them to `pdks/common.py` and import from both, keeping sky130 tests green.
- [ ] **Step 4: Run** the same tests. Expected: PASS. Run `pytest tests/test_netlist.py -q` (sky130) to confirm unchanged.
- [ ] **Step 5: Commit** `git commit -m "Add gf180 PDK lookup and netlist conversion"`.

---

### Task 3: Rule file, Astran script and the first generated cell

**Files:**
- Create: `pdks/gf180/tech.rul`, `pdks/gf180/adapter.py`, `tests/test_gf180_generate.py`

**Interfaces:**
- Consumes: Task 2 (`netlist.*`, `pdk.*`), `pdks.common.run_tool`, the `astran_cli` fixture, the sky130 `adapter.py` as the template.
- Produces in `adapter.py`: all contract names from `pdks/README.md` for gf180; `DEFAULT_CELLS = ["inv", "nand2", "nor2", "aoi21"]`; `BOUNDARY_LAYER = pdk.LAYERS["prBoundary"]`; `SETTINGS: list[str]` (`set vddnet VDD`, `set gndnet VSS`, grid and row height to be chosen); `astran_script(...)` returning a full `.run` text ending in `export layout`; `cell_size`, `reference_size` (reads the 7t GDS prBoundary), `notes()`. `postprocess`, `drc`, `lvs` may delegate to modules created in later tasks; until then they raise `NotImplementedError` and the tests for them are written in those tasks.

- [ ] **Step 1: Write failing tests**: `test_check_environment_reports_missing_tools` (empty `PATH` → `AdapterError` listing `magic`, `netgen`, `klayout`, `highs`); `test_reference_sizes` (`reference_size` for the four cells equals 2.24, 2.80, 3.36, 4.48 × 3.92); `test_astran_script_is_complete` (contains `load technology`, `cellgen compact`, ends with `export layout`); `test_inv_generates_raw_gds` (runs `astran-cli` on the inv script; exit 0; GDS contains contact, poly, comp and metal1 shapes).
- [ ] **Step 2: Run** `pytest tests/test_gf180_generate.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Write `tech.rul`** by hand from `libs.tech/magic/gf180mcuD.tech` and the klayout decks in `libs.tech/klayout/drc/rule_decks` (poly2, comp, contact, metal1, via1, metal2, nplus, pplus, nwell). Same header style and `*` comments naming the gf180 rule as sky130's file does; conservative value where a rule is conditional; the GDS column uses `<layer>/<datatype>` from `LAYERS`. Grid: choose `hgrid`/`vgrid` so one row is close to 3.92 µm tall when `rowheight` rows are used (e.g. 0.28 µm × 14 rows = 3.92); record the choice.
- [ ] **Step 4: Implement** `adapter.py` as above. Starting script lines as for sky130 (`fold`, `place`, `route`, `compact`); templates `"Taps w/ continuous diff"` only if Task 6 finds taps are needed — start with the tap-free one Astran offers.
- [ ] **Step 5: Run** the tests. Expected: PASS. Run `pytest -q` — sky130 unchanged.
- [ ] **Step 6: Commit** `git commit -m "Add gf180 rule file and Astran script; generate inv"`.

---

### Task 4: DRC and LVS runners, tested on the foundry's own cells

**Files:**
- Create: `pdks/gf180/checks.py`, `tests/test_gf180_checks.py`

**Interfaces:**
- Consumes: `pdks.common.run_tool`, `CheckResult`; sky130 `checks.py` as the model.
- Produces: `magic_drc(gds, top, workdir) -> CheckResult`, `klayout_drc(gds, top, workdir) -> CheckResult`, `netgen_lvs(gds, top, ref, workdir) -> CheckResult`, `KLAYOUT_SWITCHES: dict[str,str]`. magic needs `$PDK_ROOT/gf180mcuD` (symlink in the workdir, as sky130 does) and `gf180mcuD.magicrc`. klayout runs `libs.tech/klayout/drc/rule_decks/main.drc` with `-rd input=… -rd topcell=… -rd report=… -rd metal_level=<stack> -rd metal_top=<thickness>` and the on/off switches; confirm the variable names in `main.drc` (`$input`, `$topcell`, `$report`, `$metal_level`, `$metal_top`, `$feol`, `$beol`, `$offgrid`, `$conn_drc`, …). The stack is the one librelane uses for gf180mcuD by default.
- Netgen setup: `libs.tech/netgen/gf180mcuD_setup.tcl`.

- [ ] **Step 1: Write failing tests**: `test_foundry_inv_passes_magic_drc_klayout_drc_and_lvs` (extract `inv_1` from the 7t GDS and its SPICE as the reference, run all three; all pass — if a foundry cell fails a check on its own, record why and handle it as the sky130 plan did, not by hiding it); `test_violation_is_reported` (add a sliver of metal1 to the foundry cell → both DRC checkers report count > 0); `test_lvs_detects_wrong_circuit` (use nand2's netlist as the reference for inv → `ok=False`); `test_crashing_tool_is_a_failure` (put a fake `magic`/`klayout`/`netgen` on `PATH` that exits 1 or writes nothing → `ok=False, count=-1` for each); `test_timeout_is_a_failure` (fake tool sleeps; patch the timeout small).
- [ ] **Step 2: Run** `pytest tests/test_gf180_checks.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `checks.py` following the sky130 module: magic `drc style drc(full)` count parsed between markers; klayout report parsed from `.lyrdb` with unusable report → failure; netgen "Circuits match uniquely." gate; property errors fail. Record every klayout switch turned off with its reason in a comment next to `KLAYOUT_SWITCHES`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Add gf180 DRC and LVS runners, validated on foundry cells"`.

---

### Task 5: Post-processing (derived layers)

**Files:**
- Create: `pdks/gf180/postprocess.py`, `tests/test_gf180_postprocess.py`
- Modify: `pdks/gf180/adapter.py` (`postprocess` delegates)

**Interfaces:**
- Produces: `postprocess(gds_in: Path, gds_out: Path, cell: str) -> None` in `pdks/gf180/postprocess.py`. Output top cell is `layout_name(cell)`; contains prBoundary 0/0 equal to the Astran cell box; dualgate over every transistor channel region; nplus/pplus over the matching diffusion; pwell as required by the decks; wells and implants extended to the cell edges as the rules require. Never moves or resizes poly, diffusion, contacts or metal.

- [ ] **Step 1: Write failing tests**: `test_boundary_matches_cell_box`; `test_dualgate_covers_every_gate_and_nothing_else` (dualgate ∩ poly ∩ comp area equals poly ∩ comp area; no dualgate outside diffusion enclosure margin); `test_geometry_of_poly_diffusion_contact_metal_unchanged` (the Astran layers are identical before and after); `test_postprocess_is_deterministic`; `test_implant_types_match_diffusion_types`.
- [ ] **Step 2: Run** `pytest tests/test_gf180_postprocess.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with klayout.db regions. Constants for enclosures and spacings come from the gf180 rules (name the rule in a comment next to each, as `pdks/sky130/postprocess.py` does). Look at the foundry inv_1 for the intended nplus/pplus/dualgate/well structure before writing it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Add gf180 post-processing"`.

---

### Task 6: Abutment and the driver for gf180

**Files:**
- Create: `tests/test_gf180_driver.py`
- Modify: `pdks/gf180/adapter.py` (`drc`, `lvs` wired to `checks`); nothing in `astran_pdk.py` unless a neutral bug is found

**Interfaces:**
- Consumes: `pdks.common.build_abutment(cell_gds, top, neighbours, BOUNDARY_LAYER, out)`, `checks.*`.
- Produces: `adapter.drc(gds, top, workdir) -> list[tuple[str, CheckResult]]` (magic, klayout) and `adapter.lvs(...)`.

- [ ] **Step 1: Write failing tests**: `test_driver_runs_gf180_inv_and_prints_table_row` (`astran_pdk.main(["gf180","inv", …])` prints a row with the 10 columns, exit code 0 or 1 but never a traceback); `test_missing_pdk_exits_2_with_fetch_hint` (env var to nowhere → exit 2, output contains the fetch command); `test_abutment_catches_edge_violation` (a lone cell built from the foundry `inv_1` GDS passes; a copy whose well is cut short so two abutted cells violate spacing fails only in the abutted run, not alone).
- [ ] **Step 2: Run** `pytest tests/test_gf180_driver.py -v`. Expected: FAIL.
- [ ] **Step 3: Wire** `drc` and `lvs` in the adapter; fix any hard-coded sky130 assumption in the driver or `common.py` neutrally (list it for the final report).
- [ ] **Step 4: Run** the tests, then `pytest -q`. Expected: PASS for the new tests; the suite is green.
- [ ] **Step 5: Commit** `git commit -m "Run gf180 through the driver, alone and abutted"`.

---

### Task 7: Make the four cells clean

**Files:**
- Modify: `pdks/gf180/tech.rul`, `pdks/gf180/adapter.py` (`SETTINGS`, script values), `pdks/gf180/postprocess.py`; core only if neutral and tested
- Create: `tests/test_gf180_acceptance.py`
- Modify: `tests/test_acceptance.py` (`test_no_pdk_names_in_generator` also forbids `gf180` and `dualgate` in `Astran/src`)

**Interfaces:**
- Produces: `astran_pdk.py gf180` printing `ok pass pass pass` for inv, nand2, nor2, aoi21 with exit 0.

- [ ] **Step 1: Write failing tests** (all `@pytest.mark.slow`): `test_four_cells_clean` (as sky130's: each row's columns 2–5 are `ok pass pass pass`, exit 0); `test_flow_is_deterministic` (two runs give equal sizes); `test_poly_lengths_match_reference_netlist` (drawn N/P gate lengths in the final GDS equal the reference's 0.6 and 0.5 µm).
- [ ] **Step 2: Run** `pytest tests/test_gf180_acceptance.py -v -m slow`. Expected: FAIL with the current DRC/LVS counts printed.
- [ ] **Step 3: Iterate**: read each report, fix at the right layer (rule value in `tech.rul`, derived layer in `postprocess.py`, script values, or a neutral core change as `E3DFCT` was for sky130). One fix per cause; rerun after each. Decide taps here: if a lone cell fails only tap/latchup-type rules, switch to the "Taps w/ continuous diff" template and record the area effect. Stop and report instead of working around a rule if the only way through is non-neutral.
- [ ] **Step 4: Run** `pytest tests/test_gf180_acceptance.py -m slow -v`, then the full suite (`pytest -q`, C++ tests, and the sky130 acceptance). Expected: all pass; sky130 table identical to the README's.
- [ ] **Step 5: Commit** `git commit -m "Make gf180 inv, nand2, nor2 and aoi21 DRC/LVS clean"`.

---

### Task 8: Documentation and final verification

**Files:**
- Create: `pdks/gf180/README.md`
- Modify: `pdks/README.md` (correct "Adding a PDK" wherever gf180 contradicted it), `README.md` (add the gf180 table under "Open PDKs")

**Interfaces:** none produced; consumes the Task 7 table.

- [ ] **Step 1: Write the failing test** `test_klayout_switches_are_documented` in `tests/test_gf180_acceptance.py`: every key in `KLAYOUT_SWITCHES` whose value is `false` appears in `pdks/gf180/README.md` with a reason line; and `test_readme_lists_every_adapter_name` (the README's layer table mentions every layer in `pdk.LAYERS`).
- [ ] **Step 2: Run** them. Expected: FAIL (no README).
- [ ] **Step 3: Write** `pdks/gf180/README.md` (layer mapping, differences from the 7t reference, rule-value judgement calls with their gf180 rule names, post-processing, switches off and why, the gate-length finding, the table with the area ratios) and the corrections to `pdks/README.md` and `README.md`. End with the list "Changed outside `pdks/gf180/`" with the reason each change is neutral (empty if none).
- [ ] **Step 4: Run** the full suite including slow tests from a clean clone with the PDK fetched: `git clone . /tmp/x && cd /tmp/x && nix develop -c pytest -q`, and `python3 astran_pdk.py gf180`. Expected: all pass; the table is the one in the README.
- [ ] **Step 5: Commit** `git commit -m "Document the gf180 adapter"`.
