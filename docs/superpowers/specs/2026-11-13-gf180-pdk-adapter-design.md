# gf180mcu PDK adapter for Astran — design

Date: 2026-11-13
Status: awaiting approval (builder check done)

Items marked **(decided)** were chosen by the project owner. Items marked
**(my call)** are defaults picked while writing this up and can be overturned.
Everything under "Left to the builder" is open.

## Intent

The sky130 adapter (`docs/superpowers/specs/2026-11-12-sky130-pdk-adapter-design.md`,
merged) made Astran generate real cells in an open PDK and judge them against a
foundry library. The owner wants to see whether Astran can **support more PDKs**,
and gf180mcuD (GlobalFoundries 180 nm, open_pdks) is the second one. The new PDK is
also a test of the sky130 design: the adapter contract and driver should carry over
unchanged, and any C++ change gf180 forces should be a generic improvement, not a
gf180 workaround. **(decided)**

The second use is the same as for sky130: compare generated cells with a foundry
library, here `gf180mcu_fd_sc_mcu7t5v0`. **(decided: 7-track)**

## Goals

1. Generate INV, NAND2, NOR2 and AOI21 in gf180mcuD from the 7t library's own
   transistor netlists (`inv_1`, `nand2_1`, `nor2_1`, `aoi21_1`), export GDS, and
   pass gf180 DRC and LVS. **(cell list mirrors sky130: my call)**
2. The same single command as for sky130 (`astran_pdk.py`, now with a `gf180`
   argument) prints the table: cell, generation, DRC alone, DRC abutted, LVS,
   width×height, reference width×height, area, reference area, ratio.
3. Checks are the same three as for sky130, so both tables mean the same thing:
   magic `drc(full)`, klayout DRC, and magic extraction + netgen LVS.
   **(decided: sky130 checks)**
4. The PDK-neutral pieces (`astran_pdk.py`, `pdks/common.py`, the adapter contract in
   `pdks/README.md`) work without gf180-specific edits. Where they don't, that is
   reported as a finding and fixed in a neutral way.
5. `pdks/README.md`'s "Adding a PDK" section is checked against reality: whatever
   was missing or wrong when doing gf180 is corrected there.

## Non-goals (this round)

- Other gf180 libraries (9t, 3.3 V variants), other gf180 variants (A, B, C).
  **(decided: 7t only)**
- Cells with more than one drive strength, sequential cells, a full library.
- klayout LVS deck and klayout's `run_drc.py` runner. gf180 ships both; they are
  not used so that the check set matches sky130. **(decided)**
- Passing OpenROAD, or matching reference area. Area is reported, not a gate.
- A third PDK. This round only needs to show that a second one fits.

## Anti-goals

- gf180 specifics (layer numbers, rule values, tap handling, 6 V device models)
  leaking into `Astran/src/` or `pdks/common.py`.
- Weakening a check to get a pass: dropping rules, switching off klayout rule
  groups beyond what is justified and recorded, or counting a crashed or timed-out
  tool as clean. The sky130 failure rule stands: crash / timeout / no report = fail.
- Hand-editing GDS output per cell. Post-processing is derived-layer logic that
  works for any cell, as in sky130.

## Current state

Verified on this machine on 2026-11-13:

- gf180mcuD is installed at
  `~/.ciel/ciel/gf180mcu/versions/0fe599b2afb6708d281543108caf8310912f54af/gf180mcuD`
  (7.5 GB for the family), fetched with `ciel enable --pdk-family gf180mcu`. The
  revision is the one librelane pins (`librelane/open_pdks_rev`), the same revision
  sky130 uses.
- `libs.tech/magic/gf180mcuD.tech` (+ `.magicrc`, `-GDS.tech`), the klayout DRC
  decks in `libs.tech/klayout/drc/rule_decks` (+ `main.drc`, `run_drc.py`), the
  klayout LVS deck, and the netgen setup `libs.tech/netgen/gf180mcuD_setup.tcl`.
- Reference library `libs.ref/gf180mcu_fd_sc_mcu7t5v0/` with `gds`, `lef`,
  `spice`, `cdl`, `mag`.

What the reference cells look like (from the GDS and SPICE):

| | inv_1 | nand2_1 | nor2_1 | aoi21_1 |
|---|---|---|---|---|
| prBoundary (layer 0/0), µm | 2.24 × 3.92 | 2.80 × 3.92 | 3.36 × 3.92 | 4.48 × 3.92 |

All four were read from the GDS boundary on 2026-11-13. The GDS bbox is wider
(inv_1: 3.10 × 4.78) because wells extend 0.43 µm past the cell edge, so the
reference area uses the boundary. **(my call)**

- Layers seen in inv_1: nwell 21/0, pwell 204/0, comp 22/0 (two shapes only: the
  two transistor diffusions, so the reference cells are **tapless**), poly2 30/0,
  contact 33/0, metal1 34/0, plus implants 31/0, 32/0 and dualgate 55/0.
  Metal2 is 36/0, via1 35/0, metal3 42/0.
- There is **no local interconnect** layer. Astran's three routing layers would be
  CONT = contact, MET1 = metal1, VIA1 = via1, MET2 = metal2, VIA2 = via2,
  MET3 = metal3. **(my call, to be confirmed against the rule decks)**
- The 7t netlists use 4 pins for power (`VDD VNW VPW VSS`) and **6 V devices**:
  `nfet_06v0` with L = 0.6 µm and `pfet_06v0` with L = 0.5 µm. The two gate lengths
  differ. sky130 had a single minimum gate length.
- The AOI cell is `aoi21_1`, not `a21oi_1`.

Reused from sky130 unchanged (verified there): the Astran CLI build, GDS export with
layer/datatype mapping and label layer, the rule-file `layer/datatype` syntax, the
`E3DFCT` generic rule, the continuous-diffusion tap template, the abutment array,
`run_tool` failure semantics, and the driver's table and exit codes.

## Design

### Shape **(decided: same as sky130)**

`pdks/gf180/` is an adapter directory implementing the existing contract. The driver
discovers it by name. No new mechanism.

### Repository layout **(my call)**

    pdks/gf180/{__init__,pdk,netlist,adapter,postprocess,checks}.py
    pdks/gf180/tech.rul
    pdks/gf180/README.md
    tests/…  gf180 tests next to the sky130 ones, parametrised over the PDK where a
             test is generic, and gf180-specific where not

Shared logic goes to `pdks/common.py` only if sky130 and gf180 both need it. Copying
a helper into `pdks/gf180/` first and extracting it once both uses are visible is
acceptable.

### How gf180 maps onto Astran's model **(my call)**

Layer mapping as in the table above, with the rule values hand-written in
`tech.rul` from `gf180mcuD.tech` and the klayout decks, taking the conservative value
where a rule is conditional. Each value carries a comment naming the gf180 rule.

Unlike sky130, the reference library is tapless, so the "cells carry taps" decision
from sky130 may not be needed. Whether a lone gf180 cell passes DRC without taps, or
needs in-cell taps like sky130, is open (see below). If taps are needed, the sky130
template ("Taps w/ continuous diff") is the starting point.

### Changes to the Astran core

None planned. Anything that turns out to be needed must be technology-neutral, with
a test in `Astran/tests/`, and listed in the final report. The known risk is
**per-device gate length**: if Astran's model has one poly width per technology, then
gf180's N=0.6 µm and P=0.5 µm would not both fit, and that is a core finding rather
than an adapter detail.

### Post-processing step (gf180-specific)

Derived-layer logic only, with klayout.db, as for sky130: whatever the generator does
not draw but the rule decks require (wells, implants, dualgate for 6 V devices,
boundary, any needed extensions to the cell edge). The exact set comes from the DRC
results.

### Netlist conversion (gf180-specific)

7t CDL/SPICE → Astran SPICE, mapping `nfet_06v0`/`pfet_06v0` to Astran NMOS/PMOS,
`VDD`/`VSS` to the supply nets, and `VNW`/`VPW` to the well/body connections. The LVS
reference uses gf180 device model names and the PDK's own device recognition in
magic/netgen.

### Checks **(decided)**

magic `drc(full)`, klayout DRC, magic extraction + netgen LVS with `gf180mcuD_setup.tcl`.
klayout DRC uses the gf180 decks (`main.drc`) with options chosen to match a cell-level
check; any rule group switched off is listed in `pdks/gf180/README.md` with the reason,
as was done for seal and floating metal in sky130.

### Abutment **(decided: same as sky130)**

The same array: cell, x-mirrored cell, cell, neighbours, rows alternately flipped.
Because the reference wells extend 0.43 µm past the cell edge, the abutted check is
important for gf180 and must stay a gate.

### Area comparison

Astran width × height against the reference prBoundary width × height, reported as a
ratio. Reference 3.92 µm tall: row height in the Astran grid is to be chosen so the
height is close to this; whether that is reachable is a result, not a requirement.

### Driver

`astran_pdk.py gf180 [cells…]`. No new columns.

### Environment **(my call)**

The PDK path resolves like sky130: `ASTRAN_GF180_DIR`, then
`$PDK_ROOT/ciel/gf180mcu/versions/<pinned>/gf180mcuD`, then `~/.ciel`. The pinned
revision is librelane's. A missing PDK produces an error that says how to fetch it
(`ciel enable --pdk-family gf180mcu <rev>`). Tests that need the PDK skip when it is
absent, as for sky130.

## Settled after the builder check

Answered by the project or the reference data:

- **dualgate and 6 V devices:** the reference cells draw dualgate (55/0), so the
  generated cells must too. A cell without it does not count as a pass.
- **Supply pins:** follow the sky130 precedent (`SUPPLY` map in `netlist.py`): the
  body pins `VNW`/`VPW` are merged into `VDD`/`VSS` in the LVS reference, and the
  cell is tied through its taps. The Astran model carries two supply nets.
- **Gate length:** Astran's netlist keeps a length per transistor
  (`cellnetlst.cpp`, used at `autocell2.cpp:994`), so N = 0.6 µm and P = 0.5 µm are
  representable in principle. Whether the drawn poly honours them is the first thing
  to check, before any other work.

My calls (overturn any of them):

- If per-device gate length is not honoured by the generator, a technology-neutral
  fix with a test in `Astran/tests/` is allowed. If that is not possible, stop and
  report with evidence; do not use one length for both devices and edit the LVS
  reference to match.
- In-cell taps are acceptable if a lone cell needs them for DRC. The area table
  then notes that the reference is tapless, as it did for sky130's hd cells.
- klayout rule groups: the baseline is the sky130 one (seal and floating-metal
  analogues off, each recorded with its reason). Anything beyond that needs a
  recorded reason too. Density and antenna are cell-level non-issues only if shown so.
- Metal stack for klayout options: the stack librelane uses for gf180mcuD by
  default (builder checks), with only metal1 to metal3 drawn.
- Placement grid and area ratio: the ratio is reported, never gated. A 0.56 µm
  placement pitch is not enforced.

## Constraints

- The Astran C++ stays technology-neutral; all gf180 content lives in `pdks/gf180/`.
- Deterministic output: same input, same GDS.
- The sky130 results table must not change (its tests are part of the gate).
- Work on a branch; do not push or merge without being asked.

## Done means

1. All four cells generate in gf180 and report `ok pass pass pass` (gen, DRC alone,
   DRC abutted, LVS), by one command, on a clean clone with the PDK fetched.
2. The table shows area against the 7t reference.
3. The sky130 flow and the whole existing suite still pass.
4. `pdks/README.md` is corrected where gf180 contradicted it; `pdks/gf180/README.md`
   documents the mapping and every judgement call.
5. A written list of what, if anything, had to change outside `pdks/gf180/`, with
   the reason each change is technology-neutral.

If DRC-clean cells turn out to be impossible without a core change that is not
neutral, stop and report with evidence instead of working around it.

## Left to the builder

- Row height and track count (3.92 µm reference; Astran grid values to choose).
- Whether taps are in-cell, and the exact post-processing.
- How to handle N and P gate lengths of 0.6 and 0.5 µm. First check how Astran
  handles transistor length; if the model cannot represent both, report it.
- Whether `dualgate` / 6 V device layers need to be drawn, and where.
- Fold, place, route and compaction script values.
- Whether any rule group of the klayout decks needs switching off, with reasons.
- Exact net and pin mapping for the 4-pin supply in the LVS reference.

## Later, in rough order

- 9t library, then the 3.3 V library, in gf180.
- A third PDK (e.g. IHP sg13g2), which would show whether two PDKs were enough to
  validate the contract.
- Running the generated cells through a place-and-route flow.
