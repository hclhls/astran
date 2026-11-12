# sky130 PDK adapter for Astran — design

Date: 2026-11-12
Status: awaiting approval

Items marked **(decided)** were chosen by the project owner. Items marked
**(my call)** are defaults picked while writing this up and can be overturned.
Everything under "Left to the builder" is open.

## Intent

Astran generates standard-cell layouts from transistor netlists, but it only
knows technologies through hand-written rule files for a few older or academic
processes (0.35 µm, 65 nm, FreePDK45). The goal is to make it produce real
cells in open PDKs, starting with SkyWater sky130, so its output can be judged
against a foundry library: `sky130_fd_sc_hd`.

The first use is generating a few cells and comparing them with their hd
counterparts on area. A full library pushed through OpenROAD is a possible
later step, not part of this work.

## Goals

1. Generate INV, NAND2, NOR2 and `a21oi` in sky130 from the hd library's own
   transistor netlists, export GDS, and pass sky130 DRC and LVS.
   (Cell list: INV/NAND2/NOR2 plus one complex cell is **(my call)**; `a21oi`
   as the complex cell is **(my call)**.)
2. One command that runs the whole chain for a cell or list of cells and
   prints a table: cell, DRC result (alone and abutted), LVS result, Astran
   area, hd area, ratio.
3. A structure where a second PDK is a new directory of data and scripts, not
   new generator code. **(decided: generic core plus per-PDK post-processing)**

## Non-goals (this round)

- Timing and power comparison. **(decided: area first, timing/power later)**
- Drop-in compatibility with hd: same 2.72 µm height, met1 rails over li1,
  tapless cells with VPB/VNB pins, pins on the routing grid.
  **(decided: own template first, drop-in later)**
- LEF and Liberty output, a full cell library, any OpenROAD run.
- A second PDK. gf180mcu is the likely next one; nothing is built for it now
  beyond keeping the directory shape ready.
- The GUI. Everything runs through Astran's shell/script mode.
- Deriving rule values automatically from PDK tech files. The rule file is
  written by hand from the sky130 design rules.

## Anti-goals

These make the work a failure even if the table prints "pass":

- sky130 special cases hardcoded in the generator (`if tech == sky130`, layer
  names like npc or hvtp in the C++).
- "Clean" achieved by waiving, filtering or editing DRC rules, or by loosening
  LVS (ignoring device parameters, black-boxing).
- Hand-edited layouts. Every polygon in the checked GDS comes from Astran or
  the post-processing script.

## Current state

Findings from reading the code and the machine, for the builder's orientation.

**Astran**
- Repo root is `/mnt/home3/Work/astran`; sources are in `Astran/src`.
- A technology is one `.rul` file: `TECHNAME`, `MINSTEP`, `MLAYERS`, about 95
  named rules (`src/rules.h`, enum `rule_name`), and a layer map with CIF,
  GDSII and tech-name columns. `Astran/build/Work/tech_freePDK45.rul` is the
  closest existing example. `Astran/build/RULES.png` illustrates the rules.
- The layer list is a fixed enum (`layer_name` in `src/rules.h`): CONT, POLY,
  NDIF, PDIF, NSEL, PSEL, NWEL, PWEL, VIA1–9, MET1–10, CELLBOX, MET1P–MET3P.
- GDS export (`src/designmng.cpp`, `EXPORT_LAYOUT`; `src/gds.cpp`) writes a
  layer number only, datatype 0. Text labels always go on MET1's layer number.
  Coordinates are written as 2× the internal integer value.
- The cell generator assumes contact → metal1. Rails are MET1. Three cell
  templates exist (`src/circuit.cpp`): "Tapless", "Taps close to the
  boundary", "Taps w/ continuous diff".
- The SPICE reader (`src/spice.h`) accepts `M` lines whose model name is one of
  NMOS/PMOS/CMOSN/CMOSP/MODN/MODP/NMOS_VTL/PMOS_VTL, with sizes such as
  `L=0.35u W=1.6u`. Everything is upcased.
- Script mode: `Astran script.run` or `Astran --shell`; example in
  `Astran/build/HOWTO.txt`. Relevant settings exist as shell commands
  (`SET VDDNET`, `SET GNDNET`, `SET ROWHEIGHT`, `SET SUPPLYSIZE`,
  `SET CELLTEMPLATE`, `SET HGRID`/`VGRID`, `SET LPSOLVE`, …; see
  `src/designmng.h`).
- Compaction needs an external LP/MIP solver. Recent commits added open-source
  solver support including HiGHS (`src/compaction.cpp`). `/usr/bin/lp_solve`
  exists on this machine.
- Known issue from `Astran/build/ISSUES.txt`: spacing between same-net metal
  and poly shapes is not checked, which produces DRC errors.
- There is no Astran binary on this machine and no wxWidgets installed. Even
  shell mode goes through `wxAppConsole` (`src/icpdApp.cpp`).

**sky130 and tools**
- sky130A is installed through ciel at
  `~/.ciel/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130A`.
  `libs.ref/sky130_fd_sc_hd/` has `cdl`, `spice`, `gds`, `lef`;
  `libs.tech/` has `magic`, `netgen`, `klayout` (DRC, LVS, `.lyp` layer file).
- `/home/jesse/Work/FlexRAM/third_party/dffram/flake.nix` is a five-line flake
  that re-exports the librelane dev shells. That shell supplies magic, netgen,
  klayout, OpenROAD and ciel. Nix is installed (`nix 2.33.3`).
- hd netlists come in two forms. CDL:
  `MMPA0 pndA A1 VPWR VPB pfet_01v8_hvt m=1 w=1.0 l=0.15 …` (microns, with
  continuation lines). SPICE:
  `X1 VPWR A Y VPB sky130_fd_pr__pfet_01v8_hvt w=1e+06u l=150000u`.
  Ports are `… VGND VNB VPB VPWR …`.
- sky130 layer/datatype pairs, read from `sky130A.lyp`:
  nwell 64/20, diff 65/20, tap 65/44, poly 66/20, licon1 66/44, npc 95/20,
  li1 67/20, li1 pin 67/16, li1 label 67/5, mcon 67/44, met1 68/20,
  met1 pin 68/16, met1 label 68/5, via 68/44, met2 69/20, nsdm 93/44,
  psdm 94/20, hvtp 78/44, prBoundary 235/4.
- `sky130_fd_sc_hd__inv_1` is 1.380 × 2.720 µm in the LEF.

## Design

### Shape **(decided)**

Astran's C++ stays technology-neutral. It gets only general fixes that any PDK
would benefit from. Everything specific to sky130 lives in a per-PDK directory:
data Astran reads, plus a post-processing step that turns Astran's output into
PDK-correct GDS.

### Repository layout **(my call)**

```
flake.nix                     dev shell (librelane tools + what Astran needs to build)
pdks/
  README.md                   what an adapter directory must contain
  sky130/
    tech.rul                  Astran rule file and layer map for sky130
    cell.run fragment/config  Astran circuit settings (template, row height, rails, grids)
    netlist conversion        hd netlist → Astran SPICE, and → LVS reference
    post-processing script    Astran GDS → sky130 GDS (klayout, batch mode)
    check scripts             DRC and LVS runners
    cells.txt                 the default cell list
<driver>                      top-level command: PDK name + cell list → table
```

File names inside `pdks/sky130/` are illustrative; the file *set* is the
contract. `pdks/README.md` states that contract so the next PDK can follow it.

### How sky130 maps onto Astran's model **(my call)**

| Astran layer | sky130 layer | Note |
|---|---|---|
| CONT | licon1 | |
| MET1 | li1 | Astran's first routing layer and rails |
| VIA1 | mcon | |
| MET2 | met1 | |
| VIA2 / MET3 | via / met2 | only if a cell needs them |
| POLY, NWEL, NSEL, PSEL | poly, nwell, nsdm, psdm | |
| NDIF, PDIF | diff, or tap where it is a well/substrate tie | split in post-processing |
| CELLBOX | prBoundary | |
| MET1P and labels | li1 pin / li1 label | |

Consequences, accepted for this round:
- Rails are li1, not met1. This is not how hd does it and is not drop-in. It
  must still be DRC-clean.
- Cells carry their own taps under the rails (one of Astran's tap templates),
  so bodies are tied to the rails inside the cell.
- The rule file's "M1" rules hold li1 values, "CT" rules hold licon values,
  "VI" rules hold mcon values, "M2" rules hold met1 values, and so on.

### Changes to the Astran core (all technology-neutral)

1. **GDS layer/datatype.** The GDSII column of the layer map accepts
   `layer/datatype` (e.g. `67/20`); a bare number keeps meaning datatype 0 so
   existing rule files still work. **(decided in principle: "datatype support
   in the layer map")**
2. **Pin labels on the pin layer.** Labels are written on the layer/datatype
   configured for the pin layer of the metal they sit on, not on MET1's drawing
   layer. How a label layer distinct from the pin-shape layer is expressed
   (sky130 uses 67/16 for pin shapes and 67/5 for text) is the builder's
   choice, as long as it is expressed in the rule file. **(my call)**
3. **Linux shell build.** Astran builds and runs in script mode inside the
   project's Nix shell. See "Environment".
4. **Generator fixes found on the way.** If the four cells cannot be made clean
   because of a generator defect or a rule Astran cannot express (the known
   same-net spacing issue, minimum-area on li1, and so on), fixing it in the
   generator as a general rule is in scope. **(decided)** Adding a rule slot to
   `rule_name` is fine when the rule is a generic concept ("minimum MET1
   area") and not a sky130 name.

No other core changes are planned. In particular the generator does not learn
about npc, hvtp or tap.

### Post-processing step (sky130-specific)

Input: the GDS Astran exported. Output: the GDS that gets checked. Run with
klayout in batch mode from the Nix shell. It:

- derives **npc** around licon-on-poly, merged and sized to satisfy the npc
  rules;
- derives **hvtp** over the PMOS devices, because the hd netlists use
  `pfet_01v8_hvt`;
- reclassifies diffusion that is a tie (p+ outside nwell, n+ inside nwell)
  from **diff** to **tap**;
- fixes anything else that is purely a derived-layer matter (for example
  merging or squaring implant shapes to meet implant width/spacing rules);
- leaves all drawn routing, contacts, poly and diffusion geometry alone.

The boundary: post-processing may add or reclassify derived layers. It may not
move or resize devices, contacts or wires to fix a violation. A violation in
drawn geometry is fixed in the rule file or the generator.

Risk to plan for: because the compactor does not know about npc or hvtp, a
derived shape may violate its own spacing rule in a layout Astran considers
legal. The first answer is a conservative value in the rule file (for example
wider poly-contact spacing). If that is not enough, stop and report: say
which cell and rule, what was tried, and what the options are. Do not teach
the compactor about derived layers without the owner agreeing, since that
changes the generic-core decision. Abutment (below) is the most likely place
for this to come up.

### Netlist conversion (sky130-specific)

From the hd library netlist for the requested cell, produce:

- **Astran input:** `M` lines with NMOS/PMOS models and sizes in the form
  Astran reads, supply nets named consistently with `SET VDDNET`/`SET GNDNET`,
  body terminals dropped (Astran ties bodies through its taps). Same transistor
  count, widths and lengths as hd, so the comparison is layout-only.
  **(decided: use hd's own netlists)**
- **LVS reference:** the hd devices (`sky130_fd_pr__nfet_01v8`,
  `sky130_fd_pr__pfet_01v8_hvt`) with VNB tied to VGND and VPB tied to VPWR,
  since the Astran cell has taps and therefore four-terminal-less ports. The
  subcircuit's ports are the signal pins plus VPWR and VGND.

Astran may fold transistors. LVS must still match with normal parallel-device
merging; that is standard netgen behaviour and not a waiver.

### Checks **(my call)**

- **DRC gate:** magic with the PDK's `sky130A.tech`, full DRC style. Zero
  errors required.
- **LVS gate:** magic extraction plus netgen with the PDK's
  `sky130A_setup.tcl`, against the LVS reference above. Must report a match,
  including device sizes.
- **Second opinion:** klayout with the PDK's `sky130A_mr.drc`, run and
  reported in the table. Checks that cannot apply to a lone cell (density,
  seal ring, chip-level) are switched off through the deck's own options and
  the switches used are listed in the output. Any other klayout violation
  counts as a failure.

This is the same pairing librelane uses for signoff, which is why magic/netgen
is the gate.

### Abutment **(decided)**

Cells must be DRC-clean when abutted, not only alone. For each cell the driver
also builds a small array from the post-processed cell and runs the same DRC
gate (magic, plus klayout as second opinion) on it. The array covers the
placements a row-based design uses: the cell next to a copy of itself, next to
a mirrored copy, and stacked rail-to-rail against a vertically flipped copy.
Cells abut at their CELLBOX edges with no gap, and the CELLBOX is what the
area comparison uses.

Abutting each cell against the other three cells in the list is also run
**(my call)**, since a library is only usable if different cells can sit
together.

What this adds to the work:
- the post-processing step needs edge behaviour for the derived layers (npc,
  hvtp, tap, merged implants) so they are legal across a cell boundary, for
  example by keeping them half a spacing inside the CELLBOX or extending them
  to the edge so they merge with the neighbour;
- the rule file may need more conservative values near the cell edge;
- LVS stays per cell; the array is a DRC check only.

### Area comparison

- Astran area: the CELLBOX rectangle of the generated cell.
- hd area: `SIZE` of the corresponding `_1` drive-strength macro in
  `sky130_fd_sc_hd.lef`.
- The table also shows width and height for both, since the templates differ.
- The output states plainly that the Astran cells include well taps and hd
  cells do not, so the ratio is pessimistic for Astran by the tap area.
  **(my call)**

### Driver **(my call)**

A Python script (Python is already in the librelane shell). Given a PDK name
and a cell list, for each cell it runs: netlist conversion → Astran script →
post-processing → DRC → LVS → area lookup, keeps every intermediate file and
log in a per-cell output directory outside version control, and prints the
table. A failing cell does not stop the others. Exit status is non-zero if any
cell fails DRC or LVS.

The driver contains no sky130 knowledge; it calls the pieces in
`pdks/<name>/` by the contract in `pdks/README.md`.

### Environment **(my call)**

- A `flake.nix` at the repo root gives one `nix develop` shell with the
  librelane tools (same input as the dffram flake), a C++ compiler, whatever
  Astran needs to link, and an LP/MIP solver.
- The PDK is located through ciel / `PDK_ROOT`, with the installed version
  above as the pinned default. Nothing from the PDK is copied into the repo.
- No personal absolute paths in committed files.

## Constraints

- sky130 manufacturing grid is 0.005 µm. All output geometry must be on grid,
  including after Astran's 2× coordinate scaling in GDS export and after
  post-processing.
- Existing rule files (`tech_035.rul`, `tech_0065.rul`, `tech_freePDK45.rul`)
  must keep loading and exporting as before.
- The repo has no tests today. The driver's table on the four cells is the
  acceptance test; unit tests for the new core changes (layer/datatype parsing
  at least) are expected.

## Done means

Inside `nix develop`, from a clean checkout, the driver run on the default
cell list finishes with INV, NAND2, NOR2 and a21oi each showing DRC pass (magic
and klayout) alone and abutted, LVS match, and both areas with their ratio. No
rule was waived,
and no sky130-specific name appears in `Astran/src`.

## Left to the builder

- How Astran is built on Linux: add wxWidgets to the Nix shell and build as
  today, or give script mode an entry point that does not need wx. Prefer
  whichever is less invasive; the GUI need not build.
- Which solver the shell provides and Astran is pointed at (HiGHS is the
  natural choice given the recent commits).
- Which hd netlist form (CDL or SPICE) the converter reads.
- Which Astran tap template, row height, supply width, track grid and nwell
  position give clean and reasonably compact sky130 cells. Start from what
  passes; tuning for area comes after clean.
- The actual rule values in `tech.rul`, taken from the sky130 design rule
  documentation and cross-checked against `sky130A.tech`. Where Astran has one
  rule and sky130 has several conditional ones, use the conservative value and
  note it in a comment.
- Whether Astran writes final PDK layer numbers directly and post-processing
  only adds derived layers, or Astran writes an intermediate numbering that
  post-processing remaps. Either satisfies the design.
- Internal structure and naming of scripts, and the exact table format.
- Whether folding is used for these four cells.

## Later, in rough order

1. Timing and power: extraction, characterisation, comparison with hd Liberty.
2. Drop-in hd template: 2.72 µm height, met1 rails over li1, tapless with
   VPB/VNB, pins on the li1/met1 track grid.
3. LEF/Liberty output and a larger cell set through OpenROAD.
4. A second adapter (gf180mcu), which tests whether the contract in
   `pdks/README.md` is really PDK-neutral.
