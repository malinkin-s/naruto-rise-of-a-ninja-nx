#!/usr/bin/env python3
"""Direct calls between recompiled game functions that have no hook (post-codegen step, after every codegen).

From sa2-nx tools/direct_calls.py (masseffect-nx's, GPL-3.0), adapted to Naruto. With GCC every recompiled function
sub_X is a weak alias of __imp__sub_X (DEFINE_REX_FUNC in naruto_pch.h), so a hook (REX_HOOK*, BANJO_RENUT_HOOK*)
can replace it at link time. The generated code always calls sub_X, and the compiler cannot inline a weak function.
This step turns `sub_X(ctx, base);` into `__imp__sub_X(ctx, base);` when sub_X has no hook: the same function, now
inlinable. naruto_init.cpp / naruto_register.cpp are not touched: the indirect-call table keeps sub_X and its hooks.

Hooked = conservative: every 82xxxxxx / 88xxxxxx address anywhere in the app's and the SDK's sources, the manifest,
the Switch defaults and CMakeLists.txt, comments and SA2 addresses of the vendored renderer included (a name too
many only costs an inlining; one missing would bypass a hook). The seed lists (*-seeds.toml) are function bounds, not
hooks, and are left out.

  python3 tools/direct_calls.py [--undo | --redo] [--dry-run] [--check]
    --redo: undo + convert in one pass, writing only files that change (run after every codegen).
    --check: exit 1 if a tree has convertible calls left or no direct call at all.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app')
TREES = [os.path.join(APP, 'generated', t) for t in ('default', 'ai2c')]
SDK = os.path.join(ROOT, 'sdk')
SOURCES = [os.path.join(APP, 'src'), os.path.join(SDK, 'src'), os.path.join(SDK, 'include'),
           os.path.join(APP, 'naruto_manifest.toml'), os.path.join(APP, 'naruto_switch_defaults.toml'),
           os.path.join(APP, 'codegen_flavor.toml'), os.path.join(APP, 'CMakeLists.txt'), os.path.join(APP, 'cmake')]
SKIP_SUFFIXES = ('.a', '.o', '.obj', '.png', '.jpg', '.bin')
ADDRESS = re.compile(r'(?<![0-9A-Fa-f])(8[28][0-9A-Fa-f]{6})(?![0-9A-Fa-f])')


def hooked():
    names = set()
    for root in SOURCES:
        if os.path.isfile(root):
            paths = [root]
        elif os.path.isdir(root):
            paths = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if not f.endswith(SKIP_SUFFIXES)]
        else:
            continue
        for path in paths:
            try:
                text = open(path, encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            # A native layer calling an original through __imp__sub_X does not hook sub_X.
            text = re.sub(r'__imp__sub_[0-9A-Fa-f]{8}', ' ', text)
            names.update('sub_' + m.upper() for m in ADDRESS.findall(text))
    return names


def main():
    undo = '--undo' in sys.argv
    redo = '--redo' in sys.argv
    check = '--check' in sys.argv
    dry = '--dry-run' in sys.argv or check
    with_hook = set() if undo else hooked()
    call = re.compile(r'(?<![\w])sub_([0-9A-F]{8})\(ctx, base\);')
    direct = re.compile(r'__imp__sub_([0-9A-F]{8})\(ctx, base\);')
    failed = False
    for gen in TREES:
        changed = files = seen = already = 0
        for f in sorted(os.listdir(gen)):
            if not re.match(r'\w+_recomp\.\d+\.cpp$', f):
                continue
            path = os.path.join(gen, f)
            text = open(path, encoding='utf-8').read()
            seen += 1
            already += len(direct.findall(text))
            if undo:
                new, n = direct.subn(lambda m: 'sub_%s(ctx, base);' % m.group(1), text)
            else:
                source = direct.sub(lambda m: 'sub_%s(ctx, base);' % m.group(1), text) if redo else text
                new = call.sub(lambda m: m.group(0) if 'sub_' + m.group(1) in with_hook
                               else '__imp__sub_%s(ctx, base);' % m.group(1), source)
                n = len(call.findall(source)) - len(call.findall(new))
            if new != text:
                files += 1
                if not dry:
                    open(path, 'w', encoding='utf-8', newline='\n').write(new)
            changed += n
        name = os.path.relpath(gen, ROOT)
        if seen == 0:
            sys.exit('ERROR (post-codegen): direct_calls: no *_recomp.N.cpp in %s' % name)
        if not undo and changed == 0 and already == 0:
            sys.exit('ERROR (post-codegen): direct_calls: no sub_X calls and no direct calls in %s: the generated '
                     'call shape changed' % name)
        if check:
            print('%s: %d direct calls, %d still convertible' % (name, already, changed))
            failed |= bool(changed) or already == 0
            continue
        print('%s: %s %d calls in %d files (%d hooked addresses respected)' %
              (name, 'undone' if undo else 'direct', changed, files, len(with_hook)))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
