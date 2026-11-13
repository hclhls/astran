from pdks.gf180.splitgate import reduce_split_gates

# oai21 as magic extracts it once Astran has folded the A2-A1 PMOS stack into two copies
FOLDED = """.subckt c A1 A2 B ZN VDD VNW VPW VSS
X0 VDD A2 a_1# VNW pfet_06v0 ad=0.2p pd=2.1u as=0.1p ps=1.0u w=0.61u l=0.5u
X1 ZN A1 a_n# VPW nfet_06v0 w=0.82u l=0.6u
X2 a_1# A1 ZN VNW pfet_06v0 w=0.61u l=0.5u
X3 ZN B VDD VNW pfet_06v0 w=0.565u l=0.5u
X4 a_n# A2 ZN VPW nfet_06v0 w=0.82u l=0.6u
X5 VDD B ZN VNW pfet_06v0 w=0.565u l=0.5u
X6 a_2# A2 VDD VNW pfet_06v0 w=0.61u l=0.5u
X7 a_n# B VSS VPW nfet_06v0 w=0.82u l=0.6u
X8 ZN A1 a_2# VNW pfet_06v0 w=0.61u l=0.5u
.ends
"""


def devices(text):
    return sorted((t[5], t[2], t[-2], frozenset((t[1], t[3]))) for t in (l.split() for l in text.splitlines()) if t[0][0] == "X")


def test_folded_stack_copies_are_merged_with_summed_widths():
    out, merged = reduce_split_gates(FOLDED)
    assert merged == 1
    p = [d for d in devices(out) if d[0] == "pfet_06v0" and d[1] in ("A1", "A2")]
    assert [(d[1], d[2]) for d in p] == [("A1", "w=1.22u"), ("A2", "w=1.22u")]
    assert len(devices(out)) == 7                       # the two B fingers are parallel devices: netgen's job
    assert frozenset(p[0][3] & p[1][3]) and len(p[0][3] & p[1][3]) == 1      # still one stack sharing one net


def test_nothing_to_merge_returns_the_text_unchanged():
    plain = "\n".join(l for l in FOLDED.splitlines() if not l.startswith(("X6", "X8"))) + "\n"
    assert reduce_split_gates(plain) == (plain, 0)


def test_stacks_that_differ_are_not_merged():
    for old, new in (("X8 ZN A1 a_2#", "X8 ZN B a_2#"),               # other gate
                     ("X6 a_2# A2 VDD", "X6 a_2# A2 VSS"),            # other end net
                     ("X8 ZN A1 a_2# VNW pfet_06v0 w=0.61u l=0.5u", "X8 ZN A1 a_2# VNW pfet_06v0 w=0.61u l=0.6u")):
        text = FOLDED.replace(old, new)
        assert text != FOLDED and reduce_split_gates(text) == (text, 0), old


def test_a_net_with_a_third_connection_is_not_internal():
    text = FOLDED.replace("X3 ZN B VDD", "X3 a_1# B VDD")            # a_1# now has three terminals
    assert reduce_split_gates(text) == (text, 0)
    assert reduce_split_gates(FOLDED.replace(".subckt c A1", ".subckt c a_1# A1"))[1] == 0     # or it is a port


def test_gate_order_must_agree():
    text = FOLDED.replace("X6 a_2# A2 VDD", "X6 a_2# A1 VDD").replace("X8 ZN A1 a_2#", "X8 ZN A2 a_2#")
    assert reduce_split_gates(text) == (text, 0)
