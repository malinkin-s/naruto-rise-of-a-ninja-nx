#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""cpu_aggressive (proposed post-codegen step, after tools/flush_mode_flow.py): flush-mode checks of a loop header
hoisted in front of the loop.

flush_mode_flow.py proves a check redundant when every path into it agrees on the mode. At the head of a loop the
paths are the loop's entry (mode unknown) and its back edges (mode set by this very check on the previous
iteration), so a check there stays and costs a load of ctx.fpscr, a test and a branch on EVERY iteration (the
compiler cannot keep the cached word in a register: guest stores may alias ctx for it). Example: the inner loop of
the XAudio voice filter sub_82B0DCB8 (256 iterations per block).

Rewrite, per loop, when all of these hold (checked on the generated text):
  1. the loop is a run of lines from a label H to the last `goto H` (or `if (...) goto H;`) after it; no goto from
     outside the run lands inside it except at H, and no line outside the run but this one falls into H... the only
     way in is falling into H from the line before (loop_locals.py's REX_LOOP_IN copies included) or a border stub
     that goes to H (the check is then also put into the stub);
  2. nothing in the run passes ctx to other code (no `(ctx, base` call, REX_CALL_INDIRECT, REX_PROMOTED, ppc_trap,
     hook), no `return`, no `switch`, and no fpscr mention other than checks of ONE direction (all disable or all
     enable) and REX_FLUSH_KNOWN_* of that same direction;
  3. the check C is in the straight-line part of the header: between H and C only statements that are not labels,
     gotos, ifs, returns or blocks (a REX_LOOP_BARRIER, guest loads, register moves): every entry to the loop
     executes C before it can leave the loop or test anything.
Then C becomes REX_FLUSH_KNOWN_<dir>() and the same check is written before H (and in each stub to H). Exact:
  - the statements between the hoisted check and C's old place are mode-independent (each mode-dependent
    statement has its own check or a flush_mode_flow proof; a proof that relied on the entry mode in that stretch
    would contradict 2., which forbids the other direction in the loop, and in front of C there is no such proof:
    C is the first check on the path);
  - every iteration after the first starts in C's mode (2.: nothing in the loop changes it), so C would not switch;
  - at every exit the mode is C's in both forms (3.: C runs before any exit).
Every hoisted check keeps the PC build's verification: REX_FLUSH_KNOWN_* tests the mode and counts on the PC, and a
wrong proof would show as "N had to switch the mode" in the [verify] line. Switch back: REX_FLUSH_HOIST_OFF makes
the REX_FLUSH_HOIST_KNOWN_* macros the original check again (the hoisted copy before the loop is then redundant and
harmless: it is the same check C performs first anyway).

  python flush_hoist.py --gen <tree> [--check] [--stats out.json]
"""
import argparse
import collections
import json
import os
import re

FUNC = re.compile(r'^DEFINE_REX_FUNC\((\w+)\) \{$')
LABEL = re.compile(r'^(loc_[0-9A-Fa-f]+):$')
GOTO_ANY = re.compile(r'\bgoto (loc_[0-9A-Fa-f]+);')
DISABLE = 'ctx.fpscr.disableFlushMode();'
HOIST_TAG = '// flush_hoist.py'
ENABLE = 'ctx.fpscr.enableFlushMode();'
MARKER = '// cpu_aggressive: loop-header flush checks hoisted (flush_hoist.py)'
MACROS = MARKER + r'''
#ifndef REX_FLUSH_HOIST_KNOWN_ON
#if defined(REX_FLUSH_HOIST_OFF)
#define REX_FLUSH_HOIST_KNOWN_ON() ctx.fpscr.enableFlushMode()
#define REX_FLUSH_HOIST_KNOWN_OFF() ctx.fpscr.disableFlushMode()
#else
#define REX_FLUSH_HOIST_KNOWN_ON() REX_FLUSH_KNOWN_ON()
#define REX_FLUSH_HOIST_KNOWN_OFF() REX_FLUSH_KNOWN_OFF()
#endif
#endif
'''
UNSAFE = re.compile(r'\(ctx, base|REX_CALL_INDIRECT|REX_PROMOTED|ppc_trap|\breturn\b|switch \(|setjmp|longjmp|'
                    r'Unconditional|storeFromGuest|loadFromHost|restoreGuestBits|mtfsf|mffs|\(ctx\)|\(ctx,|, ctx\)')
FLOATY = re.compile(r'\.f64|\.f32|simde|_mm_|REX_F[A-Z]|AnyMode|double\(|float\(|f32\[|f64\[')
STRAIGHT_OK = re.compile(r'^(//|REX_LOOP_BARRIER\(\);|REX_LOOP_IN\(|[\w.\[\]]+ = [^;{}?]*;$|REX_FLUSH_KNOWN_(ON|OFF)\(\);|'
                         r'REX_DEAD_DEF\(|REX_DEAD_REC\(|s\.Hit\()')


def process(body, stats):
    """New body lines or None."""
    lines = list(body)
    changed = False
    label_at = {}
    for k, l in enumerate(lines):
        m = LABEL.match(l.strip())
        if m:
            label_at[m.group(1)] = k
    gotos = collections.defaultdict(list)       # label -> line indices of gotos to it
    for k, l in enumerate(lines):
        for t in GOTO_ANY.findall(l):
            gotos[t].append(k)
    for lab, h in sorted(label_at.items(), key=lambda x: x[1]):
        back = [k for k in gotos.get(lab, []) if k > h]
        if not back:
            continue
        end = max(back)
        run = range(h + 1, end + 1)
        text = [lines[k].strip().replace(' ' + HOIST_TAG, '') for k in run]
        # 2. nothing unsafe; one direction
        if any(UNSAFE.search(t) for t in text if not t.startswith('//')):
            stats['unsafe'] += 1
            continue
        dirs = set()
        for t in text:
            if t == DISABLE or t == 'REX_FLUSH_KNOWN_OFF();' or t == 'REX_FLUSH_HOIST_KNOWN_OFF();':
                dirs.add('off')
            elif t == ENABLE or t == 'REX_FLUSH_KNOWN_ON();' or t == 'REX_FLUSH_HOIST_KNOWN_ON();':
                dirs.add('on')
            elif 'fpscr' in t:
                dirs.add('other')
        if len(dirs) != 1 or 'other' in dirs:
            if dirs:
                stats['mixed'] += 1
            continue
        d = dirs.pop()
        check = DISABLE if d == 'off' else ENABLE
        # 3. the first check in the header's straight line
        c = None
        for k in run:
            t = lines[k].strip().replace(' ' + HOIST_TAG, '')
            if t == check:
                c = k
                break
            if t.startswith('//') or not t:
                continue
            if not STRAIGHT_OK.match(t) or LABEL.match(t) or 'goto' in t or t.startswith('if') or '{' in t or '}' in t:
                break
            if FLOATY.search(t):
                break                    # a float statement in front of C: not provably mode-independent
        if c is None:
            stats['no_header_check'] += 1
            continue
        # 1. entries: no goto from outside the run into it, except to H (from stubs or elsewhere)
        inside = set(run) | {h}
        ok = True
        stubs = []
        for l2, k2 in label_at.items():
            if h < k2 <= end:
                if any(g not in inside for g in gotos.get(l2, [])):
                    ok = False
                    break
        if not ok:
            stats['side_entry'] += 1
            continue
        outside_gotos_to_h = [g for g in gotos.get(lab, []) if g not in inside]
        # a goto from outside to H: only from a border stub (label line + REX_LOOP_IN lines + this goto)
        for g in outside_gotos_to_h:
            gl = lines[g].strip()
            if not re.match(r'^goto loc_[0-9A-Fa-f]+;$', gl):
                ok = False
                break
            j = g - 1
            while j >= 0 and lines[j].strip().startswith('REX_LOOP_IN('):
                j -= 1
            if j < 0 or not LABEL.match(lines[j].strip()):
                ok = False
                break
            stubs.append(g)
        if not ok:
            stats['outside_goto'] += 1
            continue
        # does the line before H fall into it? (it does unless it is an unconditional goto / return)
        prev = h - 1
        while prev >= 0 and (not lines[prev].strip() or lines[prev].strip().startswith('//')):
            prev -= 1
        falls = prev >= 0 and not re.match(r'^(goto loc_[0-9A-Fa-f]+;|return;|\}.*)$', lines[prev].strip())
        # rewrite: C -> known; the check before H on the fall-through path and in front of each stub's goto
        lines[c] = lines[c].replace(check, 'REX_FLUSH_HOIST_KNOWN_%s();' % d.upper())
        ins = []
        if falls:
            # in front of loop_locals.py's REX_LOOP_IN copies that end the fall-through path, if any
            j = h
            while j - 1 >= 0 and lines[j - 1].strip().startswith('REX_LOOP_IN('):
                j -= 1
            ins.append(j)
        ins += stubs
        for k in sorted(ins, reverse=True):
            # the marker comment keeps flush_mode_flow.py (if it ever runs on this text) from taking the line for a
            # generator check it may prove, and lets --restore find it
            lines.insert(k, '\t' + check + ' ' + HOIST_TAG)
        stats['hoisted'] += 1
        stats['stub_entries'] += len(stubs)
        changed = True
        return lines  # one loop per pass (indices moved); the caller repeats
    return lines if changed else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--list')
    ap.add_argument('--restore', action='store_true', help='take every hoist of an earlier run back out')
    a = ap.parse_args()
    files = sorted(f for f in os.listdir(a.gen) if re.match(r'\w+_recomp\.\d+\.cpp$', f))
    if a.restore:
        n = 0
        for f in files:
            path = os.path.join(a.gen, f)
            t = open(path, encoding='utf-8').read()
            if 'REX_FLUSH_HOIST_KNOWN_' not in t and HOIST_TAG not in t:
                continue
            lines = [l for l in t.split('\n') if not l.endswith(' ' + HOIST_TAG)]
            t2 = '\n'.join(lines).replace('REX_FLUSH_HOIST_KNOWN_OFF();', DISABLE).replace(
                'REX_FLUSH_HOIST_KNOWN_ON();', ENABLE)
            open(path, 'w', encoding='utf-8', newline='\n').write(t2)
            n += 1
        print('flush_hoist: restored %d files' % n)
        return
    pch = [f for f in os.listdir(a.gen) if f.endswith('_pch.h')][0]
    stats = collections.Counter()
    hoisted_in = collections.Counter()
    for f in files:
        path = os.path.join(a.gen, f)
        lines = open(path, encoding='utf-8').read().split('\n')
        out = []
        i = 0
        changed = False
        while i < len(lines):
            m = FUNC.match(lines[i])
            if not m:
                out.append(lines[i])
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j] != '}':
                j += 1
            body = lines[i + 1:j]
            before = stats['hoisted']
            for _ in range(64):
                new = process(body, stats)
                if new is None:
                    break
                body = new
            if stats['hoisted'] != before:
                hoisted_in[m.group(1)] += stats['hoisted'] - before
                changed = True
            out.append(lines[i])
            out.extend(body)
            i = j
        if changed and not a.check:
            open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    if not a.check:
        p = os.path.join(a.gen, pch)
        t = open(p, encoding='utf-8').read()
        if MARKER not in t:
            anchor = '// rexglue ports: 16-byte reversal of guest vectors'
            if anchor in t:
                k = t.index(anchor)
                open(p, 'w', encoding='utf-8', newline='\n').write(t[:k] + MACROS + t[k:])
            elif '#define REX_LOAD_U8(x)' in t:
                k = t.index('#define REX_LOAD_U8(x)')
                open(p, 'w', encoding='utf-8', newline='\n').write(t[:k] + MACROS + t[k:])
            else:
                open(p, 'w', encoding='utf-8', newline='\n').write(MACROS + t)
    if a.list:
        with open(a.list, 'w') as fo:
            for n, c in hoisted_in.most_common():
                fo.write('%s %d\n' % (n, c))
    print('flush_hoist: %s; %d functions' % (dict(stats), len(hoisted_in)))


if __name__ == '__main__':
    main()
