#!/usr/bin/env python3
"""One structural gap pass for a module (SOL-CODE-1), naruto-nx's take on sa2-nx's gap_fixpoint.py.

  python3 -I tools/gap_pass.py MODULE SCRATCH_DIR      MODULE: default | ai2c

Needs: an up-to-date generated tree (rexglue codegen app/naruto_manifest.toml with REXGLUE_DUMP_IMAGE=out/default_image.bin).
Steps: find_gaps.py -> gaps >= 8 bytes holding code (blr / b) and targets of data words pointing into a gap
(pointer_scan.py) not examined before (SCRATCH_DIR/examined.txt) -> scratch codegen with them declared, adding tail
targets the validation reports -> gap_classify.py tier 1 + gap_fixpoint.py's filters -> appended to
app/gap-seeds.toml (default) or app/ai2c-gap-seeds.toml (ai2c). Prints how many were accepted; 0 = fixpoint.
"""
import os, re, struct, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
MOD = {
    "default": dict(gen="app/generated/default", image="out/default_image.bin", base=0x82000000,
                    code=("820C0000", "826D0000"), seeds="app/gap-seeds.toml", key='includes = ["analysis-seeds.toml"'),
    "ai2c": dict(gen="app/generated/ai2c", image="out/default_image.AI2C.bin", base=0x88000000,
                 code=("88040000", "883A1000"), seeds="app/ai2c-gap-seeds.toml", key='includes = ["ai2c-seeds.toml"'),
}


def run(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def main():
    name, sc = sys.argv[1], os.path.abspath(sys.argv[2])
    m = MOD[name]
    os.makedirs(sc, exist_ok=True)
    os.chdir(ROOT)
    toml = os.path.join(sc, "candidates.toml")
    run(sys.executable, "-I", f"{TOOLS}/find_gaps.py", "--gen", m["gen"], "--report", os.path.join(sc, "report.txt"),
        "--toml", toml)
    ptr = run(sys.executable, "-I", f"{TOOLS}/pointer_scan.py", m["image"], toml, *m["code"], f"{m['base']:08X}").stdout
    img = open(m["image"], "rb").read()
    exf = os.path.join(sc, "examined.txt")
    seen = set(open(exf).read().split()) if os.path.exists(exf) else set()
    sel, kind = {}, {}
    for l in open(toml):
        g = re.match(r'"(0x[0-9A-F]+)" = \{ \}\s*#\s*(\d+) bytes', l)
        if not g:
            continue
        a, n = int(g.group(1), 16), int(g.group(2))
        w = [struct.unpack_from(">I", img, a - m["base"] + i)[0] for i in range(0, n, 4)]
        if n >= 8 and (0x4E800020 in w or any(x >> 26 == 18 for x in w)):
            sel[a], kind[a] = n, "gap"
    for l in ptr.splitlines():
        g = re.match(r"0x([0-9A-F]+) gap=0x[0-9A-F]+\+(\d+) size=(\d+)", l)
        if g:
            v = int(g.group(1), 16)
            sel[v], kind[v] = int(g.group(3)) - int(g.group(2)), "ptr"
    sel = {a: n for a, n in sel.items() if f"0x{a:08X}" not in seen}
    if not sel:
        print(f"{name}: no new candidates (fixpoint)")
        return
    man = open("app/naruto_manifest.toml").read().replace('"../game', f'"{ROOT}/game')
    man = man.replace('includes = ["', f'includes = ["{ROOT}/app/').replace('", "', f'", "{ROOT}/app/')
    man = re.sub(r'(out_directory_path = ")', rf'\1{sc}/', man)
    extra = os.path.join(sc, "extra.toml")
    m_key = m["key"].replace('includes = ["', f'includes = ["{ROOT}/app/')
    assert m_key in man, m_key
    man = man.replace(m_key, f'includes = ["{extra}", "{ROOT}/app/' + m["key"].split('["', 1)[1])
    open(os.path.join(sc, "manifest.toml"), "w").write(man)
    rexglue = os.environ.get("REXGLUE", f"{ROOT}/sdk/out/linux-amd64/Release/rexglue")
    for _ in range(6):
        open(extra, "w").write("[functions]\n" + "".join(f'"0x{a:08X}" = {{ }}\n' for a in sorted(sel)))
        r = run(rexglue, "codegen", "manifest.toml", cwd=sc)
        log = r.stdout + r.stderr
        open(os.path.join(sc, "codegen.log"), "w").write(log)
        tails = set(re.findall(r"(0x[0-9A-F]{8}) from 0x[0-9A-F]{8}: b .*target not in any function", log))
        if not tails:
            break
        for t in tails:
            sel[int(t, 16)], kind[int(t, 16)] = 8, "tail"
    if r.returncode:
        sys.exit(f"scratch codegen failed, see {sc}/codegen.log")
    open(os.path.join(sc, "selected.txt"), "w").write("".join(f"0x{a:08X} {n}\n" for a, n in sorted(sel.items())))
    acc = os.path.join(sc, "acc.txt")
    run(sys.executable, "-I", f"{TOOLS}/gap_classify.py", os.path.join(sc, m["gen"].replace("app/", "", 1)),
        os.path.join(sc, "selected.txt"), os.path.join(sc, "codegen.log"), acc)
    ns = {}
    exec(compile(open(f"{TOOLS}/gap_classify.py").read().split("if __name__")[0], "gc", "exec"), ns)
    out = []
    for l in open(acc):
        a, s, rest = l.split(" ", 2)
        ins = [i.strip() for i in rest.lstrip("| ").strip().split(" ; ")]
        ops = [i.split()[0] for i in ins]
        if (any(re.search(r"\br1\b", i) for i in ins) or any(o in ("mtlr", "mflr", "ld", "std", "stwu", "lfd", "stfd")
                                                            for o in ops) or ns["reads_undefined_at_entry"](ins)):
            continue
        out.append(f'"{a}" = {{ }}  # {kind[int(a, 16)]}, {s} bytes: {" ; ".join(ins)[:90]}\n')
    with open(exf, "a") as f:
        f.write("".join(f"0x{a:08X}\n" for a in sel))
    seeds = m["seeds"]
    if out:
        new = not os.path.exists(seeds)
        with open(seeds, "a") as f:
            if new:
                f.write(f"# Structural gap scan of {name} (SOL-CODE-1): tools/gap_pass.py. Each line: the generated code.\n[functions]\n")
            f.write(f"# pass ({len(sel)} candidates, {len(out)} accepted)\n" + "".join(out))
    print(f"{name}: {len(sel)} candidates, {len(out)} accepted -> {seeds}")


main()
