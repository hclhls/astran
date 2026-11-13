"""Split-gate reduction of an extracted netlist, applied before LVS.

When a transistor of a series stack is too wide for its row, Astran folds the whole stack into parallel
copies, each with its own internal nets. netgen merges parallel devices but not parallel stacks, so such a
layout would not match the library netlist, which has the one stack. This merges them back: series chains
between the same two nets with the same gates, models, bulks and lengths in the same order become one
chain with the widths added position by position (what commercial LVS calls reducing split gates).
A netlist without folded stacks is returned unchanged."""
import re

_DEV = re.compile(r"^[XM]\S*\s", re.I)
_W = re.compile(r"^w=([0-9.eE+-]+)u$", re.I)


def reduce_split_gates(text: str) -> tuple:
    """(netlist text, number of stack copies merged away). Works on a single .subckt of 4-terminal MOS lines
    `X d g s b model ... w=<n>u l=<..>`; anything it cannot read leaves the netlist untouched."""
    lines = text.splitlines()
    ports, devs, where = set(), [], []
    for i, line in enumerate(lines):
        tok = line.split()
        if tok and tok[0].lower() == ".subckt":
            if ports:
                return text, 0                       # more than one subcircuit: not ours to rewrite
            ports = set(tok[2:])
        elif _DEV.match(line):
            params = dict(t.split("=", 1) for t in tok[6:] if "=" in t)
            w = _W.match("w=" + params.get("w", ""))
            if len(tok) < 6 or not w or "l" not in params:
                return text, 0
            devs.append({"d": tok[1], "g": tok[2], "s": tok[3], "b": tok[4], "model": tok[5],
                         "w": float(w.group(1)), "l": params["l"].lower()})
            where.append(i)
    # internal net of a stack: exactly two source/drain terminals of two devices, nothing else
    ends, other = {}, set()
    for i, d in enumerate(devs):
        ends.setdefault(d["d"], []).append(i)
        ends.setdefault(d["s"], []).append(i)
        other.update((d["g"], d["b"]))
    internal = {n for n, u in ends.items() if len(u) == 2 and u[0] != u[1] and n not in ports and n not in other}
    seen, groups = set(), {}
    for i in range(len(devs)):
        if i in seen:
            continue
        chain, tips = [i], [devs[i]["d"], devs[i]["s"]]
        for side in (0, 1):
            while tips[side] in internal:
                nxt = [k for k in ends[tips[side]] if k not in chain]
                if not nxt:
                    break
                e = devs[nxt[0]]
                tips[side] = e["s"] if e["d"] == tips[side] else e["d"]
                chain = [nxt[0]] + chain if side == 0 else chain + [nxt[0]]
        seen.update(chain)
        if len(chain) < 2:
            continue
        sig = [(devs[k]["g"], devs[k]["model"], devs[k]["b"], devs[k]["l"]) for k in chain]
        if (tips[0], sig) > (tips[1], sig[::-1]):                      # one orientation per chain
            tips, chain, sig = tips[::-1], chain[::-1], sig[::-1]
        groups.setdefault((tuple(tips), tuple(sig)), []).append(chain)
    merged, drop = 0, set()
    for chains in groups.values():
        keep = chains[0]
        for extra in chains[1:]:
            merged += 1
            for a, b in zip(keep, extra):
                devs[a]["w"] += devs[b]["w"]
                drop.add(b)
    if not merged:
        return text, 0
    out = []
    for i, line in enumerate(lines):
        if i in where:
            k = where.index(i)
            if k in drop:
                continue
            d = devs[k]
            # area and perimeter values describe one finger and are not compared; they are left out
            line = f"{line.split()[0]} {d['d']} {d['g']} {d['s']} {d['b']} {d['model']} w={d['w']:g}u l={d['l']}"
        out.append(line)
    return "\n".join(out) + "\n", merged
