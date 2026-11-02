#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""(banjo-nx's copy of sasrt-nx's tool of 2026-10-14; compile switch BANJO_GEN_SINGLE_FLOATS in app/CMakeLists.txt;
Banjo's double forms are the plain ones: its any-mode forms (rex::ppc::AddSingleAnyMode and the others) are left
alone. sasrt-nx's description:)
Single-precision arithmetic in float where its inputs are proven single (sasrt-nx, 2026-10-14; idea 2 of sa2-nx's
list).

The generator writes fadds / fsubs / fmuls / fdivs / fsqrts in double and rounds the result to single:
    X.f64 = double(float(A.f64 + B.f64));
When A and B hold values that are exactly representable as singles, computing in float gives the same bits: double
has more than 2 * 24 + 2 bits, so rounding the exact result to double first and then to single never differs from
rounding it to single once (for +, -, *, / and sqrt, in every rounding mode, also for results in the denormal range,
overflow and NaN payloads). This step writes those statements as
    X.f64 = REX_FADDS(A.f64, B.f64);        // double(float(A) + float(B))
and frsp of a proven single as a plain copy (REX_FRSP_SINGLE). The point is not the statement itself: where A and B are
C++ locals defined in the same function from a float (a load single, another single operation), the compiler drops
the float(double(t)) pairs and keeps the chain in single registers, without the fcvt pairs between operations
(sa2-nx counted 28 fcvt for 12 float operations in one function). Fused operations (fmadds and the others) stay as
they are (double fma, then one rounding). The statements stay where they are, so the flush mode at each one is the
same as before (the scalar FPU mode, no flush; the any-mode forms are left alone).

"Proven single", per function on the guest code (a forward must-analysis, meet = intersection): a register holds a
single after lfs / lfsx / lfsu / lfsux, the single operations (fadds fsubs fmuls fdivs fsqrts fres fmadds fmsubs
fnmadds fnmsubs frsp), fmr / fneg / fabs / fnabs of a single, and fsel of two singles. Nothing is single at the
function's entry, and every call, indirect call, trap or unknown statement forgets everything (lesson (e): a callee
may leave any value in any register).

Tested: sdk/tests/single_floats_test.cpp (the float forms against the double forms over special values, every
single-precision operand class and random pairs, in all four rounding modes); REX_SINGLE_FLOATS_OFF
(app/CMakeLists.txt BANJO_GEN_SINGLE_FLOATS=OFF) gives the double forms back.

  python tools/single_floats.py --gen app/generated [--check]
"""
import argparse
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leaf_dead_stores as lds  # noqa: E402  (the parser of the guest code and its C++ control flow)

SINGLE_RESULT = {'lfs', 'lfsx', 'lfsu', 'lfsux', 'fadds', 'fsubs', 'fmuls', 'fdivs', 'fsqrts', 'fres', 'fmadds',
                 'fmsubs', 'fnmadds', 'fnmsubs', 'frsp'}
COPIES = {'fmr', 'fneg', 'fabs', 'fnabs'}
FALL = (1 << 32) - 1
FREG = re.compile(r'^f(\d+)$')
BINARY = re.compile(r'^\t(\S+)\.f64 = double\(float\((\S+)\.f64 ([-+*/]) (\S+)\.f64\)\);$')
SQRT = re.compile(r'^\t(\S+)\.f64 = double\(float\(sqrt\((\S+)\.f64\)\)\);$')
FRSP = re.compile(r'^\t(\S+)\.f64 = double\(float\((\S+)\.f64\)\);$')
MACRO = {'+': 'REX_FADDS', '-': 'REX_FSUBS', '*': 'REX_FMULS', '/': 'REX_FDIVS'}
OPS = {'fadds': '+', 'fsubs': '-', 'fmuls': '*', 'fdivs': '/'}
WANTED = tuple('\t// %s ' % mn for mn in ('fadds', 'fsubs', 'fmuls', 'fdivs', 'fsqrts', 'frsp'))
UNMACRO = {v: k for k, v in MACRO.items()}
UNDO_BINARY = re.compile(r'^\t(\S+)\.f64 = (REX_FADDS|REX_FSUBS|REX_FMULS|REX_FDIVS)\((\S+)\.f64, (\S+)\.f64\);$', re.M)
UNDO_SQRT = re.compile(r'^\t(\S+)\.f64 = REX_FSQRTS\((\S+)\.f64\);$', re.M)
UNDO_FRSP = re.compile(r'^\t(\S+)\.f64 = REX_FRSP_SINGLE\((\S+)\.f64\);$', re.M)

MARKER = '// rexglue ports: single-precision arithmetic in float where its inputs are singles (tools/single_floats.py)'
END = '// (end of the macros of tools/single_floats.py)\n'
MACROS = MARKER + '''
#ifndef REX_FADDS
#if defined(REX_SINGLE_FLOATS_OFF)
#define REX_FADDS(a, b) double(float((a) + (b)))
#define REX_FSUBS(a, b) double(float((a) - (b)))
#define REX_FMULS(a, b) double(float((a) * (b)))
#define REX_FDIVS(a, b) double(float((a) / (b)))
#define REX_FSQRTS(a) double(float(sqrt(a)))
#define REX_FRSP_SINGLE(a) double(float(a))
#else
#define REX_FADDS(a, b) double(float(a) + float(b))
#define REX_FSUBS(a, b) double(float(a) - float(b))
#define REX_FMULS(a, b) double(float(a) * float(b))
#define REX_FDIVS(a, b) double(float(a) / float(b))
#define REX_FSQRTS(a) double(__builtin_sqrtf(float(a)))
#define REX_FRSP_SINGLE(a) (a)
#endif  // REX_SINGLE_FLOATS_OFF
#endif  // REX_FADDS
''' + END


def freg(op):
    m = FREG.match(op.strip())
    return int(m.group(1)) if m else None


def transfer(state, mn, ops, node):
    """The singles after one guest instruction."""
    if node.call or node.use == lds.ALL:
        return 0
    base = mn.rstrip('.')
    parts = [o.strip() for o in ops.split(',')] if ops.strip() else []
    dest = freg(parts[0]) if parts else None
    if dest is None:
        return state
    bit = 1 << dest
    if base in SINGLE_RESULT:
        return state | bit
    if base in COPIES and len(parts) >= 2 and freg(parts[1]) is not None:
        return (state | bit) if (state >> freg(parts[1])) & 1 else (state & ~bit)
    if base == 'fsel' and len(parts) == 4 and freg(parts[2]) is not None and freg(parts[3]) is not None:
        both = (state >> freg(parts[2])) & 1 and (state >> freg(parts[3])) & 1
        return (state | bit) if both else (state & ~bit)
    written, _ = lds.defuse(mn, ops)
    if written >> 32:
        return state & ~(written >> 32)
    return state


def analyse(lines):
    """[(node index, mn, ops, singles before)] for one function, and the C++ chunk line numbers per node."""
    nodes = lds.parse_function(lines)
    guest, chunk_lines = [], []
    for k, line in enumerate(lines):
        m = lds.COMMENT.match(line)
        if m:
            guest.append((m.group(1), m.group(2)))
            chunk_lines.append([])
        elif guest and not lds.LABEL.match(line):
            chunk_lines[-1].append(k)
    assert len(guest) == len(nodes), 'parser mismatch'
    n = len(nodes)
    state = [FALL] * n
    if n:
        state[0] = 0
    preds = [[] for _ in range(n)]
    for i, node in enumerate(nodes):
        for s in node.succ:
            preds[s].append(i)
    # Greatest fixed point from "everything single" (FALL) everywhere but the entry; a node's in-state is the
    # intersection of its predecessors' out-states. Code the entry cannot reach keeps FALL and never runs.
    work = list(range(n))
    queued = [True] * n
    while work:
        i = work.pop()
        queued[i] = False
        out = transfer(state[i], guest[i][0], guest[i][1], nodes[i])
        for s in nodes[i].succ:
            if s == 0:
                continue              # a loop back to the first instruction: the entry stays "nothing single"
            new = state[s] & out
            if new != state[s]:
                state[s] = new
                if not queued[s]:
                    queued[s] = True
                    work.append(s)
    return nodes, guest, chunk_lines, state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.gen, '*_recomp.*.cpp')))
    counts = collections.Counter()
    changed = 0
    already = 0
    for path in files:
        original = open(path, encoding='utf-8').read()
        already += sum(original.count(m + '(') for m in ('REX_FADDS', 'REX_FSUBS', 'REX_FMULS', 'REX_FDIVS',
                                                           'REX_FSQRTS', 'REX_FRSP_SINGLE'))
        # Every earlier rewrite back to the generator's form first, then the analysis of this run decides again (a
        # changed tree, e.g. a new hook or an inline call, can withdraw a proof).
        text = UNDO_BINARY.sub(lambda m: '\t%s.f64 = double(float(%s.f64 %s %s.f64));' % (
            m.group(1), m.group(3), UNMACRO[m.group(2)], m.group(4)), original)
        text = UNDO_SQRT.sub(r'\t\1.f64 = double(float(sqrt(\2.f64)));', text)
        text = UNDO_FRSP.sub(r'\t\1.f64 = double(float(\2.f64));', text)
        lines = text.split('\n')
        i = 0
        edits = {}
        while i < len(lines):
            m = lds.HEAD.match(lines[i])
            if not m:
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j] != '}':
                j += 1
            body = lines[i + 1:j]
            if not any(l.startswith(WANTED) for l in body):
                i = j + 1
                continue                  # no single operation to rewrite: no analysis (most functions)
            nodes, guest, chunk_lines, state = analyse(body)
            for k, (mn, ops) in enumerate(guest):
                base = mn.rstrip('.')
                if base not in OPS and base not in ('fsqrts', 'frsp'):
                    continue
                parts = [o.strip() for o in ops.split(',')]
                sources = [freg(p) for p in parts[1:]]
                counts[base + ' seen'] += 1
                if None in sources or not all((state[k] >> s) & 1 for s in sources):
                    continue
                for line_no in chunk_lines[k]:
                    line = body[line_no]
                    if base in OPS:
                        b = BINARY.match(line)
                        if b and b.group(3) == OPS[base]:
                            edits[i + 1 + line_no] = '\t%s.f64 = %s(%s.f64, %s.f64);' % (
                                b.group(1), MACRO[b.group(3)], b.group(2), b.group(4))
                            counts[base] += 1
                    elif base == 'fsqrts':
                        s = SQRT.match(line)
                        if s:
                            edits[i + 1 + line_no] = '\t%s.f64 = REX_FSQRTS(%s.f64);' % (s.group(1), s.group(2))
                            counts[base] += 1
                    else:
                        r = FRSP.match(line)
                        if r:
                            edits[i + 1 + line_no] = '\t%s.f64 = REX_FRSP_SINGLE(%s.f64);' % (r.group(1), r.group(2))
                            counts[base] += 1
            i = j + 1
        for k, new in edits.items():
            lines[k] = new
        new_text = '\n'.join(lines)
        if new_text != original:
            changed += 1
            if not a.check:
                open(path, 'w', encoding='utf-8', newline='\n').write(new_text)
    pchs = glob.glob(os.path.join(a.gen, '*_pch.h'))
    if len(pchs) != 1:
        sys.exit('ERROR (post-codegen patch): single_floats: no single *_pch.h in %s' % a.gen)
    text = open(pchs[0], encoding='utf-8').read()
    if MACROS not in text and not a.check:
        anchor = '#define REX_LOAD_U8(x)'
        if MARKER in text:
            start = text.index(MARKER)
            text = text[:start] + MACROS + text[text.index(END, start) + len(END):]
        elif anchor in text:
            text = text.replace(anchor, MACROS + anchor, 1)
        else:
            sys.exit('ERROR (post-codegen patch): single_floats: no REX_LOAD_U8 in %s' % pchs[0])
        open(pchs[0], 'w', encoding='utf-8', newline='\n').write(text)
    print('single_floats%s: of %d fadds, %d fsubs, %d fmuls, %d fdivs, %d fsqrts and %d frsp, %d, %d, %d, %d, %d and %d '
          'have proven single inputs and compute in float (%d files changed; %d were in that form before this run)' % (
              ' (check only)' if a.check else '', counts['fadds seen'], counts['fsubs seen'], counts['fmuls seen'],
              counts['fdivs seen'], counts['fsqrts seen'], counts['frsp seen'], counts['fadds'], counts['fsubs'],
              counts['fmuls'], counts['fdivs'], counts['fsqrts'], counts['frsp'], changed, already))


if __name__ == '__main__':
    main()
