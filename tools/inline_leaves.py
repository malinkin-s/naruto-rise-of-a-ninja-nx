#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""banjo-nx (package 27, codegen round): the tiny leaf functions a generated file calls in another file, as inline
copies in the calling file.

No guest function is inlined into another on the Switch build except within one generated file: every call hands its
arguments over through ctx (stores before, loads after, the callee's own loads and stores of them) and pays a call and
a return. Of the 10,771 direct calls to tiny leaf functions (at most --max guest instructions, calling nothing), 68
are in the callee's own file. This step gives each file a `static inline` copy of every tiny leaf it calls in another
file, the same text as the function's definition, and calls the copy (REX_INL), so GCC can inline it and keep the
values in registers.

Exact by construction: the copy is the function's own generated code, run on the same ctx and memory. Only direct calls
of unhooked functions (`__imp__sub_X(ctx, base);`, tools/direct_calls.py) are redirected; a hooked function, a call
through a pointer or a hook keeps the original. A function whose text has static or thread_local storage, calls
anything, or is a localized native's is not copied. REX_INLINE_LEAVES_OFF (CMake BANJO_GEN_INLINE_LEAVES=OFF) calls the
originals.

Run last of the post-codegen steps (the copies are the final text); --restore first (the other steps' analyses read
calls by name and must not see the copies). Idempotent.

banjo-nx (2026-10-19, CPU proposal 7): --hot <app/config/hot_edges.txt> adds the console profile's hottest calls to
larger leaves in other files (caller callee per line): the callee (a leaf of up to --hot-max guest instructions, 128)
is copied into the caller's file only, and the calls in that file go to the copy.

usage: inline_leaves.py --gen <app/generated> [--restore] [--max N] [--hot FILE] [--hot-max N]
"""
import glob
import os
import re
import sys

BEGIN = '// banjo-nx: inline copies of tiny leaf functions of other files (tools/inline_leaves.py)'
END = '// banjo-nx: end of the inline copies (tools/inline_leaves.py)'
FUNC_RE = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]+)\) \{$')
CALL_ANY_RE = re.compile(r'\b(\w+)\(ctx, base\)')
DIRECT_RE = re.compile(r'\b__imp__(sub_[0-9A-F]+)\(ctx, base\);')
INL_RE = re.compile(r'\bREX_INL\((sub_[0-9A-F]+)\)\(ctx, base\);')
PCH_MACRO = '''
// banjo-nx (package 27): tools/inline_leaves.py. A call of a tiny leaf function of another file goes to the copy the
// calling file has of it (the same code; GCC may inline it), or to the original with REX_INLINE_LEAVES_OFF.
#ifndef REX_INL
#if defined(REX_INLINE_LEAVES_OFF)
#define REX_INL(name) __imp__##name
#else
#define REX_INL(name) inl_##name
#endif
#endif
'''


def restore_text(text):
    if BEGIN in text:
        a = text.index(BEGIN)
        b = text.index(END) + len(END) + 1
        # peggle2-nx (2026-10-19): the empty line main() puts after END goes too. Before, every run of
        # tools/post_codegen.py on a processed tree left one more empty line in each file with copies.
        if text[b:b + 1] == '\n':
            b += 1
        text = text[:a] + text[b:]
    return INL_RE.sub(lambda m: f'__imp__{m.group(1)}(ctx, base);', text)


def parse_functions(files, max_ins, hot=None, hot_max=0):
    """name -> (file, body lines) of the copyable tiny leaves (and of the hot callees up to hot_max instructions)."""
    leaves = {}
    for path in files:
        lines = open(path, encoding='utf-8').read().split('\n')
        i = 0
        while i < len(lines):
            m = FUNC_RE.match(lines[i])
            if not m:
                i += 1
                continue
            name = m.group(1)
            j = i + 1
            while j < len(lines) and lines[j] != '}':
                j += 1
            body = lines[i + 1:j]
            i = j + 1
            text = '\n'.join(body)
            instructions = sum(1 for l in body if l.startswith('\t// ') and not l.startswith('\t// REX'))
            if instructions > (hot_max if hot and name in hot else max_ins):
                continue
            calls = [c for c in CALL_ANY_RE.findall(text)]
            if calls:
                continue
            if 'static ' in text or 'thread_local' in text or 'REX_HOT_' in text or 'banjo_' in text or 'sa2_' in text or \
                    '&ctx' in text:
                continue
            leaves[name] = (path, body)
    return leaves


def main():
    args = sys.argv[1:]
    gen = args[args.index('--gen') + 1]
    max_ins = int(args[args.index('--max') + 1]) if '--max' in args else 12
    hot_max = int(args[args.index('--hot-max') + 1]) if '--hot-max' in args else 128
    hot = {}  # callee -> the callers whose files get a copy
    if '--hot' in args:
        for line in open(args[args.index('--hot') + 1], encoding='utf-8'):
            parts = line.split('#', 1)[0].split()
            if len(parts) == 2:
                hot.setdefault(parts[1], set()).add(parts[0])
    files = sorted(glob.glob(os.path.join(gen, '*_recomp.*.cpp')))
    # Restore every file first (the copies and the calls), then, unless --restore, add them again.
    for path in files:
        text = open(path, encoding='utf-8').read()
        new = restore_text(text)
        if new != text:
            open(path, 'w', encoding='utf-8', newline='\n').write(new)
    if '--restore' in args:
        return
    pch = os.path.join(gen, 'sa2_pch.h')
    if os.path.isfile(pch):
        p = open(pch, encoding='utf-8').read()
        if 'REX_INL(' not in p:
            open(pch, 'w', encoding='utf-8', newline='\n').write(p + PCH_MACRO)
    leaves = parse_functions(files, max_ins, hot, hot_max)
    # The files that define each hot edge's caller: only they get a copy of a callee above --max.
    hot_files = {}
    if hot:
        callers = {c for cs in hot.values() for c in cs}
        for path in files:
            for line in open(path, encoding='utf-8'):
                m = FUNC_RE.match(line.rstrip('\n'))
                if m and m.group(1) in callers:
                    hot_files.setdefault(m.group(1), path)
    total_calls = total_copies = 0
    for path in files:
        text = open(path, encoding='utf-8').read()
        used = []

        def redirect(m):
            name = m.group(1)
            leaf = leaves.get(name)
            if leaf is None or leaf[0] == path:
                return m.group(0)
            if name in hot and not any(hot_files.get(c) == path for c in hot[name]):
                # a hot callee above --max: only in its callers' files
                body = leaf[1]
                if sum(1 for l in body if l.startswith('\t// ') and not l.startswith('\t// REX')) > max_ins:
                    return m.group(0)
            if name not in used:
                used.append(name)
            return f'REX_INL({name})(ctx, base);'

        new = DIRECT_RE.sub(redirect, text)
        if not used:
            continue
        copies = [BEGIN]
        for name in sorted(used):
            body = leaves[name][1]
            copies.append(f'static inline void inl_{name}(PPCContext& __restrict ctx, uint8_t* base) {{')
            copies += body
            copies.append('}')
        copies.append(END)
        # After the file's includes: before its first function.
        lines = new.split('\n')
        first = next(i for i, l in enumerate(lines) if FUNC_RE.match(l) or l.startswith('DEFINE_REX_FUNC('))
        lines[first:first] = copies + ['']
        open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
        total_calls += len(DIRECT_RE.findall(text)) - len(DIRECT_RE.findall(new))
        total_copies += len(used)
    print(f'inline_leaves: {len(leaves)} tiny leaf functions (<= {max_ins} guest instructions, no calls; '
          f'{sum(1 for h in hot if h in leaves)} of the {len(hot)} hot callees up to {hot_max}); '
          f'{total_calls} calls in other files go to {total_copies} inline copies')


if __name__ == '__main__':
    main()
