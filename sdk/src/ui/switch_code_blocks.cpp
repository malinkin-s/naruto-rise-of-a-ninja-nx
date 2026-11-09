/*
 * sa2-nx (2026-11-05, from kameo-nx v1.0.1): the NRO's code and read-only data on 2 MB blocks.
 *
 * The idea and its measurements come from the Torchlight port (src/torchlight_code_blocs.cpp there, which was not
 * available here: this is written from its description). There, instruction fetches away from the TLB cost +115 ns
 * with 4 KB pages and +7 ns with blocks, reads +81 ns and +5 ns, and combat ran 2 to 4 % faster.
 *
 * hbloader reads the NRO to the start of its heap and maps it with svcMapProcessCodeMemory at an arbitrary address, so
 * the virtual and physical addresses don't line up modulo 2 MB and the kernel has to use 4 KB pages. Here the same
 * bytes are copied to a part of the heap that does line up, and mapped at the same virtual address. Nothing else
 * changes: no pointer moves, and the code doesn't know.
 *
 * What makes this safe, or would make it unsafe:
 *  - The code can't unmap itself, so the swap runs from a page of its own (kStub), and only uses registers and the
 *    stack: the data segment and the stack stay mapped.
 *  - Nothing else may run the code during the swap. Priority 101 is the first constructor: no thread of ours exists yet,
 *    and libnx's startup (__appInit, before the constructors) starts none.
 *  - Text and read-only data have no relocations, so a copy made now is the same as the original.
 *  - svcUnmapProcessCodeMemory fails, and changes nothing, unless it is given the pages that are mapped there: the kernel
 *    compares them. A wrong guess at the loader's copy costs nothing and the game runs as before.
 *  - hbloader would abort if the NRO returned to it, because its own unmap would fail. The game never returns to it: every
 *    exit is __nx_applet_exit_mode 1 and __libnx_exit (windowed_app_main_switch.cpp, rex_app.cpp).
 *
 * The cost: the loader's copy can't be given back (it's in the middle of the heap, with .data after it), so the text and
 * read-only data take their size again in memory, about 47 MB here.
 *
 * An emulator runs NROs without a loader, as CodeStatic memory, which can't be unmapped. There the code stays where it is
 * and the swap is tested on pages of its own instead.
 *
 * banjo_code_blocks = false in naruto.toml turns it off. The cvars aren't read yet, so this looks at the file itself; the
 * cvar is in guest_memory_switch.cpp, so the key is known. The built-in defaults can't turn it off.
 */
#if defined(__SWITCH__)

#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <switch.h>

extern "C" {
// The executable's first instruction. Not __start__, an absolute linker symbol that is never relocated (the first build of
// 1.0.1 used it, and the swap left the code where it was).
extern char _start;
extern int __system_argc;
extern char** __system_argv;
}

namespace {

constexpr u64 kBlock = 0x200000;
constexpr u64 kPage = 0x1000;

/* The layout kStub reads. */
struct Segment {
  u64 va;
  u64 old_src;
  u64 new_src;
  u64 size;
  u64 perm;
};
struct Args {
  u32 process;
  u32 count;
  Segment seg[2];
};
static_assert(sizeof(Segment) == 40 && __builtin_offsetof(Args, seg) == 8, "kStub reads this layout");

/*
 * u32 stub(Args*): for each segment, unmap the old copy, map the new one and set its permission. Returns 0, or the
 * kernel's result. If the new copy is refused the old one goes back, so a segment is always mapped when it returns. If
 * that fails too, nothing can run: brk. Assembled by devkitA64's as (data rather than a function, so that no
 * compiler option can add a call to it). 0x78 svcUnmapProcessCodeMemory, 0x77 svcMapProcessCodeMemory,
 * 0x73 svcSetProcessMemoryPermission.
 */
const u32 kStub[] = {
    // stub
    0xa9bd53f3,  //   0: stp x19, x20, [sp, #-48]!
    0xa9015bf5,  //   4: stp x21, x22, [sp, #16]
    0xf90013f7,  //   8: str x23, [sp, #32]
    0xaa0003f3,  //   c: mov x19, x0
    0xb9400274,  //  10: ldr w20, [x19]
    0xb9400675,  //  14: ldr w21, [x19, #4]
    0x91002276,  //  18: add x22, x19, #0x8
    // next
    0x34000595,  //  1c: cbz w21, cc <ok>
    0x2a1403e0,  //  20: mov w0, w20
    0xf94002c1,  //  24: ldr x1, [x22]
    0xf94006c2,  //  28: ldr x2, [x22, #8]
    0xf9400ec3,  //  2c: ldr x3, [x22, #24]
    0xd4000f01,  //  30: svc #0x78
    0x350004e0,  //  34: cbnz w0, d0 <out>
    0x2a1403e0,  //  38: mov w0, w20
    0xf94002c1,  //  3c: ldr x1, [x22]
    0xf9400ac2,  //  40: ldr x2, [x22, #16]
    0xf9400ec3,  //  44: ldr x3, [x22, #24]
    0xd4000ee1,  //  48: svc #0x77
    0x2a0003f7,  //  4c: mov w23, w0
    0x350001c0,  //  50: cbnz w0, 88 <put_back>
    0x2a1403e0,  //  54: mov w0, w20
    0xf94002c1,  //  58: ldr x1, [x22]
    0xf9400ec2,  //  5c: ldr x2, [x22, #24]
    0xf94012c3,  //  60: ldr x3, [x22, #32]
    0xd4000e61,  //  64: svc #0x73
    0x2a0003f7,  //  68: mov w23, w0
    0x340002a0,  //  6c: cbz w0, c0 <done_one>
    0x2a1403e0,  //  70: mov w0, w20
    0xf94002c1,  //  74: ldr x1, [x22]
    0xf9400ac2,  //  78: ldr x2, [x22, #16]
    0xf9400ec3,  //  7c: ldr x3, [x22, #24]
    0xd4000f01,  //  80: svc #0x78
    0x350002e0,  //  84: cbnz w0, e0 <dead>
    // put_back
    0x2a1403e0,  //  88: mov w0, w20
    0xf94002c1,  //  8c: ldr x1, [x22]
    0xf94006c2,  //  90: ldr x2, [x22, #8]
    0xf9400ec3,  //  94: ldr x3, [x22, #24]
    0xd4000ee1,  //  98: svc #0x77
    0x35000220,  //  9c: cbnz w0, e0 <dead>
    0x2a1403e0,  //  a0: mov w0, w20
    0xf94002c1,  //  a4: ldr x1, [x22]
    0xf9400ec2,  //  a8: ldr x2, [x22, #24]
    0xf94012c3,  //  ac: ldr x3, [x22, #32]
    0xd4000e61,  //  b0: svc #0x73
    0x35000160,  //  b4: cbnz w0, e0 <dead>
    0x2a1703e0,  //  b8: mov w0, w23
    0x14000005,  //  bc: b d0 <out>
    // done_one
    0x9100a2d6,  //  c0: add x22, x22, #0x28
    0x510006b5,  //  c4: sub w21, w21, #0x1
    0x17ffffd5,  //  c8: b 1c <next>
    // ok
    0x52800000,  //  cc: mov w0, #0x0
    // out
    0xf94013f7,  //  d0: ldr x23, [sp, #32]
    0xa9415bf5,  //  d4: ldp x21, x22, [sp, #16]
    0xa8c353f3,  //  d8: ldp x19, x20, [sp], #48
    0xd65f03c0,  //  dc: ret
    // dead
    0xd4200000,  //  e0: brk #0x0
};

char g_status[220] = "[code blocks] did not run";

struct CodePage {
  void* heap;
  void* va;
};

/* A page of code from the heap, at a free address of the code region. */
bool MapCodePage(Handle proc, const void* code, size_t size, CodePage* out) {
  void* page = memalign(kPage, kPage);
  if (!page) return false;
  memset(page, 0, kPage);
  memcpy(page, code, size);
  armDCacheFlush(page, kPage);
  virtmemLock();
  void* va = virtmemFindCodeMemory(kPage, kPage);
  Result rc = va ? svcMapProcessCodeMemory(proc, reinterpret_cast<u64>(va), reinterpret_cast<u64>(page), kPage) : 1;
  virtmemUnlock();
  if (R_FAILED(rc)) {
    free(page);
    return false;
  }
  rc = svcSetProcessMemoryPermission(proc, reinterpret_cast<u64>(va), kPage, Perm_Rx);
  if (R_FAILED(rc)) {
    svcUnmapProcessCodeMemory(proc, reinterpret_cast<u64>(va), reinterpret_cast<u64>(page), kPage);
    free(page);
    return false;
  }
  out->heap = page;
  out->va = va;
  return true;
}

void UnmapCodePage(Handle proc, const CodePage& p) {
  svcUnmapProcessCodeMemory(proc, reinterpret_cast<u64>(p.va), reinterpret_cast<u64>(p.heap), kPage);
  free(p.heap);
}

u64 Blocks(u64 va, u64 size) {
  const u64 lo = (va + kBlock - 1) & ~(kBlock - 1);
  const u64 hi = (va + size) & ~(kBlock - 1);
  return hi > lo ? (hi - lo) / kBlock : 0;
}

bool TurnedOffInToml() {
  if (__system_argc < 1 || !__system_argv || !__system_argv[0]) return false;
  const char* nro = __system_argv[0];
  const char* bar = strrchr(nro, '/');
  if (!bar) return false;
  char path[FS_MAX_PATH];
  const char* toml_names[] = {"naruto.toml", "sa2.toml"};
  for (const char* name : toml_names) {
    const int n = snprintf(path, sizeof(path), "%s%.*s%s", strchr(nro, ':') ? "" : "sdmc:",
                           static_cast<int>(bar - nro + 1), nro, name);
    if (n <= 0 || static_cast<size_t>(n) >= sizeof(path)) continue;
    FILE* f = fopen(path, "r");
    if (!f) continue;
    bool off = false;
    char line[256];
    static const char kKey[] = "banjo_code_blocks";
    while (fgets(line, sizeof(line), f)) {
      const char* p = line;
      while (*p == ' ' || *p == '\t') p++;
      if (strncmp(p, kKey, sizeof(kKey) - 1) == 0 && strstr(p, "false")) off = true;
    }
    fclose(f);
    if (off) return true;
  }
  return false;
}

/*
 * No loader: the swap on two pages of its own, the normal path only. The refusals can't be tested here: Ryujinx accepted a
 * wrong old copy and a new copy that isn't heap, then ran the wrong page, although its source says it refuses both
 * (not explained). What the put-back path does has only been read, never run.
 */
void SelfTest(Handle proc) {
  static const u32 kReturns1[] = {0x52800020, 0xd65f03c0};  // mov w0, #1; ret
  static const u32 kReturns2[] = {0x52800040, 0xd65f03c0};  // mov w0, #2; ret
  CodePage stub, code;
  const auto say = [](const char* what) {
    snprintf(g_status, sizeof(g_status), "[code blocks] no loader (an emulator), left where it is; swap self-test: %s", what);
  };
  if (!MapCodePage(proc, kStub, sizeof(kStub), &stub)) return say("FAILED, no page for the swap");
  if (!MapCodePage(proc, kReturns1, sizeof(kReturns1), &code)) return say("FAILED, no page to swap");
  const auto swap = reinterpret_cast<u32 (*)(Args*)>(stub.va);
  const auto run = reinterpret_cast<int (*)()>(code.va);
  if (run() != 1) return say("FAILED, the first page does not run");
  void* second = memalign(kPage, kPage);
  if (!second) return say("FAILED, no second page");
  memset(second, 0, kPage);
  memcpy(second, kReturns2, sizeof(kReturns2));
  armDCacheFlush(second, kPage);
  Args a = {};
  a.process = proc;
  a.count = 1;
  a.seg[0] = {reinterpret_cast<u64>(code.va), reinterpret_cast<u64>(code.heap), reinterpret_cast<u64>(second), kPage,
              Perm_Rx};
  const u32 good = swap(&a);
  const int after_good = run();
  char what[64];
  snprintf(what, sizeof(what), "%s (0x%X, runs %d)", good == 0 && after_good == 2 ? "passed" : "FAILED", good, after_good);
  say(what);
  svcUnmapProcessCodeMemory(proc, reinterpret_cast<u64>(code.va), reinterpret_cast<u64>(second), kPage);
  free(second);
  free(code.heap);
  UnmapCodePage(proc, stub);
}

void Apply(Handle proc) {
  const u64 text_va = reinterpret_cast<u64>(&_start);
  MemoryInfo text = {}, ro = {}, old = {};
  u32 page_info = 0;
  const auto skip = [](const char* why, u64 value) {
    snprintf(g_status, sizeof(g_status), "[code blocks] left where it is: %s (0x%llX)", why,
             static_cast<unsigned long long>(value));
  };
  if (R_FAILED(svcQueryMemory(&text, &page_info, text_va)) || text.addr != text_va || (text.perm & Perm_Rx) != Perm_Rx) {
    return skip("the text is not what was expected", text.addr);
  }
  const u32 text_type = text.type & 0xFF;
  if (text_type != MemType_ModuleCodeStatic && text_type != MemType_ModuleCodeMutable) {
    return skip("the text is not mapped by a loader", text_type);
  }
  if (R_FAILED(svcQueryMemory(&ro, &page_info, text_va + text.size)) || (ro.perm & Perm_Rw) != Perm_R) {
    return skip("the read-only data is not what was expected", ro.perm);
  }
  const u64 total = text.size + ro.size;

  /* The loader's copy: the start of the heap, with the permissions svcMapProcessCodeMemory leaves. */
  u64 heap_base = 0;
  if (R_FAILED(svcGetInfo(&heap_base, InfoType_HeapRegionAddress, CUR_PROCESS_HANDLE, 0)) ||
      R_FAILED(svcQueryMemory(&old, &page_info, heap_base)) || !(old.attr & MemAttr_IsBorrowed)) {
    return skip("the loader's copy is not at the start of the heap", old.attr);
  }

  /*
   * The copy lines up with the code modulo 2 MB. Whole pages are lent to the kernel: the slack keeps the last one clear of
   * the next allocation's header, and the alignment keeps the first clear of this one's. Never freed.
   */
  void* raw = memalign(kBlock, total + kBlock + kPage);
  if (!raw) return skip("no memory for the copy", total);
  const u64 copy = reinterpret_cast<u64>(raw) + ((text_va - reinterpret_cast<u64>(raw)) & (kBlock - 1));
  memcpy(reinterpret_cast<void*>(copy), reinterpret_cast<const void*>(text_va), total);
  armDCacheFlush(reinterpret_cast<void*>(copy), total);

  CodePage stub;
  if (!MapCodePage(proc, kStub, sizeof(kStub), &stub)) {
    free(raw);
    return skip("the swap's page could not be mapped", 0);
  }
  Args a = {};
  a.process = proc;
  a.count = 2;
  a.seg[0] = {text_va, heap_base, copy, text.size, Perm_Rx};
  a.seg[1] = {text_va + text.size, heap_base + text.size, copy + text.size, ro.size, Perm_R};
  const u32 rc = reinterpret_cast<u32 (*)(Args*)>(stub.va)(&a);
  UnmapCodePage(proc, stub);
  if (rc != 0) return skip("the kernel refused the swap", rc);
  snprintf(g_status, sizeof(g_status),
           "[code blocks] text %llu KB and read-only data %llu KB now on a copy in line with 2 MB blocks: room for %llu and "
           "%llu blocks (0x%llX, copy 0x%llX)",
           static_cast<unsigned long long>(text.size >> 10), static_cast<unsigned long long>(ro.size >> 10),
           static_cast<unsigned long long>(Blocks(text_va, text.size)),
           static_cast<unsigned long long>(Blocks(text_va + text.size, ro.size)),
           static_cast<unsigned long long>(text_va), static_cast<unsigned long long>(copy));
}

__attribute__((constructor(101))) void RexCodeBlocksInit() {
  const Handle proc = envGetOwnProcessHandle();
  if (proc == INVALID_HANDLE) {
    SelfTest(CUR_PROCESS_HANDLE);
    return;
  }
  if (TurnedOffInToml()) {
    snprintf(g_status, sizeof(g_status), "[code blocks] off (banjo_code_blocks = false)");
    return;
  }
  Apply(proc);
}

}  // namespace

extern "C" const char* RexCodeBlocksStatus(void) { return g_status; }

#endif  // __SWITCH__
