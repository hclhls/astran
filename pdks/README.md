# PDK adapters

`astran_pdk.py <pdk> [cell ...]` knows nothing about any PDK. For `<pdk>` it imports
`pdks.<pdk>.adapter` and calls the functions below. A new PDK is a new directory
`pdks/<name>/` with an `adapter.py` that defines exactly these names.

```python
DEFAULT_CELLS: list[str]                       # cells run when none are named
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

## Rules

- The driver contains no PDK-specific names or layer numbers; everything PDK-specific is here.
- Cell names: the user's short name (`inv`) maps to the library cell, to an Astran cell name,
  and to the final top cell name (`layout_name`); each adapter documents its own mapping.
- Nothing from the PDK is copied into this repository; the adapter locates the installed PDK.
