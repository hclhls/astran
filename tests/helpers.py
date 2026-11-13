"""Shared test helpers (importable as `helpers` because tests/ is on sys.path)."""
from pathlib import Path

import klayout.db as kdb


def load(path) -> kdb.Layout:
    ly = kdb.Layout()
    ly.read(str(path))
    return ly


def region(ly: kdb.Layout, pair, cell=None) -> kdb.Region:
    """Merged region of one layer/datatype over the whole hierarchy of `cell` (default top)."""
    cell = cell or ly.top_cell()
    idx = ly.find_layer(*pair)
    if idx is None:
        return kdb.Region()
    return kdb.Region(cell.begin_shapes_rec(idx)).merged()


def same(a: kdb.Region, b: kdb.Region) -> bool:
    return (a ^ b).is_empty()


def make_gds(tmp_path, shapes: dict, cellbox, name: str = "X_1", filename: str = "x.gds",
             cellbox_pair=(235, 4)) -> Path:
    """Flat GDS with one top cell. shapes: {(layer, datatype): [(x1, y1, x2, y2) in um]}."""
    ly = kdb.Layout()
    ly.dbu = 0.001
    top = ly.create_cell(name)
    todo = dict(shapes)
    todo[cellbox_pair] = [cellbox]
    for pair, boxes in todo.items():
        li = ly.layer(*pair)
        for b in boxes:
            top.shapes(li).insert(kdb.DBox(*b))
    path = Path(tmp_path) / filename
    ly.write(str(path))
    return path
