"""PDK-neutral helpers shared by the driver and the adapters."""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AdapterError(Exception):
    """A problem the user should read as-is (the message is shown unchanged)."""


@dataclass
class CheckResult:
    ok: bool
    count: int        # violations, mismatches; -1 if the checker did not complete
    report: Path
    detail: str       # one line for the result table


def run_tool(argv: list, cwd: Path, log: Path, timeout: int = 600, env: dict = None) -> int:
    """Run a command with output going to `log`. Returns its exit code, or -1 on
    timeout or when the executable cannot be started."""
    Path(cwd).mkdir(parents=True, exist_ok=True)
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as f:
        try:
            r = subprocess.run([str(a) for a in argv], cwd=cwd, stdout=f,
                               stderr=subprocess.STDOUT, timeout=timeout,
                               stdin=subprocess.DEVNULL, env={**os.environ, **(env or {})})
        except subprocess.TimeoutExpired:
            f.write(f"\n[timeout after {timeout}s]\n")
            return -1
        except OSError as e:
            f.write(f"\n[cannot run {argv[0]}: {e}]\n")
            return -1
    return r.returncode


def build_abutment(cell_gds: Path, top: str, neighbours: list,
                   boundary: tuple, out: Path) -> str:
    """Array for abutment DRC. Returns the array's top cell name `<top>__abut`.

    Cells are placed by their boundary boxes with no gap. Row 0 is: cell, cell
    mirrored in x, cell, then each neighbour once, each followed by cell again.
    Row 1 is the same sequence flipped vertically (top rails coincide with row 0);
    row 2 is row 0 again (its bottom rail meets row 1's)."""
    import klayout.db as kdb

    out_ly = kdb.Layout()
    out_ly.dbu = 0.001

    def bring(path, name):
        src = kdb.Layout()
        src.read(str(path))
        sc = src.cell(name)
        if sc is None:
            raise AdapterError(f"{path}: cell {name} not found")
        if abs(src.dbu - out_ly.dbu) > 1e-12:
            raise AdapterError(f"{path}: database unit {src.dbu} differs from {out_ly.dbu}")
        li = src.find_layer(*boundary)
        box = kdb.Region(sc.begin_shapes_rec(li)).bbox() if li is not None else kdb.Box()
        if box.empty():
            raise AdapterError(f"{path}: cell {name} has no boundary shape on layer {boundary[0]}/{boundary[1]}")
        dest = out_ly.create_cell(name)
        dest.copy_tree(sc)
        return dest, box

    own, own_box = bring(cell_gds, top)
    others = [bring(p, n) for p, n in neighbours]
    height = own_box.height()
    for dest, box in others:
        if box.height() != height:
            raise AdapterError(f"cell {dest.name} has height {box.height() * out_ly.dbu:g} um, "
                               f"{top} has {height * out_ly.dbu:g} um: cannot abut in a row")

    # (cell, box, mirror_x)
    seq = [(own, own_box, False), (own, own_box, True), (own, own_box, False)]
    for dest, box in others:
        seq += [(dest, box, False), (own, own_box, False)]

    arr = out_ly.create_cell(top + "__abut")

    def place(dest, box, mx, my, x, y):
        # mirror the boundary box, then move its lower-left corner to (x, y)
        rot = kdb.Trans(kdb.Trans.M0 if my else kdb.Trans.R0)          # flip vertically (y -> -y)
        if mx:
            rot = kdb.Trans(kdb.Trans.M90) * rot                        # mirror in x (x -> -x)
        moved = rot * box
        arr.insert(kdb.CellInstArray(dest.cell_index(), kdb.Trans(rot.rot, rot.is_mirror(),
                                                                  kdb.Vector(x - moved.left, y - moved.bottom))))

    for row in range(3):
        x = 0
        for dest, box, mx in seq:
            place(dest, box, mx, row % 2 == 1, x, row * height)
            x += box.width()

    opt = kdb.SaveLayoutOptions()
    opt.select_all_cells = False
    opt.add_cell(arr.cell_index())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_ly.write(str(out), opt)
    return arr.name
