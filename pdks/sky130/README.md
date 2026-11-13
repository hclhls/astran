# sky130 adapter

`python3 astran_pdk.py sky130 [cell ...]` (default cells: inv, nand2, nor2, a21oi) runs, per cell:
hd CDL netlist -> Astran netlist + LVS reference -> `astran-cli` -> post-processing -> DRC (magic and
klayout) alone and in an abutment array -> LVS (magic extraction + netgen) -> area vs `sky130_fd_sc_hd`.

## Layer mapping (Astran -> sky130)

| Astran | sky130 | | Astran | sky130 |
|---|---|---|---|---|
| CONT | licon1 66/44 | | MET1 / MET1P / MET1L | li1 67/20, pin 67/16, label 67/5 |
| POLY | poly 66/20 | | VIA1 | mcon 67/44 |
| NDIF, PDIF | diff 65/20 | | MET2 | met1 68/20 |
| NSEL, PSEL | nsdm 93/44, psdm 94/20 | | VIA2, MET3 | via 68/44, met2 69/20 |
| NWEL | nwell 64/20 | | CELLBOX | prBoundary 235/4 |

So an "M1" rule in `tech.rul` holds an li1 value, "CT" a licon value, "VI" an mcon value, "M2" a met1 value.
PWEL has no GDS layer (sky130 has no drawn pwell).

## Not drop-in with hd

- Rails are **li1**, not met1, and are centred on the cell boundary (half of each rail lies outside the cell box).
- Cells carry their own taps: a continuous tap strip with contacts under each rail (Astran template
  "Taps w/ continuous diff"). hd cells are tapless and get taps from separate tap cells.
- Cell height is 3.4 um (10 rows of the 0.34 um grid) against 2.72 um. A height of 9 rows was tried and
  rejected: post-processing then reports "npc too close to cell edge" for nand2, nor2 and a21oi.
- No VPB/VNB pins; bulk is tied to VPWR/VGND through the taps.

## Rule values

`tech.rul` is written by hand from the sky130 design rules and cross-checked against
`libs.tech/magic/sky130A.tech`. Where Astran has one rule and sky130 several, the conservative value is used,
with a `*` comment: `S2P1P1`, `E1M2VI`, `S2M2M2`, `E1M2V2`, `E1M3V2`, and `S1CTDF` (0.235, the poly-contact to
p-diffusion value of licon.9/psdm.5a). `E3DFCT` (0.12, licon.7) is a generic rule slot added to Astran for the
diffusion enclosure of a tap contact; rule files that do not set it keep the old behaviour.

## Post-processing (derived layers only)

`postprocess.py` never moves or resizes poly, diffusion, contacts or metal. It reclassifies tap diffusion
(65/20 -> 65/44), gives each tap the implant of its own type (Astran draws the main n and p implants over the
tap strips), derives npc around poly contacts and hvtp over the PMOS gates (hd uses `pfet_01v8_hvt`), closes
implant gaps, and extends nwell/hvtp/implants to the cell edge so abutting cells merge. If npc cannot be kept
0.135 um inside the left/right cell edge it raises an error instead of moving contacts.

## Checks

- DRC gate: magic, `drc(full)` style, zero errors; second opinion: klayout `sky130A_mr.drc`.
  Switched off: `seal` and `floating_met` only (printed under the table). Density is a separate deck and is not run.
- LVS: magic extraction + netgen with the PDK's `sky130A_setup.tcl`, against the hd transistor netlist with
  bulks tied to the supplies. Nothing is waived or black-boxed.
- A checker that crashes, times out or leaves no report is a failure, never "0 errors".
- The foundry's own tapless `inv_1` fails magic's full DRC (nwell.4, LU.2, LU.3): there is no tap in the cell. The
  checker tests therefore use the inverter next to a tap cell as the magic reference.

## Area ratio

The Astran cells include well taps and the hd cells do not, so the ratio is pessimistic for Astran by the tap area.
