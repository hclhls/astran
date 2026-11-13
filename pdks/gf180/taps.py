"""Library tap cells at the ends of every row, for DRC.

The gf180mcu 7t cells, ours included, are tapless: substrate and well taps come from separate tap
cells placed in the row, so a lone cell breaks the tap-distance rules (DF.13_MV / DF.14_MV). Checking
a layout therefore means checking it with the library's own tap cell (`filltie`) on both ends of each
row, exactly how the foundry cells themselves pass. Nothing is copied into the repository: the tap
cell is read from the installed PDK."""
from pathlib import Path

import klayout.db as kdb

from pdks.common import AdapterError
from pdks.gf180 import pdk

TIE = "gf180mcu_fd_sc_mcu7t5v0__filltie"


def _tie_layout() -> kdb.Layout:
    path = pdk.pdk_dir() / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds"
    ly = kdb.Layout()
    try:
        ly.read(str(path))
    except Exception as e:
        raise AdapterError(f"cannot read {path}: {e}")
    if ly.cell(TIE) is None:
        raise AdapterError(f"tap cell {TIE} not found in {path}")
    return ly


MAX_SEGMENT = 24000       # dbu (um/1000): longest run of cells between two taps; DF.13_MV/DF.14_MV allow 15 um to a tap


def _pieces(ly: kdb.Layout, top: kdb.Cell) -> list:
    """(instance, boundary box) of each cell instance of `top`; a cell without instances is one piece."""
    li = ly.find_layer(*pdk.LAYERS["prBoundary"])
    out = []
    if li is not None:
        for inst in top.each_inst():
            child_box = kdb.Region(inst.cell.begin_shapes_rec(li)).bbox()
            if not child_box.empty():
                out.append((inst.cell_inst, inst.cell_inst.trans * child_box))
        if not out:
            box = kdb.Region(top.begin_shapes_rec(li)).bbox()
            if not box.empty():
                out.append((kdb.CellInstArray(top.cell_index(), kdb.Trans()), box))
    if not out:
        raise AdapterError(f"cell {top.name}: no boundary (prBoundary {pdk.LAYERS['prBoundary']}) found")
    return out


def add_end_taps(gds_in: Path, top: str, gds_out: Path) -> str:
    """Write `gds_out` holding the cells of `top` in rows with a tap cell on both ends of each row and
    along it every MAX_SEGMENT. Returns the new top cell name."""
    src = kdb.Layout()
    src.read(str(gds_in))
    if src.cell(top) is None:
        raise AdapterError(f"{gds_in}: cell {top} not found")
    lib = _tie_layout()
    if abs(lib.dbu - src.dbu) > 1e-12:
        raise AdapterError(f"database unit of {gds_in} ({src.dbu}) differs from the library's ({lib.dbu})")
    tie_w = kdb.Region(lib.cell(TIE).begin_shapes_rec(lib.layer(*pdk.LAYERS["prBoundary"]))).bbox().width()

    src_top = src.cell(top)
    pieces = _pieces(src, src_top)
    nwell = src.find_layer(*pdk.LAYERS["nwell"])
    well = kdb.Region(src_top.begin_shapes_rec(nwell)) if nwell is not None else kdb.Region()
    rows = {}
    for inst, box in pieces:
        rows.setdefault((box.bottom, box.top), []).append((inst, box))

    out = kdb.Layout()
    out.dbu = src.dbu
    tie = out.create_cell(TIE)
    tie.copy_tree(lib.cell(TIE))
    wrapper = out.create_cell(top + "__taps")
    mapping = {}

    def child(cell):
        if cell.cell_index() not in mapping:
            c = out.create_cell(cell.name)
            c.copy_tree(cell)
            mapping[cell.cell_index()] = c
        return mapping[cell.cell_index()]

    for (bottom, top_y), items in sorted(rows.items()):
        items.sort(key=lambda it: it[1].left)
        left, right = items[0][1].left, items[-1][1].right
        # a flipped row has its nwell in the lower half; the tap cell flips with it
        rw = well & kdb.Region(kdb.Box(left, bottom, right, top_y))
        flipped = not rw.is_empty() and rw.bbox().center().y < (bottom + top_y) // 2

        def put_tie(x):
            t = kdb.Trans(kdb.Trans.M0, x, top_y) if flipped else kdb.Trans(x, bottom)
            wrapper.insert(kdb.CellInstArray(tie.cell_index(), t))

        put_tie(left - tie_w)
        shift, last_tap = 0, left
        for inst, box in items:
            if box.right + shift - last_tap > MAX_SEGMENT and box.left != left:
                put_tie(box.left + shift)
                shift += tie_w
                last_tap = box.left + shift
            moved = kdb.CellInstArray(child(src.cell(inst.cell_index)).cell_index(),
                                      kdb.Trans(inst.trans.rot, inst.trans.is_mirror(), inst.trans.disp + kdb.Vector(shift, 0)))
            wrapper.insert(moved)
        put_tie(right + shift)

    opt = kdb.SaveLayoutOptions()
    opt.select_all_cells = False
    opt.add_cell(wrapper.cell_index())
    Path(gds_out).parent.mkdir(parents=True, exist_ok=True)
    out.write(str(gds_out), opt)
    return wrapper.name
