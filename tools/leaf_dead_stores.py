#!/usr/bin/env python3
# sa2-nx: copied from banjo-nx on 2026-10-19 (its codegen round), adapted to sa2-nx's tree.
"""(banjo-nx's copy of sasrt-nx's tool of 2026-10-14: Banjo's entry point, its tomls in app/config, its hand-written
natives from app/src/cpu/hot/hand.txt, out/renut_image.bin; compile switches BANJO_GEN_LEAF_DEAD and
BANJO_GEN_LEAF_DEAD_POISON in app/CMakeLists.txt. sasrt-nx's description:)
Leaf functions write back only the registers a caller can read (sasrt-nx, 2026-10-14; idea 1 of sa2-nx's list).

tools/leaf_locals.py keeps the ctx registers of a leaf function in C++ locals and writes every register the function
wrote back into ctx at each exit (REX_LEAF_STORE). This step finds the write-backs no caller can read and writes them
as REX_LEAF_DEAD_R / REX_LEAF_DEAD_F, which compile to nothing (or, for the PC test, to a poison value).

"No caller can read" is decided on the GUEST code (the instruction comments of the generated tree), across functions:
  - per function, the registers it (or anything it calls) may read before writing them (UE), to a fixed point over the
    call graph; a call kills nothing (the 360 compiler allocates registers across functions, lesson (e) of the list);
  - per call site, the registers live after the call: read later in the caller before being written, or still
    unwritten when the caller returns and live after the CALLER returns (LiveOut of the caller, to a fixed point); a
    tail call passes the caller's LiveOut on unchanged;
  - everything is live (ALL) after a function nobody can be shown to call only directly: its address is a data word
    of the image (any section but .pdata), a lis + addi / ori pair anywhere in a function, the entry point, a promoted
    indirect target, any 8[23]xxxxxx in the port's own sources (app/src, sdk, the tomls and txt files: hooks, natives,
    the verify mode that compares registers, host code that calls guest functions), or it has no direct caller;
  - everything is live at an indirect call, an import or hooked call (sub_X without __imp__), a trap, an unknown
    instruction, and before a call whose callee is not in the tree;
  - r1, r2, r13 (stack, TOC, thread) and the return registers r3 and f1 are always written back.
Only the volatile registers (r0, r3-r12, f0-f13) ever take the dead form: the non-volatile ones are locals already.

The PC test (lesson (c)): REX_LEAF_DEAD_POISON (app/CMakeLists.txt BANJO_GEN_LEAF_DEAD_POISON) writes 0xDEADBEEF...
into a skipped general register and a signalling NaN into a skipped float register, so a reader this analysis missed
breaks the game visibly. REX_LEAF_DEAD_KEEP (BANJO_GEN_LEAF_DEAD=OFF) writes them back as before.

  python tools/leaf_dead_stores.py --gen app/generated [--image out/renut_image.bin] [--check] [--list FILE]
"""
import argparse
import collections
import glob
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY_POINT = 0x82543108  # sa2-nx: the image's PE header (AddressOfEntryPoint 0x543108 + base 0x82000000)


def R(n):
    return 1 << n


def F(n):
    return 1 << (32 + n)


ALL = (1 << 64) - 1
VOLATILE = R(0) | sum(R(n) for n in range(3, 13)) | sum(F(n) for n in range(14))
ALWAYS = R(1) | R(2) | R(13) | R(3) | F(1)
REG = re.compile(r'(?<![\w])([rf])(\d+)(?![\w])')


def regs(text):
    m = 0
    for kind, n in REG.findall(text):
        n = int(n)
        if n < 32:
            m |= R(n) if kind == 'r' else F(n)
    return m


def reg_name(bit):
    return ('r%d' % bit) if bit < 32 else ('f%d' % (bit - 32))


# --- what each guest instruction reads and writes (general and float registers only) -------------------------------
WRITE_FIRST = set('''add addc adde addic addme addze and andc andi andis clrldi clrlwi cntlzd cntlzw divd divdu divw
divwu eqv extsb extsh extsw fabs fadd fadds fcfid fctid fctidz fctiw fctiwz fdiv fdivs fmadd fmadds fmr fmsub fmsubs
fmul fmuls fnabs fneg fnmadd fnmadds fnmsub fnmsubs frsp fsel fsqrt fsqrts fsub fsubs mflr mfmsr mfocrf mfcr mftb mffs
mfctr mfxer mulhw mulhwu mulhd mulhdu mulld mulli mullw neg nor not or orc ori oris rldicl rldicr rldic rldcl rotldi
rotlw rotlwi rlwinm rlwnm sld slw srad sradi sraw srawi srd srw subf subfc subfe subfic subfme subfze xor xori xoris
mr li lis extlwi extrwi slwi srwi sldi srdi clrrwi clrrdi'''.split())
ADDI_FORMS = {'addi', 'addis', 'la'}                    # rA = r0 is the literal 0
READ_DEST = {'rlwimi', 'rldimi', 'insrwi', 'inslwi', 'insrdi'}
LOADS = set('''lbz lbzu lbzux lbzx ld ldarx ldbrx ldu ldux ldx lfd lfdu lfdux lfdx lfs lfsu lfsux lfsx lha lhau lhaux
lhax lhz lhzu lhzux lhzx lwa lwarx lwax lwaux lwbrx lhbrx lwz lwzu lwzux lwzx'''.split())
VLOADS = set('''lvebx lvehx lvewx lvewx128 lvlx lvlx128 lvlxl lvlxl128 lvrx lvrx128 lvrxl lvrxl128 lvsl lvsl128 lvsr
lvsr128 lvx lvx128 lvxl lvxl128'''.split())
STORES = set('''stb stbu stbux stbx std stdbrx stdcx stdu stdux stdx stfd stfdu stfdux stfdx stfiwx stfs stfsu stfsux
stfsx sth sthbrx sthu sthux sthx stw stwbrx stwcx stwu stwux stwx stvebx stvehx stvewx stvewx128 stvlx stvlx128 stvlxl
stvlxl128 stvrx stvrx128 stvrxl stvrxl128 stvx stvx128 stvxl stvxl128'''.split())
READS = set('''cmpd cmpdi cmpld cmpldi cmplw cmplwi cmpw cmpwi fcmpu fcmpo mtctr mtlr mtcr mtcrf mtxer mtmsr mtmsrd
mtfsf mtspr dcbf dcbst dcbt dcbtst dcbz dcbzl dcbi icbi'''.split())
NONE = set('''nop sync lwsync eieio isync db16cyc cctpl cctpm cctph mtfsfi mtfsb0 mtfsb1 crand crandc creqv crnand crnor
cror crorc crxor crset crclr crnot crmove mcrf'''.split())
TRAPS = re.compile(r'^t[dw]')


def address_operand(op):
    """The registers an address operand reads: 'd(rA)' or 'rA' (r0 there is the literal 0) or '0'."""
    m = re.match(r'^-?\w*\((r\d+)\)$', op)
    reg = m.group(1) if m else op
    return 0 if reg in ('r0', '0') else regs(reg)


def defuse(mn, operands):
    """(written, read) register masks of one guest instruction; unknown forms read everything and write nothing."""
    base = mn.rstrip('.').rstrip('+-')
    ops = [o.strip() for o in operands.split(',')] if operands.strip() else []
    if base.startswith('v') or base in NONE:
        return 0, 0                                     # vector arithmetic: no general or float register
    if base.startswith('b'):
        return 0, 0                                     # branches: the C++ structure gives their effect
    if TRAPS.match(base) or base == 'trap' or base == '.long' or base == 'sc':
        return 0, ALL
    if base in WRITE_FIRST and ops:
        return regs(ops[0]), regs(','.join(ops[1:]))
    if base in ADDI_FORMS and len(ops) == 3:
        return regs(ops[0]), (0 if ops[1] == 'r0' else regs(ops[1]))
    if base in READ_DEST and ops:
        return regs(ops[0]), regs(','.join(ops))
    if base in LOADS and len(ops) >= 2:
        use = address_operand(ops[1]) | (regs(','.join(ops[2:])) if len(ops) > 2 else 0)
        write = regs(ops[0])
        if base.endswith(('u', 'ux')) and base not in ('lwbrx', 'ldbrx', 'lhbrx'):
            m = re.search(r'\((r\d+)\)', ops[1])
            write |= regs(m.group(1) if m else ops[1])
            use |= regs(m.group(1) if m else ops[1])
        return write, use
    if base in VLOADS and len(ops) >= 2:
        return 0, address_operand(ops[1]) | (regs(','.join(ops[2:])) if len(ops) > 2 else 0)
    if base in STORES and len(ops) >= 2:
        use = regs(ops[0]) | address_operand(ops[1]) | (regs(','.join(ops[2:])) if len(ops) > 2 else 0)
        write = 0
        if base.endswith(('u', 'ux')):
            m = re.search(r'\((r\d+)\)', ops[1])
            write = regs(m.group(1) if m else ops[1])
            use |= write
        return write, use
    if base in READS:
        if base.startswith('dcb') or base == 'icbi':
            return 0, address_operand(ops[0]) | (regs(','.join(ops[1:])) if len(ops) > 1 else 0) if ops else 0
        return 0, regs(','.join(ops))
    return 0, ALL


# --- the generated tree as functions of guest instructions with their C++ control flow ------------------------------
HEAD = re.compile(r'^DEFINE_REX_FUNC\((?:__imp__)?sub_([0-9A-F]{8})\) \{$')
COMMENT = re.compile(r'^\t// (\S+)[ \t]*(.*)$')
LABEL = re.compile(r'^loc_([0-9A-F]{8}):')
# A direct call; also inside a macro that keeps it as its fallback (REX_MEMCPY_CONST(n, sub_X(ctx, base)) of
# tools/inline_memcalls.py: the inline path reads no more than the call does, so it counts as the call).
CALL = re.compile(r'\b(__imp__)?sub_([0-9A-F]{8})\(ctx, base\)')
OTHER_CALL = re.compile(r'\b(\w+)\(ctx, base\)')
GOTO = re.compile(r'\bgoto loc_([0-9A-F]{8});')
LEAF_STORE = re.compile(r'REX_LEAF_(?:STORE|DEAD_R|DEAD_F)\((\w+), ([rf]\d+)\)')
SAVE_HELPERS = re.compile(r'^__(?:save|rest)(?:vmx|gprlr|fpr)_\d+$')


STUB_LABEL = re.compile(r'^(loc_[0-9A-F]{8}):')
STUB_GOTO = re.compile(r'^\s*goto (loc_[0-9A-F]{8});\s*$')
ANY_GOTO = re.compile(r'\bgoto (loc_[0-9A-F]{8});')


def resolve_stubs(lines):
    """The function's lines with every goto to a border stub of tools/loop_locals.py redirected to where the stub
    goes. A stub is a label whose lines up to the next label or guest instruction are only REX_LOOP_IN / REX_LOOP_OUT
    copies and end in an unconditional goto (`loc_F0000001: REX_LOOP_IN(...); goto loc_8273FC34;`). parse_function maps
    a label to the next guest instruction, so a goto to such a stub was taken for an edge to whatever instruction
    follows the stubs (often the loop header's first instruction: a different place). Same number of lines, same
    instruction comments: the nodes and the statements stay aligned."""
    target = {}
    for i, line in enumerate(lines):
        m = STUB_LABEL.match(line)
        if not m:
            continue
        for j in range(i + 1, len(lines)):
            text = lines[j]
            if COMMENT.match(text) or STUB_LABEL.match(text):
                break
            g = STUB_GOTO.match(text)
            if g:
                target[m.group(1)] = g.group(1)
                break
            stripped = text.strip()
            if stripped and not stripped.startswith(('REX_LOOP_IN(', 'REX_LOOP_OUT(')):
                break
    if not target:
        return lines

    def final(label):
        seen = set()
        while label in target and label not in seen:
            seen.add(label)
            label = target[label]
        return label

    out = []
    for line in lines:
        if 'goto loc_' in line and not COMMENT.match(line):
            line = ANY_GOTO.sub(lambda m: 'goto %s;' % final(m.group(1)), line)
        out.append(line)
    return out


# banjo-nx (2026-10-15): mid-asm hooks. The generator calls a hook's host function in the middle of the guest code,
# with the registers the hook names passed by reference (`textureTools_SetTexture_hook(ctx.r5);`) or as a test that
# can jump (`if (disable_particles_sim()) {` / `goto loc_X;` / `}` / `else {` / `}`, or the goto in the else). Before,
# the parser saw neither the registers a hook reads nor that its goto is conditional: it took the goto for the end of
# the instruction, so the call that follows the test in the same instruction was never seen, and the writes of that
# call's arguments looked dead (the crash of tools/dead_ctx_defs.py). A hook's names are the generator's externs.
HOOK_DECL = re.compile(r'^extern (?:void|bool) (\w+)\(', re.M)
HOOK_CALL = re.compile(r'^(?:if \()?!?(\w+)\(')
MID_ASM_HOOKS = None


def load_mid_asm_hooks(gen=None):
    """The mid-asm hook names of the generated tree (its `extern void|bool name(...)` declarations)."""
    global MID_ASM_HOOKS
    gen = gen or os.path.join(ROOT, 'app', 'generated')
    names = set()
    for path in glob.glob(os.path.join(gen, '*_recomp.*.cpp')):
        names |= set(HOOK_DECL.findall(open(path, encoding='utf-8').read()))
    MID_ASM_HOOKS = names
    return names


def hook_block(chunk, k, node, targets):
    """The lines of a hook test's if / else blocks from chunk[k] on: their gotos and returns are branches the test may
    take (the instruction also falls through). Returns the index of the first line after the blocks."""
    depth = chunk[k].count('{') - chunk[k].count('}')
    k += 1
    while k < len(chunk):
        if depth <= 0:
            if not chunk[k].startswith('else'):
                break
            depth = 0
        line = chunk[k]
        g = GOTO.search(line)
        if g:
            targets.append(g.group(1))
        elif re.search(r'\breturn;', line):
            node.exit = True
        if CALL.search(line) or OTHER_CALL.search(line):
            node.use = ALL
        depth += line.count('{') - line.count('}')
        k += 1
    return k


class Node:
    __slots__ = ('use', 'defn', 'succ', 'exit', 'call', 'tail')

    def __init__(self, use, defn):
        self.use, self.defn = use, defn
        self.succ = []
        self.exit = False
        self.call = None      # (address, known) of a direct call: known = __imp__ (unhooked)
        self.tail = False     # the call is a tail call (the function returns right after it)


def parse_function(lines):
    """Nodes of one function body (the lines between its head and its closing brace)."""
    lines = resolve_stubs(lines)  # banjo-nx (2026-10-15): gotos to loop_locals.py's border stubs, to their real target
    if MID_ASM_HOOKS is None:
        load_mid_asm_hooks()
    nodes, labels, chunks = [], {}, []
    pending_labels = []
    cur = None
    for line in lines:
        m = LABEL.match(line)
        if m:
            pending_labels.append(m.group(1))
            continue
        m = COMMENT.match(line)
        if m:
            d, u = defuse(m.group(1), m.group(2))
            cur = len(nodes)
            nodes.append(Node(u, d))
            chunks.append([])
            for lab in pending_labels:
                labels[lab] = cur
            pending_labels = []
            continue
        if cur is not None and line.strip():
            chunks[cur].append(line.strip())
    end = len(nodes)
    for lab in pending_labels:
        labels[lab] = end          # a label at the very end: the function's exit
    for i, (node, chunk) in enumerate(zip(nodes, chunks)):
        falls = True
        targets = []
        text = ' '.join(chunk)
        if 'switch (' in text:
            targets += GOTO.findall(text)
            falls = False
        else:
            skip_to = 0
            for k, line in enumerate(chunk):
                if k < skip_to:
                    continue
                h = HOOK_CALL.match(line)
                if h and h.group(1) in MID_ASM_HOOKS:
                    node.use |= regs(line[h.end():])  # the registers it takes by reference
                    if line.startswith('if'):
                        skip_to = hook_block(chunk, k, node, targets)
                    continue
                if 'REX_CALL_INDIRECT' in line or 'REX_PROMOTED' in line or 'ppc_trap' in line:
                    node.use = ALL
                for m in OTHER_CALL.finditer(line):
                    name = m.group(1)
                    if re.match(r'^(?:__imp__)?sub_[0-9A-F]{8}$', name):
                        continue
                    if SAVE_HELPERS.match(name):
                        node.use |= R(0) | R(11) | R(12)
                    else:
                        node.use = ALL
                c = CALL.search(line)
                if c:
                    node.call = (int(c.group(2), 16), bool(c.group(1)))
                    rest = line[c.end():].lstrip(';') + ' ' + ' '.join(chunk[k + 1:k + 2])
                    if re.match(r'^\s*return;', rest) or (line.startswith('if') and 'return;' in line):
                        node.tail = True
                        node.exit = True
                        if not line.startswith('if'):
                            falls = False
                            break
                    continue
                g = GOTO.search(line)
                if line.startswith('if') or line.startswith('--'):
                    if g:
                        targets.append(g.group(1))
                    elif 'return;' in line:
                        node.exit = True
                    continue
                if g:
                    targets.append(g.group(1))
                    falls = False
                    break
                if re.match(r'^(\{.*)?return;( \})?$', line):
                    node.exit = True
                    falls = False
                    break
        raw = [labels.get(t, end) for t in targets] + ([i + 1] if falls else [])
        node.succ = sorted(set(s for s in raw if s < end))
        if any(s >= end for s in raw):
            node.exit = True             # falls off the end of the function, or jumps to its last label
    return nodes


def functions(gen):
    """address -> (file, list of body lines) for every function of the tree."""
    out = {}
    for path in sorted(glob.glob(os.path.join(gen, '*_recomp.*.cpp'))):
        lines = open(path, encoding='utf-8').read().split('\n')
        i = 0
        while i < len(lines):
            m = HEAD.match(lines[i])
            if not m:
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j] != '}':
                j += 1
            out[int(m.group(1), 16)] = (path, lines[i + 1:j])
            i = j + 1
    return out


# --- functions whose callers are not all direct calls in the tree --------------------------------------------------
def sections(img):
    pe = struct.unpack_from('<I', img, 0x3C)[0]
    count = struct.unpack_from('<H', img, pe + 6)[0]
    at = pe + 24 + struct.unpack_from('<H', img, pe + 20)[0]
    out = []
    for _ in range(count):
        size, va = struct.unpack_from('<II', img, at + 8)
        out.append((img[at:at + 8].rstrip(b'\0').decode('latin1'), va, size))
        at += 40
    return out


def address_taken(gen, image, starts, bodies):
    pch = open(glob.glob(os.path.join(gen, '*_pch.h'))[0], encoding='utf-8').read()
    value = lambda name: int(re.search(r'#define %s (0x[0-9A-Fa-f]+)' % name, pch).group(1), 16)
    image_base, code_base, code_size = value('REX_IMAGE_BASE'), value('REX_CODE_BASE'), value('REX_CODE_SIZE')
    img = open(image, 'rb').read()
    taken = collections.defaultdict(set)
    code_lo, code_hi = code_base - image_base, code_base - image_base + code_size
    for name, va, size in sections(img):
        lo, hi = va, min(va + size, len(img))
        if name == '.pdata' or (lo >= code_lo and hi <= code_hi) or hi <= lo:
            continue
        for w in struct.unpack_from('>%dI' % ((hi - lo) // 4), img, lo):
            if w in starts:
                taken[w].add('data word')
    # lis rX, hi ... addi / ori rY, rX, lo anywhere later in the same function; not the target of a bctr the generator
    # turned into a direct tail call (a jump thunk: lis / addi / mtctr / bctr is a tail call, an edge of the analysis).
    lis = re.compile(r'^\t// lis (r\d+),(-?\d+)$')
    low = re.compile(r'^\t// (addi|ori|addic) (r\d+),(r\d+),(-?\d+)$')
    bctr_direct = re.compile(r'^\t// bctr \n\t(?:__imp__)?sub_([0-9A-F]{8})\(ctx, base\);\n\treturn;', re.M)
    for addr, (_, lines) in bodies.items():
        resolved = set(int(t, 16) for t in bctr_direct.findall('\n'.join(lines)))
        his = collections.defaultdict(set)
        for line in lines:
            m = lis.match(line)
            if m:
                his[m.group(1)].add(int(m.group(2)) & 0xFFFF)
                continue
            m = low.match(line)
            if m and m.group(3) in his:
                lo16 = int(m.group(4))
                for hi16 in his[m.group(3)]:
                    a = ((hi16 << 16) | (lo16 & 0xFFFF)) if m.group(1) == 'ori' else ((hi16 << 16) + lo16) & 0xFFFFFFFF
                    if a in starts and a not in resolved:
                        taken[a].add('lis pair')
    taken[ENTRY_POINT].add('entry point')
    # Every address the port's own sources name (hooks, natives, verify, host code calling guest functions).
    sources = [os.path.join(ROOT, 'app', 'src'), os.path.join(ROOT, 'sdk', 'src'), os.path.join(ROOT, 'sdk', 'include')]
    # Not app/thunks.toml: it names every jump thunk and its target for tools/thunk_calls.py; a thunk is a tail call
    # in the tree (an edge of this analysis), and a thunk whose own address is taken is found like any other.
    sources += [p for p in glob.glob(os.path.join(ROOT, 'app', '*.toml')) if not p.endswith('thunks.toml')]
    # banjo-nx: its tomls are in app/config; its census hooks file is inside app/src (walked above).
    # renut_funcs.toml is the generator's table of every function's bounds and name (like thunks.toml, not a hook).
    sources += [p for p in glob.glob(os.path.join(ROOT, 'app', 'config', '*.toml'))
                if not p.endswith(('thunks.toml', 'renut_funcs.toml'))]
    sources += glob.glob(os.path.join(ROOT, 'app', '*.txt'))
    for root in sources:
        paths = [root] if os.path.isfile(root) else [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs
                                                      if f.endswith(('.cpp', '.h', '.hpp', '.inc', '.c', '.toml', '.txt'))]
        for path in paths:
            try:
                text = open(path, encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            for h in re.findall(r'(?<![0-9A-Fa-f])(8[23][0-9A-Fa-f]{6})(?![0-9A-Fa-f])', text):
                a = int(h, 16)
                if a in starts:
                    taken[a].add('named in ' + os.path.relpath(path, ROOT).replace(os.sep, '/'))
    return taken


# --- the analysis --------------------------------------------------------------------------------------------------
def forward_undefined(nodes):
    """Per node, the registers possibly not yet written on some path from the entry (in-state)."""
    n = len(nodes)
    state = [0] * n
    if not n:
        return state
    state[0] = ALL
    work = [0]
    queued = [False] * n
    queued[0] = True
    while work:
        i = work.pop()
        queued[i] = False
        out = state[i] & ~nodes[i].defn
        for s in nodes[i].succ:
            new = state[s] | out
            if new != state[s]:
                state[s] = new
                if not queued[s]:
                    queued[s] = True
                    work.append(s)
    return state


def backward(nodes, use_of, boundary):
    """Per node, live-in with `boundary` live at the exits; use_of(node) gives the node's reads."""
    n = len(nodes)
    live = [0] * n
    preds = [[] for _ in range(n)]
    for i, node in enumerate(nodes):
        for s in node.succ:
            preds[s].append(i)
    work = list(range(n))
    queued = [True] * n
    while work:
        i = work.pop()
        queued[i] = False
        node = nodes[i]
        out = boundary if node.exit else 0
        for s in node.succ:
            out |= live[s]
        new = use_of(node) | (out & ~node.defn)
        if new != live[i]:
            live[i] = new
            for p in preds[i]:
                if not queued[p]:
                    queued[p] = True
                    work.append(p)
    return live


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True)
    ap.add_argument('--image', default=os.path.join(ROOT, 'out', 'default_image.bin'))
    ap.add_argument('--check', action='store_true', help='count only, write nothing')
    ap.add_argument('--list', help='write the dead write-backs per function to this file')
    a = ap.parse_args()

    # banjo-nx (2026-10-15): the guest functions the generator names (rex_strncat, meInternalFree: 5,129 in Banjo) are
    # analysed too, and a call of one is a call edge (tools/dead_ctx_defs.py's helpers). Before, their bodies were not
    # read, so a sub_X they call missed their needs in its LiveOut (a leaf write-back one of them reads could be left
    # out), and a call of one counted as an unknown host call.
    import dead_ctx_defs as dcd
    named = dcd.named_functions(a.gen)
    hooked_named = dcd.hooked_names(set(named))
    bodies = dcd.all_functions(a.gen, named)
    starts = set(bodies)
    taken = address_taken(a.gen, a.image, starts, bodies)
    # banjo-nx (2026-10-15): gotos to tools/loop_locals.py's border stubs are followed to their real target first
    # (dead_ctx_defs.resolve_stubs): parse_function took them for edges to the instruction after the stubs.
    parsed = {addr: parse_function(lines) for addr, (_, lines) in bodies.items()}
    for addr, (_, lines) in bodies.items():
        dcd.fix_named_calls(parsed[addr], dcd.chunks_of(lines), named, hooked_named)
    # A call through the hook of a hand-written native (SASRT_HOT_HOOK_NATIVE: memcpy, memset, memmove, the Direct3D
    # constant writers) reads what the original reads: the native takes its arguments, and its guard compares the
    # return and non-volatile registers the two runs produce. Such a call counts as a call of the original. Every
    # other hooked call (localized copies, whose shadow guard compares every register; the port's own hooks) stays
    # unknown: everything live.
    # banjo-nx: its hand-written natives are listed in app/src/cpu/hot/hand.txt (the address first on each line).
    hand = os.path.join(ROOT, 'app', 'src', 'cpu', 'hot', 'hand.txt')
    natives = set(int(m.group(1), 16) for m in re.finditer(r'^([0-9A-Fa-f]{8})\b',
                                                             open(hand, encoding='utf-8').read(), re.M))
    for nodes in parsed.values():
        for node in nodes:
            if node.call and not node.call[1] and node.call[0] in natives:
                node.call = (node.call[0], True)
    print('leaf_dead_stores: %d functions, %d guest instructions; %d functions have an address outside direct calls' % (
        len(parsed), sum(len(v) for v in parsed.values()), len(taken)))
    reasons = collections.Counter(r for why in taken.values() for r in why)
    print('  found as: ' + ', '.join('%s %d' % kv for kv in reasons.most_common()))

    # 1. UE: the registers a function may read before writing them, through its callees, to a fixed point.
    summary = {}
    for addr, nodes in parsed.items():
        undefined = forward_undefined(nodes)
        local = 0
        calls = []
        for node, state in zip(nodes, undefined):
            local |= node.use & state
            if node.call:
                calls.append((node.call, state))
        summary[addr] = (local, calls)
    ue = {addr: s[0] for addr, s in summary.items()}
    callers_of = collections.defaultdict(set)
    for addr, (_, calls) in summary.items():
        for (callee, known), _ in calls:
            callers_of[callee].add(addr)
    work = set(summary)
    while work:
        addr = work.pop()
        local, calls = summary[addr]
        new = local
        for (callee, known), state in calls:
            new |= (ue.get(callee, ALL) if known else ALL) & state
        if new != ue[addr]:
            ue[addr] = new
            work |= callers_of[addr]

    # 2. Per call site: live after it, as (A, T): A with nothing live at the caller's exits, T the registers that can
    #    reach an exit unwritten. Live after = A | (LiveOut(caller) & T).
    def use_of(node):
        if node.call:
            callee, known = node.call
            return node.use | (ue.get(callee, ALL) if known else ALL)
        return node.use

    sites = collections.defaultdict(list)          # callee -> [(caller, A, T)]
    tails = collections.defaultdict(set)           # callee -> callers that tail-call it
    direct = collections.Counter()
    for addr, nodes in parsed.items():
        if not any(node.call for node in nodes):
            continue
        live_a = backward(nodes, use_of, 0)
        live_t = backward(nodes, lambda node: 0, ALL)
        for i, node in enumerate(nodes):
            if not node.call:
                continue
            callee, known = node.call
            direct[callee] += 1
            if not known:
                continue
            if node.tail:
                tails[callee].add(addr)
            if not node.tail or node.succ:
                out_a = 0
                out_t = ALL if (node.exit and not node.tail) else 0
                for s in node.succ:
                    out_a |= live_a[s]
                    out_t |= live_t[s]
                sites[callee].append((addr, out_a, out_t))

    # 3. LiveOut to a fixed point; ALL for every function with an address outside direct calls or with no caller.
    live_out = {}
    for addr, nodes in parsed.items():
        if addr in taken:
            live_out[addr] = ALL
        elif not direct[addr]:
            # Nobody calls it directly and its address is nowhere: a jump thunk whose callers the generator sends
            # straight to the target (thunk_calls.py) is unreached and passes nothing on; anything else might be
            # reached in a way this analysis cannot see.
            thunk = len(nodes) == 4 and nodes[3].tail
            live_out[addr] = 0 if thunk else ALL
        else:
            live_out[addr] = 0
    unknown_calls = set()
    for addr, nodes in parsed.items():
        for node in nodes:
            if node.call and not node.call[1]:
                unknown_calls.add(node.call[0])
    for addr in unknown_calls:
        if addr in live_out:
            live_out[addr] = ALL
    callees_of = collections.defaultdict(set)
    for callee, lst in sites.items():
        for caller, _, _ in lst:
            callees_of[caller].add(callee)
    for callee, callers in tails.items():
        for caller in callers:
            callees_of[caller].add(callee)
    work = set(addr for addr in parsed if live_out[addr] != ALL)
    while work:
        addr = work.pop()
        if live_out[addr] == ALL:
            continue
        new = live_out[addr]
        for caller, out_a, out_t in sites.get(addr, ()):
            new |= out_a | (live_out.get(caller, ALL) & out_t)
        for caller in tails.get(addr, ()):
            new |= live_out.get(caller, ALL)
        if new != live_out[addr]:
            live_out[addr] = new
            work |= callees_of[addr]

    # Why the leaf functions' callers keep everything: the first reason found per leaf.
    why = collections.Counter()
    for addr, (path, lines) in bodies.items():
        if not any('REX_LEAF_' in l for l in lines):
            continue
        if live_out[addr] != ALL:
            why['analysed'] += 1
        elif addr in taken:
            why['address taken'] += 1
        elif not direct[addr]:
            why['no direct caller'] += 1
        elif addr in unknown_calls:
            why['called as a hooked sub_X'] += 1
        else:
            why['everything live after a call site'] += 1
    print('  leaf functions: ' + ', '.join('%s %d' % kv for kv in why.most_common()))

    # 4. The leaf write-backs.
    stores = dead = funcs_with = 0
    by_reg = collections.Counter()
    per_function = {}
    rewrite = {}
    for addr, (path, lines) in bodies.items():
        keep = live_out[addr] | ALWAYS | ~VOLATILE
        text = '\n'.join(lines)
        found = LEAF_STORE.findall(text)
        if not found:
            continue
        stores += len(found)
        gone = sorted({reg for _, reg in found if not (regs(reg) & keep)})
        if gone:
            funcs_with += 1
            per_function[addr] = gone
            dead += sum(1 for _, reg in found if reg in gone)
            for reg in gone:
                by_reg[reg[0]] += 1
            rewrite.setdefault(path, {})[addr] = set(gone)
    print('leaf_dead_stores: %d leaf write-backs in the tree; %d of them (in %d functions) write a register no caller '
          'can read: %d general, %d float register write-backs per function' % (
              stores, dead, funcs_with, by_reg['r'], by_reg['f']))
    if a.list:
        with open(a.list, 'w') as f:
            for addr in sorted(per_function):
                f.write('sub_%08X %s live-out %s\n' % (addr, ' '.join(per_function[addr]), ' '.join(
                    reg_name(b) for b in range(64) if (live_out[addr] >> b) & 1 and (VOLATILE >> b) & 1)))
    if a.check:
        return
    install(a.gen, bodies, rewrite)


MARKER = '// rexglue ports: leaf write-backs no caller can read (tools/leaf_dead_stores.py)'
END = '// (end of the macros of tools/leaf_dead_stores.py)\n'
MACROS = MARKER + '''
#ifndef REX_LEAF_DEAD_R
#if defined(REX_LEAF_DEAD_KEEP) || defined(REX_LEAF_LOCALS_OFF)
#define REX_LEAF_DEAD_R(name, reg) REX_LEAF_STORE(name, reg)
#define REX_LEAF_DEAD_F(name, reg) REX_LEAF_STORE(name, reg)
#elif defined(REX_LEAF_DEAD_POISON)
#define REX_LEAF_DEAD_R(name, reg) (ctx.reg.u64 = 0xDEADBEEFDEADBEEFull)
#define REX_LEAF_DEAD_F(name, reg) (ctx.reg.u64 = 0x7FF4DEADBEEF0000ull)
#else
#define REX_LEAF_DEAD_R(name, reg) ((void)0)
#define REX_LEAF_DEAD_F(name, reg) ((void)0)
#endif  // REX_LEAF_DEAD_KEEP
#endif  // REX_LEAF_DEAD_R
''' + END


def install(gen, bodies, rewrite):
    """Every leaf write-back as REX_LEAF_STORE again, then the dead ones as REX_LEAF_DEAD_R / _F (a re-run follows
    a changed analysis, e.g. a new hook)."""
    undo = re.compile(r'REX_LEAF_DEAD_[RF]\((\w+), ([rf]\d+)\)')
    changed = 0
    for path in sorted(glob.glob(os.path.join(gen, '*_recomp.*.cpp'))):
        text = open(path, encoding='utf-8').read()
        new = undo.sub(r'REX_LEAF_STORE(\1, \2)', text)
        dead = rewrite.get(path, {})
        if dead:
            out = []
            gone = None
            for line in new.split('\n'):
                m = HEAD.match(line)
                if m:
                    gone = dead.get(int(m.group(1), 16))
                elif gone and 'REX_LEAF_STORE(' in line:
                    line = re.sub(r'REX_LEAF_STORE\((\w+), ([rf]\d+)\)',
                                  lambda s: ('REX_LEAF_DEAD_%s(%s, %s)' % (s.group(2)[0].upper(), s.group(1), s.group(2))
                                             if s.group(2) in gone else s.group(0)), line)
                out.append(line)
            new = '\n'.join(out)
        if new != text:
            changed += 1
            open(path, 'w', encoding='utf-8', newline='\n').write(new)
    pch = glob.glob(os.path.join(gen, '*_pch.h'))[0]
    text = open(pch, encoding='utf-8').read()
    if MACROS not in text:
        anchor = '#define REX_LOAD_U8(x)'
        if MARKER in text:
            start = text.index(MARKER)
            text = text[:start] + MACROS + text[text.index(END, start) + len(END):]
        elif anchor in text:
            text = text.replace(anchor, MACROS + anchor, 1)
        else:
            sys.exit('ERROR (post-codegen patch): leaf_dead_stores: no REX_LOAD_U8 in %s' % pch)
        open(pch, 'w', encoding='utf-8', newline='\n').write(text)
    print('leaf_dead_stores: %d files written' % changed)


if __name__ == '__main__':
    main()
