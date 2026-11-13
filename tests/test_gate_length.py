import subprocess

import klayout.db as kdb

from pdks.sky130 import adapter


def test_poly_width_follows_each_transistors_length(astran_cli, tmp_path):
    """Astran must draw each gate as long as its own transistor's L (gf180 needs N=0.6, P=0.5)."""
    sp = tmp_path / "ln.sp"
    sp.write_text(".subckt LN A Y VPWR VGND\n"
                  "M0 Y A VGND VGND NMOS L=0.6U W=0.82U\n"
                  "M1 Y A VPWR VPWR PMOS L=0.5U W=1.13U\n"
                  ".ends\n")
    gds = tmp_path / "raw.gds"
    (tmp_path / "cell.run").write_text(adapter.astran_script("LN", sp, gds))
    r = subprocess.run([str(astran_cli), "cell.run"], cwd=tmp_path, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.top_cell()
    reg = lambda l, d: kdb.Region(top.begin_shapes_rec(ly.layer(l, d)))
    gates = reg(66, 20) & reg(65, 20)
    ngate = (gates & reg(93, 44)).merged()
    pgate = (gates & reg(94, 20)).merged()
    assert ngate.count() >= 1 and pgate.count() >= 1       # a wide device may be folded
    assert {q.bbox().width() for q in ngate.each()} == {round(0.6 / ly.dbu)}
    assert {q.bbox().width() for q in pgate.each()} == {round(0.5 / ly.dbu)}
