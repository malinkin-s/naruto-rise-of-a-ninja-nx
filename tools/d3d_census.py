#!/usr/bin/env python3
"""Call graph of a code range of the generated C++ (the game's Direct3D library), for the SOL-REND-1 census.

  python3 -I tools/d3d_census.py [--gen app/generated/default] [--lo 82128000] [--hi 82148000] [--fn 8212EF28 ...]

For each function: instructions, callees (bl), callers (from the whole module), kernel imports it calls, whether it
touches GPU MMIO (lis rX,0x7FC8), and the device offsets it reads/writes most (displacements on r31/r3).
"""
import argparse, collections, glob, os, re

ap = argparse.ArgumentParser()
ap.add_argument("--gen", default="app/generated/default")
ap.add_argument("--lo", default="82128000")
ap.add_argument("--hi", default="82148000")
ap.add_argument("--fn", nargs="*", default=[])
a = ap.parse_args()
lo, hi = int(a.lo, 16), int(a.hi, 16)
funcs = {}
cur = None
for path in sorted(glob.glob(os.path.join(a.gen, "*_recomp.*.cpp"))):
    for line in open(path, errors="replace"):
        m = re.match(r"DEFINE_REX_FUNC\(sub_([0-9A-F]+)\)", line)
        if m:
            cur = int(m.group(1), 16)
            funcs[cur] = dict(n=0, calls=[], imps=set(), mmio=False, offs=collections.Counter())
            continue
        if cur is None:
            continue
        if line.startswith("}"):
            cur = None
            continue
        f = funcs[cur]
        if line.startswith("\t// "):
            f["n"] += 1
            ins = line[4:].strip()
            m = re.match(r"bl 0x([0-9a-f]+)", ins)
            if m:
                f["calls"].append(int(m.group(1), 16))
            if re.match(r"lis r\d+,32712$", ins):
                f["mmio"] = True
            m = re.match(r"(l|st)[a-z]*\s+r\d+,(\d+)\(r(31|3)\)$", ins)
            if m and int(m.group(2)) >= 1024:
                f["offs"][int(m.group(2))] += 1
        m = re.search(r"__imp__([A-Za-z0-9_]+)\(", line)
        if m:
            f["imps"].add(m.group(1))
callers = collections.defaultdict(set)
for fa, f in funcs.items():
    for c in f["calls"]:
        callers[c].add(fa)
sel = [int(x, 16) for x in a.fn] or [x for x in sorted(funcs) if lo <= x < hi]
for fa in sel:
    f = funcs.get(fa)
    if not f:
        print(f"{fa:08X}: not a function"); continue
    cs = sorted(set(f["calls"]))
    cr = sorted(callers[fa])
    out = [f"{fa:08X} n={f['n']:4d} callers={len(cr):3d}"]
    if f["mmio"]: out.append("MMIO")
    if f["imps"]: out.append("imp=" + ",".join(sorted(f["imps"])))
    out.append("calls=" + " ".join(f"{c:08X}" for c in cs[:8]) + (" ..." if len(cs) > 8 else ""))
    if len(sel) < 30:
        out.append("from=" + " ".join(f"{c:08X}" for c in cr[:10]) + (" ..." if len(cr) > 10 else ""))
        out.append("offs=" + " ".join(f"{o}x{n}" for o, n in f["offs"].most_common(8)))
    print("  ".join(out))
