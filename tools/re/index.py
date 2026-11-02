#!/usr/bin/env python3
"""Function index of the recompiled game (default.xex and AI2C.dll), built from app/generated/ and the module images.

Read-only: nothing in the build is touched. REA cannot open Xbox 360 PowerPC images (COFF machine 0x01f2), so the
recompiled C++ (every line keeps the PowerPC instruction as a comment) is the readable form of the game's code. This
tool turns it into something searchable:

  per function: address, instruction count, FP / vector / indirect-call counts, strings it references (resolved from
  the module image through lis/addi pairs), callees (direct and imports), callers, tags from the strings.

  python3 tools/re/index.py build                 # writes out/re/index.json (out/ is git-ignored)
  python3 tools/re/index.py find STRING           # functions that reference a string containing STRING (case-insensitive)
  python3 tools/re/index.py func 825CFAE8         # one function: size, strings, callees, callers
  python3 tools/re/index.py callers 825CFAE8 [-d 2]   # callers, transitively up to depth d
  python3 tools/re/index.py callees 825CFAE8 [-d 2]
  python3 tools/re/index.py tag Vegetation        # functions with a tag
  python3 tools/re/index.py hot FILE              # FILE: lines of "ADDR weight" (e.g. from a stack profile): index rows, heaviest first
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, 'app', 'generated')
OUT = os.path.join(ROOT, 'out', 're')
INDEX = os.path.join(OUT, 'index.json')
MODULES = {
    'default': (os.path.join(ROOT, 'out', 'default_image.bin'), os.path.join(GEN, 'default')),
    'ai2c': (os.path.join(ROOT, 'out', 'default_image.AI2C.bin'), os.path.join(GEN, 'ai2c')),
}

TAGS = {  # substring (case-insensitive) of a referenced string -> tag
    'vegetation': 'vegetation', 'fadedist': 'fade-distance', 'visib': 'visibility', 'cull': 'culling',
    'lod': 'lod', 'billboard': 'billboard', 'shadow': 'shadow', 'camera': 'camera', 'particle': 'particles',
    'anim': 'animation', 'skelet': 'skeleton', 'collision': 'collision', 'physic': 'physics',
    'ai_': 'ai', 'trigger': 'trigger', 'sound': 'sound', 'audio': 'sound', 'texture': 'texture',
    'shader': 'shader', 'render': 'render', 'draw': 'draw', 'save': 'save', 'load': 'loading',
}

FUNC = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]{8})\)')
CALL = re.compile(r'(?<![\w])(__imp__)?(sub_[0-9A-F]{8})\(ctx, base\)')
IMPORT = re.compile(r'(?<![\w])__imp__([A-Za-z_]\w*)\(ctx, base\)')
INSN = re.compile(r'^\t// ([a-z][a-z0-9_.+-]*)\b ?(.*)$')
LIS = re.compile(r'^(r\d+),\s*(-?\d+)')
ADDI = re.compile(r'^(r\d+),\s*(r\d+),\s*(-?\d+)')
FPOPS = ('lfs', 'lfd', 'stfs', 'stfd', 'fadd', 'fsub', 'fmul', 'fdiv', 'fmadd', 'fmsub', 'fnmsub', 'fnmadd', 'fsel',
         'fcmp', 'fctiwz', 'fcfid', 'frsp', 'fabs', 'fneg', 'fmr', 'fsqrt', 'fres', 'frsqrte')


class Image:
    """A module's PE image: section table maps a virtual address to the file bytes."""

    def __init__(self, path):
        self.data = open(path, 'rb').read() if os.path.exists(path) else b''
        self.sections = []
        d = self.data
        if len(d) < 0x100:
            return
        pe = struct.unpack_from('<I', d, 0x3C)[0]
        n = struct.unpack_from('<H', d, pe + 6)[0]
        opt = pe + 24
        self.base = struct.unpack_from('<I', d, opt + 28)[0]
        so = opt + struct.unpack_from('<H', d, pe + 20)[0]
        for i in range(n):
            o = so + 40 * i
            vsize, va, rsize, raw = struct.unpack_from('<IIII', d, o + 8)
            self.sections.append((self.base + va, max(vsize, 0), raw, rsize))

    def read_string(self, addr, limit=160):
        for va, vsize, raw, rsize in self.sections:
            if va <= addr < va + min(vsize, rsize):
                off = raw + (addr - va)
                end = self.data.find(b'\0', off, off + limit)
                if end < 0:
                    return None
                s = self.data[off:end]
                if len(s) >= 4 and all(32 <= c < 127 or c in (9, 10) for c in s):
                    return s.decode('ascii').replace('\n', '\\n').replace('\t', ' ')
                return None
        return None


def scan_module(name, image_path, gen_dir):
    image = Image(image_path)
    funcs = {}
    files = sorted(f for f in os.listdir(gen_dir) if re.match(r'\w+_recomp\.\d+\.cpp$', f))
    for fname in files:
        cur = None
        regs = {}
        with open(os.path.join(gen_dir, fname), encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if cur is None:
                    m = FUNC.match(line)
                    if m:
                        addr = m.group(1)[4:]
                        cur = funcs.setdefault(addr, {
                            'addr': addr, 'module': name, 'file': fname, 'insns': 0, 'fp': 0, 'vec': 0,
                            'indirect': 0, 'loads': 0, 'stores': 0, 'strings': [], 'calls': [], 'imports': []})
                        regs = {}
                    continue
                if line.startswith('}'):
                    cur = None
                    continue
                m = INSN.match(line)
                if m:
                    op, args = m.group(1), m.group(2)
                    cur['insns'] += 1
                    if op.startswith(FPOPS):
                        cur['fp'] += 1
                    elif op.startswith('v') and op not in ('vsel',):
                        cur['vec'] += 1
                    if op in ('bctrl', 'bctr'):
                        cur['indirect'] += 1
                    if op[0] == 'l' and op not in ('li', 'lis'):
                        cur['loads'] += 1
                    elif op.startswith('st'):
                        cur['stores'] += 1
                    if op == 'lis':
                        a = LIS.match(args)
                        if a:
                            regs[a.group(1)] = (int(a.group(2)) << 16) & 0xFFFFFFFF
                    elif op == 'addi':
                        a = ADDI.match(args)
                        if a:
                            rd, rs, imm = a.group(1), a.group(2), int(a.group(3))
                            if rs in regs:
                                val = (regs[rs] + imm) & 0xFFFFFFFF
                                regs[rd] = val
                                s = image.read_string(val)
                                if s and s not in cur['strings']:
                                    cur['strings'].append(s)
                            else:
                                regs.pop(rd, None)
                    continue
                for m in CALL.finditer(line):
                    t = m.group(2)[4:]
                    if t not in cur['calls']:
                        cur['calls'].append(t)
                for m in IMPORT.finditer(line):
                    if not m.group(1).startswith('sub_') and m.group(1) not in cur['imports']:
                        cur['imports'].append(m.group(1))
    return funcs


def build():
    index = {}
    for name, (img, gen) in MODULES.items():
        if not os.path.isdir(gen):
            sys.exit('no generated tree: %s (run tools/codegen.sh)' % gen)
        funcs = scan_module(name, img, gen)
        print('%s: %d functions' % (name, len(funcs)))
        index.update({f: v for f, v in funcs.items()})
    callers = collections.defaultdict(list)
    for a, f in index.items():
        for c in f['calls']:
            callers[c].append(a)
    for a, f in index.items():
        f['callers'] = sorted(callers.get(a, []))
        tags = set()
        text = ' '.join(f['strings']).lower() + ' ' + ' '.join(f['imports']).lower()
        for key, tag in TAGS.items():
            if key in text:
                tags.add(tag)
        f['tags'] = sorted(tags)
    os.makedirs(OUT, exist_ok=True)
    with open(INDEX, 'w') as fh:
        json.dump(index, fh)
    with_str = sum(1 for f in index.values() if f['strings'])
    print('%d functions, %d with strings -> %s' % (len(index), with_str, os.path.relpath(INDEX, ROOT)))


def load():
    if not os.path.exists(INDEX):
        sys.exit('no index: run  python3 tools/re/index.py build')
    return json.load(open(INDEX))


def row(f):
    return '%s %-7s %5d insn  fp %-4d vec %-4d ind %-3d calls %-3d callers %-3d %s' % (
        f['addr'], f['module'], f['insns'], f['fp'], f['vec'], f['indirect'], len(f['calls']), len(f['callers']),
        ','.join(f['tags']))


def walk(index, start, key, depth):
    seen = {start}
    level = [start]
    for d in range(depth):
        nxt = []
        for a in level:
            for b in index.get(a, {}).get(key, []):
                if b not in seen:
                    seen.add(b)
                    nxt.append(b)
                    f = index.get(b)
                    print('  ' * d + (row(f) if f else b + ' (not in the index)'))
        level = nxt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['build', 'find', 'func', 'callers', 'callees', 'tag', 'hot'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('-d', '--depth', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'build':
        return build()
    index = load()
    arg = (a.arg or '').upper().replace('SUB_', '') if a.cmd in ('func', 'callers', 'callees') else a.arg
    if a.cmd == 'find':
        needle = a.arg.lower()
        for f in sorted(index.values(), key=lambda f: f['addr']):
            hits = [s for s in f['strings'] if needle in s.lower()]
            if hits:
                print(row(f))
                for s in hits[:3]:
                    print('    "%s"' % s[:140])
    elif a.cmd == 'func':
        f = index.get(arg)
        if not f:
            sys.exit('not in the index: ' + arg)
        print(row(f))
        print('file:', f['file'])
        for s in f['strings']:
            print('  string: "%s"' % s[:160])
        print('  imports:', ', '.join(f['imports']) or '-')
        print('  callees:', ' '.join(f['calls']) or '-')
        print('  callers:', ' '.join(f['callers']) or '-')
    elif a.cmd == 'callers':
        walk(index, arg, 'callers', a.depth)
    elif a.cmd == 'callees':
        walk(index, arg, 'calls', a.depth)
    elif a.cmd == 'tag':
        for f in sorted(index.values(), key=lambda f: -f['insns']):
            if a.arg in f['tags']:
                print(row(f))
    elif a.cmd == 'hot':
        weights = []
        for line in open(a.arg):
            p = line.split()
            if len(p) >= 2:
                weights.append((float(p[1]), p[0].upper().replace('SUB_', '')))
        for w, addr in sorted(weights, reverse=True):
            f = index.get(addr)
            print('%8.2f %s' % (w, row(f) if f else addr + ' (not in the index)'))


if __name__ == '__main__':
    main()
