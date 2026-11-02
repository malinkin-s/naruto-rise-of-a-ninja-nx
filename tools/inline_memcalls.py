#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""memcpy / memset calls of a constant size up to 64 bytes inline at the call site (from sasrt-nx's tool of
2026-10-14, idea 6 of sa2-nx's list, also sonic-unleashed-nx's SWITCH_INLINE_MEMCPY; banjo-nx's copy).
A call of the C runtime's memcpy (sub_82BB4510) or memset (sub_82BB4A40) whose size register r5 is set to a constant
(li r5,N) earlier in the same straight line, with nothing in between that writes r5, a label or a call, becomes
    REX_MEMCPY_CONST(N, <the call as it was>);      REX_MEMSET_CONST(N, <the call as it was>);
The helpers (in the generated pch, below; the pure parts in sdk/include/rex/ppc/memcalls.h, tested by
sdk/tests/memcalls_test.cpp) copy or fill the N bytes with a few loads and stores and run the original call (in Banjo:
through its hook, the hand-written native of app/src/cpu/hot/banjo_hand_natives.h) when they must not:
  - memcpy: the CRT routine copies FORWARD, so when dst > src and the ranges overlap it smears already-copied bytes;
  - memcpy: a destination over the save slot at r1 - 8 (the original stores r3 there first and reloads r3 from it
    at its return: the copy would come back in r3). banjo-nx's addition, the same test its hand-written memcpy makes;
  - both: a range in 0x7F000000-0x7FFFFFFF (hardware registers) or from 0xA0000000 (the physical views), or one
    that wraps around 4 GB;
  - memcpy keeps the original's first instruction, `std r3,-8(r1)`; r3 is left as it came, as both originals leave
    it (memset does not write it); r0 and r4-r12 are scratch the callers do not read after the call.
Banjo (2026-10-14): 2,227 memcpy and 1,365 memset call sites in the generated code.
REX_INLINE_MEMCALLS_OFF (compile time) gives the calls back.

  python tools/inline_memcalls.py --gen app/generated [--memcpy 82BB4510] [--memset 82BB4A40] [--check]
"""
import argparse
import collections
import glob
import os
import re
import sys

SET_R5 = re.compile(r'^\t(?:ctx\.)?r5\.s64 = (-?\d+);$')
WRITES_R5 = re.compile(r'(?:ctx\.|l_|ll_|\b)r5\.[su](?:64|32) =|REX_LOOP_(?:IN|OUT)\(ll_r5|\(ctx, base\)|'
                       r'REX_CALL_INDIRECT|ppc_trap|REX_PROMOTED|\bctx\.r5 =')
DONE = re.compile(r'REX_MEM(?:CPY|SET)_CONST\((\d+), ([^;]*\(ctx, base\))\);')
MARKER = '// rexglue ports: memcpy / memset of a constant size inline (tools/inline_memcalls.py)'
END = '// (end of the macros of tools/inline_memcalls.py)\n'
MACROS = MARKER + r'''
#ifndef REX_MEMCPY_CONST
#if defined(REX_INLINE_MEMCALLS_OFF)
#define REX_MEMCPY_CONST(n, call) call
#define REX_MEMSET_CONST(n, call) call
#else
#include <rex/ppc/memcalls.h>
// The decisions and the copy are in rex/ppc/memcalls.h (tested by sdk/tests/memcalls_test.cpp); here only what needs
// the guest memory macros.
template <uint32_t N>
[[gnu::always_inline]] static inline bool RexMemcpyConst(PPCContext& ctx, uint8_t* base) noexcept {
  const uint32_t dst = ctx.r3.u32, src = ctx.r4.u32;
  if (rex::ppc::CopySmears<N>(dst, src)) return false;      // dst > src, overlapping: the original smears
  if (!rex::ppc::PlainRange<N>(dst) || !rex::ppc::PlainRange<N>(src)) return false;
  // banjo-nx: the original reloads r3 from -8(r1) at its return: a destination over that slot returns copied bytes.
  if (rex::ppc::CoversSlot<N>(dst, ctx.r1.u32 - 8u)) return false;
  REX_STORE_U64(ctx.r1.u32 - 8, ctx.r3.u64);                // std r3,-8(r1), the original's first instruction
  rex::ppc::CopyConst<N>(REX_RAW_ADDR(dst), REX_RAW_ADDR(src));
  return true;
}
template <uint32_t N>
[[gnu::always_inline]] static inline bool RexMemsetConst(PPCContext& ctx, uint8_t* base) noexcept {
  const uint32_t dst = ctx.r3.u32;
  if (!rex::ppc::PlainRange<N>(dst)) return false;
  __builtin_memset(REX_RAW_ADDR(dst), int(ctx.r4.u32 & 0xFF), N);
  return true;
}
#define REX_MEMCPY_CONST(n, call) do { if (!RexMemcpyConst<n>(ctx, base)) { call; } } while (0)
#define REX_MEMSET_CONST(n, call) do { if (!RexMemsetConst<n>(ctx, base)) { call; } } while (0)
#endif  // REX_INLINE_MEMCALLS_OFF
#endif  // REX_MEMCPY_CONST
''' + END


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True)
    ap.add_argument('--memcpy', default='827F05C0')
    ap.add_argument('--memset', default='827EFEA0')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    call = re.compile(r'^(\t+)((?:__imp__)?sub_(%s|%s)\(ctx, base\));$' % (a.memcpy.upper(), a.memset.upper()))
    counts = collections.Counter()
    sizes = collections.Counter()
    changed = 0
    for path in sorted(glob.glob(os.path.join(a.gen, '*_recomp.*.cpp'))):
        text = open(path, encoding='utf-8').read()
        lines = text.split('\n')
        known = None
        for i, line in enumerate(lines):
            if line.startswith(('loc_', 'DEFINE_REX_FUNC', '}')):
                known = None
                continue
            m = SET_R5.match(line)
            if m:
                known = int(m.group(1))
                continue
            c = call.match(line)
            if c:
                which = 'memcpy' if c.group(3) == a.memcpy.upper() else 'memset'
                counts[which + ' calls'] += 1
                if known is not None and 1 <= known <= 64:
                    lines[i] = '%sREX_%s_CONST(%d, %s);' % (c.group(1), which.upper(), known, c.group(2))
                    counts[which] += 1
                    sizes[(which, known)] += 1
                known = None
                continue
            if known is not None and line.strip() and not line.strip().startswith('//') and WRITES_R5.search(line):
                known = None
        counts['already'] += sum(1 for _ in DONE.finditer(text))
        new = '\n'.join(lines)
        if new != text:
            changed += 1
            if not a.check:
                open(path, 'w', encoding='utf-8', newline='\n').write(new)
    pchs = glob.glob(os.path.join(a.gen, '*_pch.h'))
    if len(pchs) != 1:
        sys.exit('ERROR (post-codegen patch): inline_memcalls: no single *_pch.h in %s' % a.gen)
    text = open(pchs[0], encoding='utf-8').read()
    if MACROS not in text and not a.check:
        anchor = '#define REX_LOAD_U8(x)'
        if MARKER in text:
            start = text.index(MARKER)
            text = text[:start] + text[text.index(END, start) + len(END):]
        # After the load / store macros the helpers use (REX_STORE_U64, REX_RAW_ADDR): before the first function
        # declaration block, i.e. at the end of the pch's macro section.
        anchor2 = '#define REX_MEMORY_SIZE'
        if anchor2 not in text:
            sys.exit('ERROR (post-codegen patch): inline_memcalls: no REX_MEMORY_SIZE in %s' % pchs[0])
        text = text.replace(anchor2, MACROS + anchor2, 1)
        open(pchs[0], 'w', encoding='utf-8', newline='\n').write(text)
    top = ', '.join('%s %d x%d' % (w, n, c) for (w, n), c in sizes.most_common(8))
    print('inline_memcalls%s: %d of %d memcpy and %d of %d memset calls have a constant size of 1-64 bytes and are '
          'inline (%d files; %d already); most common: %s' % (
              ' (check only)' if a.check else '', counts['memcpy'], counts['memcpy calls'], counts['memset'],
              counts['memset calls'], changed, counts['already'], top))


if __name__ == '__main__':
    main()
