# gf180 adapter

`python3 astran_pdk.py gf180 [cell ...]` (default cells: inv, nand2, nor2, aoi21) runs, per cell:
7t library SPICE netlist -> Astran netlist + LVS reference -> `astran-cli` -> post-processing -> DRC
(magic and klayout) alone and in an abutment array -> LVS (magic extraction + netgen) -> area vs
`gf180mcu_fd_sc_mcu7t5v0` (gf180mcuD, 5 V library with 6 V devices `nfet_06v0` / `pfet_06v0`,
N gate 0.6 um, P gate 0.5 um, 3.92 um tall).

The PDK is `$ASTRAN_GF180_DIR` if that is set (and it is an error if it is not a directory: it is never replaced by
another PDK), otherwise the ciel version pinned in `pdks/gf180/pdk.py` under `${PDK_ROOT:-~/.ciel}`, then
`${PDK_ROOT:-~/.ciel}/gf180mcuD`. To fetch it: `ciel enable --pdk-family gf180mcu 0fe599b2afb6708d281543108caf8310912f54af`.

## Result of the default run

```
cell   gen  drc   drc-abut  lvs   w×h          ref w×h      area    ref area  ratio
inv    ok   pass  pass      pass  2.240×3.920  2.240×3.920  8.781   8.781     1.00
nand2  ok   pass  pass      pass  3.360×3.920  2.800×3.920  13.171  10.976    1.20
nor2   ok   pass  pass      pass  3.360×3.920  3.360×3.920  13.171  13.171    1.00
aoi21  ok   pass  pass      pass  4.480×3.920  4.480×3.920  17.562  17.562    1.00
```

inv, nor2 and aoi21 are the size of the foundry cell; nand2 is 20 % wider (the foundry stacks its N pair in
2.80 um; Astran needs one more track). The ratio is against the foundry's prBoundary and is reported, not gated.

## Layer mapping (Astran -> gf180)

| Astran | gf180 | | Astran | gf180 |
|---|---|---|---|---|
| CONT | contact 33/0 | | MET1 | metal1 34/0 |
| POLY | poly2 30/0 | | MET1P, MET1L (pin, label) | metal1 label 34/10 |
| NDIF, PDIF | comp 22/0 | | VIA1 | via1 35/0 |
| NSEL, PSEL | nplus 32/0, pplus 31/0 | | MET2 | metal2 36/0 |
| NWEL | nwell 21/0 | | VIA2, MET3 | via2 38/0, metal3 42/0 |
| PWEL | lvpwell 204/0 | | CELLBOX | prBoundary 0/0 |

Added by post-processing, not by Astran: dualgate 55/0, the V5_Xtor device marker 112/1, and the well labels
VNW on 21/10 and VPW on 204/10. There is no local interconnect, so an "M1" rule in `tech.rul` holds a
metal1 value, "CT" a contact value, "VI" a via1 value, "M2" a metal2 value.

## Not drop-in with sky130, and what the reference does

- **Tapless cells.** The 7t cells have no taps; tap cells (`filltie`) are placed in the row separately. So do
  ours. With tap strips in the cell, poly end-caps (PL.4 0.22) and poly to unrelated COMP (PL.5a 0.3) leave
  0.46 um for the NMOS in 3.92 um and nor2 (NMOS 0.565 um) cannot be built; DF.1a_MV (0.3 um) forbids folding
  it. Template: "Taps close to the boundary".
- **DRC is run with the library tap cell.** klayout's DF.13_MV / DF.14_MV want a tap within 15 um, and the
  foundry's own lone `inv_1` fails them (`test_klayout_drc_flags_tapless_foundry_inv_alone`). `taps.py` places
  `gf180mcu_fd_sc_mcu7t5v0__filltie`, read from the installed PDK, at both ends of every row and every 24 um
  along it (the cell before a mid-row tap is repeated after it, so no cell-to-cell interface drops out of the
  check), and DRC runs on that. The rules are not waived. LVS runs on the bare cell.
- **Body pins.** The LVS reference keeps `VDD VNW VPW VSS` with the bodies on VNW/VPW, and the layout labels the
  nwell `VNW` (21/10) and the substrate `VPW` (204/10), exactly like the foundry cells.
  Reference widths carry the `u` suffix (magic writes `w=1.22u`; without it netgen reads metres).
- **5 V devices.** The deck takes a gate for a 6 V one (L 0.7 / 0.55) unless V5_Xtor marks it, so post-processing
  draws V5_Xtor over the cell; dualgate is drawn over the cell + 0.28, comp + 0.24, poly + 0.4 (DV.6, DV.8).
- **Rails** are metal1, wide (supplysize 0.6) and centred on the cell boundary.
- Grid 0.56 um (the metal2 pitch, and the foundry's placement pitch) in both directions, 7 rows = 3.92 um.

## Rule values

`tech.rul` is hand-written from the klayout DRC decks in `libs.tech/klayout/drc/rule_decks` and cross-checked
against `gf180mcuD.tech`, using the `*_MV` (6 V device) rules. Rule names are in the comments. Where Astran has one
rule and gf180 several, the conservative value is used: `S1DFP1` (0.3, PL.5b_MV), `E1DFP1` (0.4, DF.6_MV),
`E1WNDP` and `S1DNWN` (0.6, DF.4c_MV; the second mirrors the first), `S1DFDF` (0.36, DF.3a_MV), `A1M1` and
`A1DF` (rounded up to the 0.005 step). `E1INDF` / `E1IPDF` hold the tap-implant enclosure (0.1); NP.5a / PP.5a
(0.23 around gates) is met by the half-cell implants (`pnselborder 0.2`, the foundry's implant overhang; 0.23
violated PP.3cii / NP.3cii against the neighbouring tap cell).

## Post-processing (derived layers only)

`postprocess.py` never moves or resizes poly, diffusion, contacts, metal or the wells. It draws dualgate and
V5_Xtor and labels the wells (VNW and VPW, inside the cell box near its left edge, as the foundry does).
The tapless cells have no tap strips, so there is nothing to untangle between the n and p implants.

## Checks

- DRC gate: magic `drc(full)` style, zero errors; klayout on the gf180 deck assembled the way the PDK's `run_drc.py`
  builds it (`main.drc` is only a header and runs no rules: the deck is `main.drc` + every rule table + `tail.drc`),
  variant C (5 metal layers, 9K top metal, the PDK default). klayout exits 0 even when it finds violations, so
  anything else, a log without a rule executed, or one that never reaches the end of the deck is a failure: an
  aborted deck leaves a well-formed report holding only the rules that ran before the abort.
- klayout switches that are off, each with its reason (printed under the table):
  connectivity off: the connectivity-based rules need a full netlist context, not one standard cell;
  density off: a die-wide density rule cannot be met by a single cell;
  antenna off: a chip-level check, not meaningful for one cell.
- LVS: magic extraction + netgen with the PDK's `gf180mcuD_setup.tcl` against the library's transistor netlist.
  Nothing is waived or black-boxed.
- A checker that crashes, times out or leaves no report is a failure, never "0 errors".

## Astran settings

`set vddnet VDD`, `set gndnet VSS`, template "Taps close to the boundary", hgrid = vgrid = 0.56, rowheight 7,
supplysize 0.6, nwellpos 1.76, nwellborder 0.6, pnselborder 0.2; `cellgen compact 1 1 50 2 1 1 0 0 0 600`.
Gridded poly (the second `1`) matters: with `1 0 ...` HiGHS reached its 600 s limit on nor2 with no feasible point.

The 600 is a budget for the whole solve, not one HiGHS run. HiGHS sometimes stalls without finding any feasible
point, depending on its random seed (aoi211 with HiGHS 1.14: seed 0 stalls, seeds 1 and 2 solve in about 6 s).
`Compaction::solve` therefore runs it for 30 s, and if that ends with no solution, retries with the next seed and
twice the time, until the budget is spent. If an attempt found a feasible point but was still improving at its cap,
the same seed is run again for the rest of the budget. A solve that ends with no feasible point is an error
("Could not solve the ILP model"), not an empty cell.

## Changed outside `pdks/gf180/`

- `pdks/common.py`: `logical_lines` (SPICE/CDL logical-line reader) moved here from sky130's `netlist.py`, since
  both adapters use it. Neutral; sky130 behaviour unchanged.
- `tests/`: `conftest.py` fixtures, `test_acceptance.py` also forbids `gf180` and `dualgate` in `Astran/src`,
  `test_gate_length.py` (Astran already draws each gate at its own transistor's length).
- `Astran/src`: nothing.
