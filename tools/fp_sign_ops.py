#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""fneg / fabs / fnabs as float operations (from sasrt-nx's tool of 2026-10-14, idea 7 of sa2-nx's list; banjo-nx's
copy).
The generator writes the three guest sign instructions as integer operations on the register's bits:
    fneg   d.u64 = s.u64 ^ 0x8000000000000000;      ->   REX_FNEG(d, s);    d.f64 = -s.f64
    fabs   d.u64 = s.u64 & ~0x8000000000000000;     ->   REX_FABS(d, s);    d.f64 = __builtin_fabs(s.f64)
    fnabs  d.u64 = s.u64 | 0x8000000000000000;      ->   REX_FNABS(d, s);   d.f64 = -__builtin_fabs(s.f64)
On AArch64 the integer form moves the value out of the float register and back (fmov x, d; eor; fmov d, x); the float
form is one FNEG / FABS. Both only flip or clear the sign bit: no NaN is quieted, no exception raised, and the
flush-to-zero mode does not apply to them. Bit-identical for every input; sdk/tests/fp_sign_ops_test.cpp checks it
over special values and random patterns, flush mode off and on, in all four rounding modes.
What changes is what the compiler may do around them: a float negation can be folded into the arithmetic next to it
(-(a * b) as (-a) * b). Those folds are exact when the rounding is symmetric (to nearest, toward zero), not in
round-up / round-down mode, and the compiler assumes round to nearest. So this step is taken only while the game
never writes round-up or round-down: banjo_diag_runtime_census's "[census] FPSCR rounding mode" line (2026-10-14).
In Banjo (2026-10-14): about 1,400 sign statements under their guest instruction.
REX_FP_SIGN_INTEGER (compile time) gives the integer forms back.
  python tools/fp_sign_ops.py --gen app/generated [--check]
"""
import argparse
import os
import re
import sys

STMT = re.compile(r'^\t([A-Za-z_][\w.]*)\.u64 = ([A-Za-z_][\w.]*)\.u64 (\^|&|\|) (~?)0x8000000000000000;$', re.M)
MACRO = {('^', ''): 'REX_FNEG', ('&', '~'): 'REX_FABS', ('|', ''): 'REX_FNABS'}
MARKER = '// rexglue ports: fneg / fabs / fnabs as float operations (tools/fp_sign_ops.py)'
END = '// (end of the macros of tools/fp_sign_ops.py)\n'
MACROS = MARKER + '''
#ifndef REX_FNEG
#if defined(REX_FP_SIGN_INTEGER)
#define REX_FNEG(d, s) ((d).u64 = (s).u64 ^ 0x8000000000000000ull)
#define REX_FABS(d, s) ((d).u64 = (s).u64 & ~0x8000000000000000ull)
#define REX_FNABS(d, s) ((d).u64 = (s).u64 | 0x8000000000000000ull)
#else
#define REX_FNEG(d, s) ((d).f64 = -(s).f64)
#define REX_FABS(d, s) ((d).f64 = __builtin_fabs((s).f64))
#define REX_FNABS(d, s) ((d).f64 = -__builtin_fabs((s).f64))
#endif  // REX_FP_SIGN_INTEGER
#endif  // REX_FNEG
''' + END
GUEST = {'REX_FNEG': 'fneg', 'REX_FABS': 'fabs', 'REX_FNABS': 'fnabs'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True, help='generated folder (*_recomp.N.cpp and *_pch.h)')
    ap.add_argument('--check', action='store_true', help='count only, write nothing')
    a = ap.parse_args()
    files = sorted(f for f in os.listdir(a.gen) if re.match(r'.*_recomp\.\d+\.cpp$', f))
    pchs = [f for f in os.listdir(a.gen) if f.endswith('_pch.h')]
    if not files or len(pchs) != 1:
        sys.exit('ERROR (post-codegen patch): fp_sign_ops: no *_recomp.N.cpp or no single *_pch.h in %s' % a.gen)
    counts = {name: 0 for name in GUEST}
    already = changed = unexpected = 0

    for name in files:
        path = os.path.join(a.gen, name)
        text = open(path, encoding='utf-8').read()
        already += sum(text.count(m + '(') for m in GUEST)
        lines = text.split('\n')
        out = []
        for i, line in enumerate(lines):
            m = STMT.match(line)
            if m:
                macro = MACRO.get((m.group(3), m.group(4)))
                # Only under the guest instruction's own comment line: the mask has other uses (rotates).
                if macro and i and lines[i - 1].strip().split(' ')[:2][-1:] == [GUEST[macro]]:
                    out.append('\t%s(%s, %s);' % (macro, m.group(1), m.group(2)))
                    counts[macro] += 1
                    continue
                unexpected += 1
            out.append(line)
        new = '\n'.join(out)
        if new != text:
            changed += 1
            if not a.check:
                open(path, 'w', encoding='utf-8', newline='\n').write(new)
    pch = os.path.join(a.gen, pchs[0])
    text = open(pch, encoding='utf-8').read()
    if MACROS not in text:
        anchor = '#define REX_LOAD_U8(x)'
        if MARKER in text:
            start = text.index(MARKER)
            end = text.index(END, start) + len(END)
            text = text[:start] + MACROS + text[end:]
        elif anchor in text:
            text = text.replace(anchor, MACROS + anchor, 1)
        else:
            sys.exit('ERROR (post-codegen patch): fp_sign_ops: no REX_LOAD_U8 in %s: the generated pch changed' % pch)
        if not a.check:
            open(pch, 'w', encoding='utf-8', newline='\n').write(text)
    print('fp_sign_ops%s: %d fneg, %d fabs, %d fnabs as float operations in %d files (%d already in that form); %d '
          'sign-mask statements left alone (not under their guest instruction)' % (
              ' (check only)' if a.check else '', counts['REX_FNEG'], counts['REX_FABS'], counts['REX_FNABS'], changed,
              already, unexpected))


if __name__ == '__main__':
    main()
