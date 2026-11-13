# PDK adapters

`astran_pdk.py <pdk> [cell ...]` knows nothing about any PDK. For `<pdk>` it imports
`pdks.<pdk>.adapter` and calls the functions below. A new PDK is a new directory
`pdks/<name>/` with an `adapter.py` that defines exactly these names.

```python
DEFAULT_CELLS: list[str]                       # cells run when none are named
BOUNDARY_LAYER: tuple[int, int]                # layer/datatype of the cell box in the final GDS
def check_environment() -> None                # raise AdapterError if PDK or tools are missing
def layout_name(cell: str) -> str              # top cell name of the final GDS
def write_astran_netlist(cell: str, out: Path) -> str   # returns the Astran cell name
def write_lvs_netlist(cell: str, out: Path) -> None
def astran_script(astran_cell: str, netlist: Path, gds_out: Path) -> str   # full .run text
def postprocess(gds_in: Path, gds_out: Path, cell: str) -> None
def drc(gds: Path, top: str, workdir: Path) -> list[tuple[str, CheckResult]]
def lvs(gds: Path, top: str, ref: Path, workdir: Path) -> CheckResult
def cell_size(gds: Path, top: str) -> tuple[float, float]       # CELLBOX w, h in um
def reference_size(cell: str) -> tuple[float, float]            # foundry cell w, h in um
def notes() -> list[str]                       # lines printed under the table
```

`AdapterError` (from `pdks.common`) carries a message that is shown to the user unchanged.
`CheckResult(ok, count, report, detail)`: a checker that crashes, times out or leaves no
report returns `ok=False, count=-1`; it never reports "0 errors".

`pdks.common.logical_lines(text)` reads SPICE/CDL as logical lines (comments dropped, `+` continuations joined).

`pdks.common.build_abutment(cell_gds, top, neighbours, BOUNDARY_LAYER, out)` builds the abutment
array (self, mirrored self, flipped rows, and each neighbour) that the driver runs through `drc`.

## Rules

- The driver contains no PDK-specific names or layer numbers; everything PDK-specific is here.
- Cell names: the user's short name (`inv`) maps to the library cell, to an Astran cell name,
  and to the final top cell name (`layout_name`); each adapter documents its own mapping.
- Nothing from the PDK is copied into this repository; the adapter locates the installed PDK.

## Adding a PDK

1. Create `pdks/<name>/` with `__init__.py` and `adapter.py` defining exactly the names above.
2. Locate the installed PDK (environment variable, then standard paths) and raise `AdapterError` listing every
   path tried if it is missing. Copy nothing from the PDK into this repository.
3. Write a rule file for Astran (`tech.rul`; the GDSII column accepts `<layer>/<datatype>`; `MET1L` is the label layer).
4. Convert the library's cell netlists to the Astran SPICE form and to an LVS reference.
5. Return a complete `.run` script from `astran_script`, ending in `export layout`.
6. Put everything PDK-specific (derived layers, checks, naming) in the adapter, never in `Astran/src` or the driver.
7. Make every checker report a crash, timeout or missing report as a failure (`ok=False, count=-1`).
8. Test the checkers on the foundry's own cells before trusting them on Astran output, and check that each one
   reports a deliberate violation: a deck entry point can run without executing any rule (gf180's `main.drc` is
   only a header; the real deck is it plus the rule tables, as the PDK's `run_drc.py` assembles it), and that
   looks exactly like "0 errors". Also check that a deck which aborts part-way is a failure.
9. Run the foundry's own cell through every checker alone. If it fails (tap-distance rules for a tapless library),
   `drc` may check a layout with the library's helper cells added (gf180: tap cells at the row ends) provided the
   rules still run and the cell under test is not changed; say so in the PDK's README. Rows longer than the
   helper cell's reach need the helper along the row as well.
10. Decide the LVS body connections from what the library does: a tapless library names its wells with labels and
    keeps body pins in its netlist (gf180); a library whose cells carry taps ties them to the supplies (sky130).
    Units in the reference netlist matter: magic writes `w=1.22u`, and a bare `1.22` reads as metres.
