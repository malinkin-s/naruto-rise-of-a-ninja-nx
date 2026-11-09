/* See guest_memory_switch.h for the design and the reason behind each decision. */

#if defined(__SWITCH__)

#include "guest_memory_switch.h"

#include <malloc.h>
#include <stdio.h>
#include <string.h>
#include <switch.h>

#include <algorithm>
#include <map>
#include <set>
#include <atomic>
#include <mutex>
#include <vector>

namespace {

constexpr size_t kPageSize  = 0x1000;
/*
 * Large chunks are requested 2 MB aligned, so the kernel can use block descriptors instead of a
 * page table.
 */
constexpr size_t kBlockSize = 0x200000;

/* sa2-nx (2026-11-05, from kameo-nx): banjo_window_blocks, see RexGmInit. */
bool g_window_blocks = true;

constexpr size_t AlignDown(size_t v, size_t a) { return v & ~(a - 1); }
constexpr size_t AlignUp(size_t v, size_t a) { return (v + a - 1) & ~(a - 1); }

/* A committed chunk: heap backing, its code alias (the shadow), and the span of the mapping it covers. */
struct Chunk {
    size_t offset;      /* offset in the mapping */
    size_t length;
    void*  backing;     /* from the heap. Inaccessible after mapping it as code */
    void*  shadow;      /* the codeAlias: always RW, a back door */
};

/* A view: a span of the window that mirrors the mapping from `offset`. */
struct View {
    uint8_t* base;
    size_t   offset;
    size_t   length;
};

/* A span already mapped in this operation, so it can be undone if another fails. */
struct Span {
    size_t   win_off;
    uint8_t* src;
    size_t   len;
};

/*
 * The window size, without the lock
 *
 * InGuestWindow() is called on every fault (tens of thousands per second in a race) and only needs
 * to know whether the address falls inside the window. Reading it from State meant taking the global
 * lock, the same one the mappings use, and in the profile the thread that faulted most spent 22.8%
 * of its time in svcArbitrateLock because of this.
 *
 * base and size are set once in RexGmInit and only change again in RexGmShutdown, so an atomic copy
 * is enough and cannot get out of sync.
 */
std::atomic<size_t> g_size_fast{0};

/*
 * The base goes in its own atomic and is published after the size. That way, if a thread sees the
 * base, the size is already set: the other way round (as it used to be) the window could be seen
 * half-initialized, with a valid base and size 0, and then InGuestWindow said no and a legitimate
 * guest fault ended in a fatal stop.
 */
std::atomic<uint8_t*> g_base_fast{nullptr};

struct State {
    /*
     * Exclusive lock, and it cannot be replaced by a reader/writer one.
     *
     * shared_mutex was tried and it hung the game. The idea was sound on paper: the three calls of
     * the fault path only read, so they could run concurrently. But the performance profiler suspends
     * threads to sample them (svcSetThreadActivity in switch_perf.cpp) and then takes this same lock
     * to read the memory counters.
     *
     * With shared_mutex that is fatal: libstdc++ gives writers preference, so if a thread holding the
     * shared lock is suspended, the first writer to arrive queues up, and all following readers queue
     * behind it. The whole process stops. It hung exactly like that in a test: all 17 threads idle and
     * the profiler unable to write a single report.
     *
     * What did pay off from that attempt is in exception_handler_switch.cpp: asking once per fault
     * instead of five times. That reduces lock traffic without changing how it blocks.
     */
    std::mutex mutex;
    uint8_t* base = nullptr;
    size_t   size = 0;
    VirtmemReservation* reservation = nullptr;

    std::vector<View> views;
    /* chunks sorted by offset: allows finding the one that covers an offset */
    std::map<size_t, Chunk> chunks;
    /*
     * Logical permissions per page of the window, keyed by offset from base.
     * Only pages that are not REX_GM_WRITE are stored; REX_GM_WRITE is the common
     * case, so the table stays small. A page with an entry here is unmapped from
     * the window, whether it is committed or not.
     */
    std::map<size_t, RexGmAccess> protection;
    /*
     * Which (view index, chunk offset) pairs are mapped. A chunk is not mapped into
     * all five views when it is committed: it enters each view the first time it is
     * accessed there. The real ceiling on Horizon is the process limit on mappable
     * memory, and mapping too much exhausts it.
     */
    std::set<std::pair<size_t, size_t>> view_mapped;

    size_t   committed = 0;
    size_t   mapped = 0;
    uint32_t last_result = 0;
};

State& S() {
    static State s;
    return s;
}

// sa2-nx (2026-10-20): banjo-nx's emulator changes in this file (Proc, EagerViews and their uses), as banjo-nx has them.
// banjo-nx (2026-10-17): hbloader passes the process handle; an emulator (Ryujinx) runs NROs without a loader, so
// there is none, and the current-process pseudo-handle stands in for it.
Handle Proc() {
  const Handle h = envGetOwnProcessHandle();
  return h != INVALID_HANDLE ? h : CUR_PROCESS_HANDLE;
}

/*
 * banjo-nx (2026-10-17): without a loader (the same test) the views are mapped when a chunk is committed, not on the
 * first access: an emulator (Ryujinx) does not deliver data aborts to the homebrew's exception handler, so the fault
 * that RexGmFaultIn answers on a console ends the process there. A console always has the loader's handle and keeps
 * the lazy views (the process limit on mappable memory, see RexGmCommit).
 */
bool EagerViews() {
  static const bool eager = envGetOwnProcessHandle() == INVALID_HANDLE;
  return eager;
}

bool Intersect(size_t a, size_t al, size_t b, size_t bl, size_t* lo, size_t* hi) {
    const size_t l = a > b ? a : b;
    const size_t ea = a + al, eb = b + bl;
    const size_t h = ea < eb ? ea : eb;
    if (l >= h) return false;
    *lo = l;
    *hi = h;
    return true;
}

/* Finds the chunk that contains an offset of the mapping. */
Chunk* ChunkAt(State& s, size_t offset) {
    auto it = s.chunks.upper_bound(offset);
    if (it == s.chunks.begin()) return nullptr;
    --it;
    Chunk& c = it->second;
    return (offset >= c.offset && offset < c.offset + c.length) ? &c : nullptr;
}

/* The view that contains a window address. */
const View* ViewFor(State& s, uint64_t addr) {
    for (const View& v : s.views) {
        const uint64_t lo = reinterpret_cast<uint64_t>(v.base);
        if (addr >= lo && addr < lo + v.length) return &v;
    }
    return nullptr;
}

RexGmAccess AccessOf(State& s, size_t page_off) {
    auto it = s.protection.find(page_off);
    return it == s.protection.end() ? REX_GM_WRITE : it->second;
}

/* Is there committed backing behind this window address? */
bool IsCommittedWindowAddress(State& s, uint64_t addr) {
    const View* v = ViewFor(s, addr);
    if (!v) return false;
    const size_t off = v->offset + static_cast<size_t>(addr - reinterpret_cast<uint64_t>(v->base));
    return ChunkAt(s, off) != nullptr;
}

/*
 * Unmaps [win_off, win_off+len) from the window, skipping pages with logical
 * protection, which are already unmapped. `src` is the shadow address that
 * corresponds to win_off.
 *
 * Walk: `it` always points to the first protected page >= cur. Keys are
 * page-aligned and increasing, so skipping a protected page and advancing the
 * iterator keeps that invariant, and the loop always makes progress.
 */
/*
 * Read-only page: try it, and if it is refused, go back to unmapping
 *
 * Why. Watching writes by unmapping the page has an expensive side effect: the
 * guest cannot read from it either, and every read is an exception. Measured in
 * a race: 108,000 emulated reads per second at about 9 us each, which is
 * practically the whole core of the main thread.
 *
 * With the page read-only, watching works the same (the write faults and the
 * handler services it) but reads are free.
 *
 * Why it is not a given. svcSetProcessMemoryPermission only accepts memory whose
 * state allows permission changes. The shadow is mapped with
 * svcMapProcessCodeMemory, which does allow it (it is already used there, with
 * Perm_Rw). The views are mapped with svcMapProcessMemory, and whether Horizon
 * allows it there too is not documented anywhere.
 *
 * So it is tried once. The first page that needs watching is tried with
 * permissions; if the kernel refuses, that is recorded and from then on pages
 * are unmapped as before. Nothing is left half done: if the call fails, it has
 * not changed anything.
 */
enum class ReadOnly { kNoTry, kSi, kNo };
ReadOnly g_read_only = ReadOnly::kNoTry;

/* Returns true if the page was protected through permissions. */
bool ProtectWithPermissions(uint8_t* page, bool read_only) {
    if (g_read_only == ReadOnly::kNo) return false;

    const Result rc = svcSetProcessMemoryPermission(
        Proc(), reinterpret_cast<u64>(page), kPageSize, read_only ? Perm_R : Perm_Rw);
    if (R_FAILED(rc)) {
        if (g_read_only == ReadOnly::kNoTry) {
            g_read_only = ReadOnly::kNo;  // do not try again
        }
        return false;
    }
    g_read_only = ReadOnly::kSi;
    return true;
}
void UnmapWindowRange(State& s, size_t win_off, uint8_t* src, size_t len) {
    if (g_read_only == ReadOnly::kSi) {
        /* No holes here: everything was mapped, watched or not. */
        if (R_SUCCEEDED(svcUnmapProcessMemory(s.base + win_off, Proc(),
                                              reinterpret_cast<u64>(src), len))) {
            s.mapped -= len;
        }
        return;
    }
    const size_t end = win_off + len;
    size_t cur = win_off;
    auto it = s.protection.lower_bound(cur);
    while (cur < end) {
        if (it != s.protection.end() && it->first == cur) {
            cur += kPageSize;
            ++it;
            continue;
        }
        const size_t stop = (it != s.protection.end() && it->first < end) ? it->first : end;
        if (R_SUCCEEDED(svcUnmapProcessMemory(s.base + cur, Proc(),
                                              reinterpret_cast<u64>(src + (cur - win_off)),
                                              stop - cur))) {
            s.mapped -= stop - cur;
        }
        cur = stop;
    }
}

/*
 * When watched pages are read-only instead of unmapped, the whole range is mapped
 * at once and the watched pages then get their permission lowered. Simpler and
 * faster than skipping them.
 */
bool MapWindowRangeReadOnly(State& s, size_t win_off, uint8_t* src, size_t len) {
    const Result rc =
        svcMapProcessMemory(s.base + win_off, Proc(), reinterpret_cast<u64>(src), len);
    if (R_FAILED(rc)) {
        s.last_result = rc;
        return false;
    }
    s.mapped += len;
    for (auto it = s.protection.lower_bound(win_off);
         it != s.protection.end() && it->first < win_off + len; ++it) {
        ProtectWithPermissions(s.base + it->first, true);
    }
    return true;
}

/*
 * Maps [win_off, win_off+len) honoring the logical protection. If a call fails,
 * it undoes what this call had mapped and returns false: it never leaves a range
 * half mapped.
 */
bool MapWindowRange(State& s, size_t win_off, uint8_t* src, size_t len) {
    if (g_read_only == ReadOnly::kSi) {
        return MapWindowRangeReadOnly(s, win_off, src, len);
    }
    const size_t end = win_off + len;
    size_t cur = win_off;
    auto it = s.protection.lower_bound(cur);
    while (cur < end) {
        if (it != s.protection.end() && it->first == cur) {
            cur += kPageSize;
            ++it;
            continue;
        }
        const size_t stop = (it != s.protection.end() && it->first < end) ? it->first : end;
        const Result rc = svcMapProcessMemory(s.base + cur, Proc(),
                                              reinterpret_cast<u64>(src + (cur - win_off)),
                                              stop - cur);
        if (R_FAILED(rc)) {
            s.last_result = rc;
            /*
             * The unmap walks the same way as this loop, so it removes exactly what was
             * mapped, no more and no less.
             */
            UnmapWindowRange(s, win_off, src, cur - win_off);
            return false;
        }
        s.mapped += stop - cur;
        cur = stop;
    }
    return true;
}

/*
 * Maps the range [offset, offset+length) of a chunk into every view that covers
 * it. This is where the 360 mirrors come from.
 *
 * All or nothing: if it fails in one view, it undoes the previous ones. The
 * alternative (leaving a view unmapped and carrying on) would make every access
 * to it be emulated one by one by the exception handler: it would work, but at a
 * fraction of the speed and without any warning. That is exactly the bug the
 * first version had.
 */
bool ViewIndexFor(State& s, uint64_t addr, size_t* out) {
    for (size_t i = 0; i < s.views.size(); i++) {
        const uint64_t lo = reinterpret_cast<uint64_t>(s.views[i].base);
        if (addr >= lo && addr < lo + s.views[i].length) { *out = i; return true; }
    }
    return false;
}

/* Maps a chunk into one view: the view of the faulting access. */
bool MapChunkIntoView(State& s, size_t view_index, const Chunk& c) {
    const View& v = s.views[view_index];
    size_t lo, hi;
    if (!Intersect(c.offset, c.length, v.offset, v.length, &lo, &hi)) return false;
    const size_t win_off = static_cast<size_t>(v.base - s.base) + (lo - v.offset);
    uint8_t* src = static_cast<uint8_t*>(c.shadow) + (lo - c.offset);
    if (!MapWindowRange(s, win_off, src, hi - lo)) return false;
    s.view_mapped.insert({view_index, c.offset});
    return true;
}

void UnmapChunkFromViews(State& s, const Chunk& c) {
    for (size_t i = 0; i < s.views.size(); i++) {
        auto it = s.view_mapped.find({i, c.offset});
        if (it == s.view_mapped.end()) continue;  /* never entered this view */
        const View& v = s.views[i];
        size_t lo, hi;
        if (!Intersect(c.offset, c.length, v.offset, v.length, &lo, &hi)) continue;
        const size_t win_off = static_cast<size_t>(v.base - s.base) + (lo - v.offset);
        uint8_t* src = static_cast<uint8_t*>(c.shadow) + (lo - c.offset);
        UnmapWindowRange(s, win_off, src, hi - lo);
        s.view_mapped.erase(it);
    }
}

void ReleaseChunk(const Chunk& c) {
    svcUnmapProcessCodeMemory(Proc(), reinterpret_cast<u64>(c.shadow),
                              reinterpret_cast<u64>(c.backing), c.length);
    free(c.backing);
}

}  // namespace

extern "C" {

uint8_t* RexGmInit(size_t size) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (s.base) return s.base;

    /*
     * sa2-nx (2026-11-05, from kameo-nx, found by the Torchlight port): the second argument of virtmemFindAslr is a
     * guard, not an alignment. So the window was never on a 2 MB boundary, its 2 MB chunks never lined up with their
     * physical addresses, and the kernel used 4 KB pages for all of the game's memory. 2 MB more is asked for and the
     * base rounded up.
     */
    virtmemLock();
    {
        const size_t extra = g_window_blocks ? kBlockSize : 0;
        const uintptr_t found = reinterpret_cast<uintptr_t>(virtmemFindAslr(size + extra, kBlockSize));
        if (found) s.base = reinterpret_cast<uint8_t*>(g_window_blocks ? AlignUp(found, kBlockSize) : found);
    }
    if (s.base) s.reservation = virtmemAddReservation(s.base, size);
    virtmemUnlock();

    if (!s.base || !s.reservation) {
        s.base = nullptr;
        return nullptr;
    }
    s.size = size;
    g_size_fast.store(size, std::memory_order_release);
    g_base_fast.store(s.base, std::memory_order_release);
    return s.base;
}

void RexGmShutdown(void) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);

    for (auto& kv : s.chunks) {
        UnmapChunkFromViews(s, kv.second);
        ReleaseChunk(kv.second);
    }
    s.chunks.clear();
    s.views.clear();
    s.protection.clear();
    s.committed = 0;
    s.mapped = 0;

    if (s.reservation) {
        virtmemLock();
        virtmemRemoveReservation(s.reservation);
        virtmemUnlock();
        s.reservation = nullptr;
    }
    s.base = nullptr;
    s.size = 0;
    /*
     * Reverse order from startup: the base is cleared first, so nobody gets in with
     * a size that is no longer valid.
     */
    g_base_fast.store(nullptr, std::memory_order_release);
    g_size_fast.store(0, std::memory_order_release);
}

uint8_t* RexGmBase(void) { return g_base_fast.load(std::memory_order_acquire); }

size_t RexGmSize(void) { return g_size_fast.load(std::memory_order_acquire); }

bool RexGmWindowToOffset(uint64_t window_address, size_t* offset_out) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;
    const View* v = ViewFor(s, window_address);
    if (!v) return false;
    if (offset_out) {
        *offset_out =
            v->offset + static_cast<size_t>(window_address - reinterpret_cast<uint64_t>(v->base));
    }
    return true;
}

size_t RexGmCommittedBytes(void) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    return s.committed;
}

size_t RexGmChunkCount(void) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    return s.chunks.size();
}

size_t RexGmMappedBytes(void) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    return s.mapped;
}

int RexGmProtectionMode(void) {
    switch (g_read_only) {
        case ReadOnly::kSi: return 1;
        case ReadOnly::kNo: return 2;
        default: return 0;
    }
}

uint32_t RexGmLastResult(void) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    return s.last_result;
}

bool RexGmAddView(uint8_t* base, size_t offset, size_t length) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;
    if (base < s.base || static_cast<size_t>(base - s.base) + length > s.size)
        return false;  /* outside the reserved window */

    const View v{base, offset, length};

    /*
     * Nothing is mapped here: what is already committed enters this view the first
     * time it is touched.
     */
    s.views.push_back(v);
    if (EagerViews()) {
        /* banjo-nx: no faults to map it later (EagerViews): every committed chunk this view covers, now. */
        const size_t vi = s.views.size() - 1;
        for (const auto& [off, c] : s.chunks) {
            size_t lo, hi;
            if (Intersect(c.offset, c.length, v.offset, v.length, &lo, &hi))
                MapChunkIntoView(s, vi, c);
        }
    }
    return true;
}

bool RexGmCommit(size_t offset, size_t length, RexGmAccess access) {
    /*
     * Memory is always committed accessible. Restricting permissions is the job of
     * RexGmProtect, which works on window addresses and not on mapping offsets (and
     * it has to, because the same offset can be mirrored in several windows with
     * different permissions: the 360 does exactly that).
     *
     * `access` stays in the signature because the natural caller is
     * AllocFixed(kCommit, access), and removing it would invite forgetting to apply
     * it. Pages that already had logical protection keep it.
     */
    (void)access;
    if (length == 0) return true;

    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;

    /*
     * Committed in whole kBlockSize granules, not just the requested pages. Guest
     * heaps with 64 KB pages grow one page at a time, and a chunk per request (each
     * a code alias plus one mapping per view that touches it) exhausts the kernel's
     * memory blocks long before the mapping limit: measured, 0xCE01 (2001-0103) on a
     * 64 KB commit with only 329 MB of backing. The extra pages are backing only;
     * guest-level commit state is still kept by the heaps in xmemory.cpp.
     */
    const size_t begin = AlignDown(offset, kBlockSize);
    const size_t end   = std::min(AlignUp(offset + length, kBlockSize), s.size);

    size_t cur = begin;
    while (cur < end) {
        if (Chunk* existing = ChunkAt(s, cur)) {
            cur = existing->offset + existing->length;
            continue;
        }

        /* Where the gap ends: the next chunk, or the end. */
        size_t gap_end = end;
        auto sig = s.chunks.upper_bound(cur);
        if (sig != s.chunks.end() && sig->second.offset < gap_end)
            gap_end = sig->second.offset;

        const size_t sz = gap_end - cur;
        const size_t align = (sz >= kBlockSize && (cur & (kBlockSize - 1)) == 0)
                                 ? kBlockSize : kPageSize;

        void* backing = memalign(align, sz);
        if (!backing) {
            s.last_result = REX_GM_ERR_NOMEM;
            return false;
        }
        memset(backing, 0, sz);

        virtmemLock();
        void* shadow = virtmemFindCodeMemory(sz, align);
        Result rc = shadow ? svcMapProcessCodeMemory(Proc(), reinterpret_cast<u64>(shadow),
                                                     reinterpret_cast<u64>(backing), sz)
                           : 0;
        virtmemUnlock();

        if (!shadow) {
            free(backing);
            s.last_result = REX_GM_ERR_NOCODEVA;
            return false;
        }
        if (R_FAILED(rc)) {
            free(backing);
            s.last_result = rc;
            return false;
        }

        /* The code alias starts without write access; it has to be opened. */
        rc = svcSetProcessMemoryPermission(Proc(), reinterpret_cast<u64>(shadow), sz, Perm_Rw);
        if (R_FAILED(rc)) {
            svcUnmapProcessCodeMemory(Proc(), reinterpret_cast<u64>(shadow),
                                      reinterpret_cast<u64>(backing), sz);
            free(backing);
            s.last_result = rc;
            return false;
        }

        /*
         * Not mapped into the views: each view gets it on first access
         * (RexGmFaultIn). Mapping it into all five 360 views multiplies by five the
         * use of the process limit on mappable memory.
         */
        const Chunk c{cur, sz, backing, shadow};
        s.chunks[cur] = c;
        s.committed += sz;
        if (EagerViews()) {
            /* banjo-nx: no faults to map it later (EagerViews): into every view that covers it, now. */
            for (size_t vi = 0; vi < s.views.size(); vi++) {
                size_t lo, hi;
                if (Intersect(c.offset, c.length, s.views[vi].offset, s.views[vi].length, &lo, &hi))
                    MapChunkIntoView(s, vi, c);
            }
        }

        cur = gap_end;
    }
    return true;
}

bool RexGmFaultIn(uint64_t window_address) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;

    size_t vi = 0;
    if (!ViewIndexFor(s, window_address, &vi)) return false;

    /*
     * Page with logical protection: it is unmapped on purpose (write watching, MMIO,
     * read-only). Mapping the chunk would not bring it in (protected pages are
     * skipped), so answering yes would leave the fault repeating forever. The next
     * steps of the handler deal with it.
     */
    const size_t win_off =
        static_cast<size_t>(window_address - reinterpret_cast<uint64_t>(s.base));
    if (s.protection.find(AlignDown(win_off, kPageSize)) != s.protection.end()) return false;

    const size_t off = s.views[vi].offset +
                       static_cast<size_t>(window_address -
                                           reinterpret_cast<uint64_t>(s.views[vi].base));
    Chunk* c = ChunkAt(s, off);
    if (!c) return false;                                       /* not committed */
    if (s.view_mapped.count({vi, c->offset}) != 0) return false; /* already there */
    return MapChunkIntoView(s, vi, *c);
}

bool RexGmDecommit(size_t offset, size_t length) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;

    const size_t begin = AlignDown(offset, kPageSize);
    const size_t end   = AlignUp(offset + length, kPageSize);

    for (auto it = s.chunks.begin(); it != s.chunks.end();) {
        const Chunk c = it->second;
        /*
         * Only chunks entirely contained in the range are freed: splitting a chunk
         * would also mean splitting its backing, and the backing is a single heap
         * allocation. Partial chunks stay committed, which is conservative but correct.
         */
        if (c.offset >= begin && c.offset + c.length <= end) {
            UnmapChunkFromViews(s, c);
            ReleaseChunk(c);
            s.committed -= c.length;
            it = s.chunks.erase(it);
        } else {
            ++it;
        }
    }
    return true;
}

bool RexGmProtect(uint8_t* address, size_t length, RexGmAccess access, RexGmAccess* out_old) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;

    const uint64_t addr  = reinterpret_cast<uint64_t>(address);
    const uint64_t wbase = reinterpret_cast<uint64_t>(s.base);
    if (addr < wbase || addr + length > wbase + s.size) return false;

    const size_t begin = AlignDown(static_cast<size_t>(addr - wbase), kPageSize);
    const size_t end   = AlignUp(static_cast<size_t>(addr - wbase) + length, kPageSize);

    if (out_old) *out_old = AccessOf(s, begin);

    /*
     * banjo-nx (2026-10-17): without a loader (EagerViews: an emulator) the pages keep full access. Ryujinx delivers no
     * data abort, so a protected page ends the process at its next access instead of being watched; and its
     * svcSetProcessMemoryPermission throws on the views rather than refusing (the deko3d renderer's first emulator
     * runs). A console takes the path below.
     */
    if (EagerViews()) return true;

    const bool must_be = (access == REX_GM_WRITE);

    /*
     * Fast path, and the common one: asking for full access on a range that has no
     * protected page. AllocFixed(kCommit) does it for every allocation of the game
     * heap, and without this it would walk the range page by page (131,072
     * iterations for the 512 MB of physical memory) to do nothing.
     */
    if (must_be) {
        auto it = s.protection.lower_bound(begin);
        if (it == s.protection.end() || it->first >= end) return true;
    }

    for (size_t p = begin; p < end; p += kPageSize) {
        const bool was = (AccessOf(s, p) == REX_GM_WRITE);

        if (was != must_be) {
            /*
             * The view is looked up per page: a range can cross the boundary
             * between two views with different offsets.
             */
            if (const View* v = ViewFor(s, wbase + p)) {
                const size_t off_mapping =
                    v->offset + (p - static_cast<size_t>(v->base - s.base));
                size_t vi = 0;
                Chunk* c = ChunkAt(s, off_mapping);
                /*
                 * If the chunk has not entered this view yet, there is nothing to map
                 * or unmap: the permission is recorded and the first access will bring
                 * the chunk in with the right permission already.
                 */
                const bool in_view = c != nullptr && ViewIndexFor(s, wbase + p, &vi) &&
                                      s.view_mapped.count({vi, c->offset}) != 0;
                if (in_view) {
                    const u64 src = reinterpret_cast<u64>(
                        static_cast<uint8_t*>(c->shadow) + (off_mapping - c->offset));
                    /*
                     * Permissions are tried first, which keeps the page readable. If the
                     * kernel refuses, it falls back to the usual unmap. ProtectWithPermissions
                     * remembers whether it works.
                     */
                    if (!ProtectWithPermissions(s.base + p, was)) {
                        const Result rc =
                            was ? svcUnmapProcessMemory(s.base + p, Proc(), src, kPageSize)
                                   : svcMapProcessMemory(s.base + p, Proc(), src, kPageSize);
                        if (R_FAILED(rc)) {
                            s.last_result = rc;
                            return false;
                        }
                        if (was) s.mapped -= kPageSize;
                        else s.mapped += kPageSize;
                    }
                }
                /*
                 * Not committed: nothing to map, but the permission is still recorded
                 * and RexGmCommit will honor it on commit.
                 */
            }
        }

        if (must_be) s.protection.erase(p);
        else s.protection[p] = access;
    }
    return true;
}

bool RexGmQueryProtect(uint8_t* address, size_t* length, RexGmAccess* out_access) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return false;

    const uint64_t addr  = reinterpret_cast<uint64_t>(address);
    const uint64_t wbase = reinterpret_cast<uint64_t>(s.base);
    if (addr < wbase || addr >= wbase + s.size) return false;

    const size_t begin = AlignDown(static_cast<size_t>(addr - wbase), kPageSize);

    /*
     * An uncommitted page is reported as having no access, even if its logical
     * permission is the default one.
     *
     * This matters a lot: after a fault, the SDK's MMIO handler queries this, and if
     * it sees the page as accessible it concludes that another thread already
     * unprotected it and retries the instruction. If the page does not really exist,
     * the retry faults again... forever. A silent hang.
     */
    if (!IsCommittedWindowAddress(s, wbase + begin)) {
        if (out_access) *out_access = REX_GM_NONE;
        if (length) *length = kPageSize;
        return true;
    }

    const RexGmAccess a = AccessOf(s, begin);
    if (out_access) *out_access = a;

    /*
     * On input *length is the maximum to walk (0 = one page); on output, the size of
     * the committed range with the same permission.
     */
    size_t max = (length && *length) ? *length : kPageSize;
    if (begin + max > s.size) max = s.size - begin;

    size_t p = begin;
    const size_t cap = begin + max;
    while (p < cap && AccessOf(s, p) == a && IsCommittedWindowAddress(s, wbase + p))
        p += kPageSize;
    if (length) *length = p - begin;
    return true;
}

void* RexGmShadowFor(uint64_t window_address) {
    State& s = S();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.base) return nullptr;

    const View* v = ViewFor(s, window_address);
    if (!v) return nullptr;

    const size_t off_mapping =
        v->offset + static_cast<size_t>(window_address - reinterpret_cast<uint64_t>(v->base));
    Chunk* c = ChunkAt(s, off_mapping);
    if (!c) return nullptr;

    return static_cast<uint8_t*>(c->shadow) + (off_mapping - c->offset);
}

}  // extern "C"

/*
 * sa2-nx (2026-11-05, from kameo-nx): how much the TLB costs, on the console (banjo_tlb_test_s). From the Torchlight port's method: the
 * same number of cache lines in random order, first one to a page over thousands of pages, then packed into a few pages.
 * Both come mostly from the L2 cache, so the difference is the cost of finding the page. A regular order would measure
 * the prefetcher and the L2 instead. svcQueryPhysicalAddress refuses these mappings, so this is the evidence there is. An
 * emulator's numbers mean nothing here: it only shows that the test runs.
 */
extern "C" char _start;  /* the executable's first instruction; __start__ is never relocated */

namespace {

constexpr size_t kChaseLines = 2048;

/*
 * Which line of a page the i-th page uses. It has to look random: physically contiguous memory (which blocks need) indexes
 * the 2 MB, 16-way L2 by address bits 6 to 16, and the first version's (i % 64) made bits 12 to 16 follow from bits 6 to 11.
 * That put 2048 lines in 64 sets, 32 to a set: every load missed the L2, and the test measured RAM instead of the TLB
 * (+112 to +153 ns on the console, in all but the ret test and a view of 1024 lines).
 */
size_t LineOfPage(size_t i) { return static_cast<size_t>((u64(i + 1) * 0x9E3779B97F4A7C15ull) >> 58); }

/* ns per load, the best of 8 passes after a warm-up. Each load's address depends on the last load, so they can't overlap. */
double ChaseNs(const uintptr_t* addrs, size_t n) {
    u64 best = ~u64(0);
    u64 dep = 0;
    for (int pass = 0; pass < 9; pass++) {
        const u64 start = armGetSystemTick();
        for (size_t i = 0; i < n; i++) {
            u64 value;
            __asm__ volatile(
                "ldr %[v], [%[a], %[d]]\n"
                "and %[d], %[v], xzr\n"
                : [v] "=&r"(value), [d] "+r"(dep)
                : [a] "r"(addrs[i])
                : "memory");
        }
        const u64 ticks = armGetSystemTick() - start;
        if (pass > 0 && ticks < best) best = ticks;
    }
    return double(armTicksToNs(best)) / double(n);
}

/* The same for instruction fetches: every address holds a ret, so a call does nothing but fetch it. */
double FetchNs(const uintptr_t* addrs, size_t n) {
    u64 best = ~u64(0);
    for (int pass = 0; pass < 9; pass++) {
        const u64 start = armGetSystemTick();
        for (size_t i = 0; i < n; i++) reinterpret_cast<void (*)()>(addrs[i])();
        const u64 ticks = armGetSystemTick() - start;
        if (pass > 0 && ticks < best) best = ticks;
    }
    return double(armTicksToNs(best)) / double(n);
}

void Shuffle(std::vector<uintptr_t>& a) {
    u64 x = 0x9E3779B97F4A7C15ull;
    for (size_t i = a.size(); i > 1; i--) {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        std::swap(a[i - 1], a[x % i]);
    }
}

void EmitPair(void (*emit)(const char*), const char* what, double scattered, double grouped, size_t ns, size_t ng) {
    char line[160];
    snprintf(line, sizeof(line), "[tlb] %s: scattered %.1f ns, grouped %.1f ns, +%.1f ns (%zu and %zu lines)", what, scattered,
             grouped, scattered - grouped, ns, ng);
    emit(line);
}

void CodeAddresses(u64 va, u64 size, bool rets, std::vector<uintptr_t>& scattered, std::vector<uintptr_t>& grouped) {
    const size_t pages = size / kPageSize;
    const size_t stride = std::max<size_t>(1, pages / kChaseLines);
    constexpr u32 kRet = 0xD65F03C0;
    for (size_t i = 0; i < kChaseLines && i * stride < pages; i++) {
        const u64 page = va + i * stride * kPageSize;
        const u64 line = page + LineOfPage(i) * 64;
        if (!rets) {
            scattered.push_back(line);
            continue;
        }
        for (u64 at = line; at < page + kPageSize; at += 4) {
            if (*reinterpret_cast<const u32*>(at) == kRet) {
                scattered.push_back(at);
                break;
            }
        }
    }
    const u64 middle = va + (pages / 2) * kPageSize;
    const u64 end = va + size;
    if (!rets) {
        for (u64 at = middle; at + 64 <= end && grouped.size() < kChaseLines; at += 64) grouped.push_back(at);
        return;
    }
    /* At most one to a line, so that they don't share a fetch. */
    for (u64 line = middle; line + 64 <= end && line < middle + 512 * kPageSize && grouped.size() < kChaseLines; line += 64) {
        for (u64 at = line; at < line + 64; at += 4) {
            if (*reinterpret_cast<const u32*>(at) == kRet) {
                grouped.push_back(at);
                break;
            }
        }
    }
}

}  // namespace

extern "C" void RexGmSetWindowBlocks(bool on) { g_window_blocks = on; }

extern "C" void RexGmLatencyTest(void (*emit)(const char*)) {
    State& s = S();
    std::vector<uintptr_t> scattered, grouped;
    scattered.reserve(kChaseLines);
    grouped.reserve(kChaseLines);
    char line[160];
    snprintf(line, sizeof(line), "[tlb] window at 0x%llX: %s a 2 MB boundary", (unsigned long long)RexGmBase(),
             (reinterpret_cast<uintptr_t>(RexGmBase()) & (kBlockSize - 1)) ? "NOT on" : "on");
    emit(line);

    const size_t view_count = [&] {
        std::lock_guard<std::mutex> lock(s.mutex);
        return s.views.size();
    }();
    for (size_t vi = 0; vi < view_count; vi++) {
        scattered.clear();
        grouped.clear();
        double far = 0, near = 0;
        size_t view_start = 0;
        {
            /* The lock keeps every page of the lists mapped while they are read, so none of this can fault. */
            std::lock_guard<std::mutex> lock(s.mutex);
            if (vi >= s.views.size()) break;
            const View& v = s.views[vi];
            view_start = static_cast<size_t>(v.base - s.base);
            for (const auto& kv : s.chunks) {
                const Chunk& c = kv.second;
                if (scattered.size() >= kChaseLines) break;
                if (!s.view_mapped.count({vi, c.offset})) continue;
                size_t lo, hi;
                if (!Intersect(c.offset, c.length, v.offset, v.length, &lo, &hi)) continue;
                const size_t win = view_start + (lo - v.offset);
                for (size_t off = 0; off + kPageSize <= hi - lo && scattered.size() < kChaseLines; off += kPageSize) {
                    if (s.protection.count(win + off)) continue;
                    const uintptr_t page = reinterpret_cast<uintptr_t>(s.base) + win + off;
                    scattered.push_back(page + LineOfPage(scattered.size()) * 64);
                    for (size_t l = 0; l < 64 && grouped.size() < kChaseLines; l++) grouped.push_back(page + l * 64);
                }
            }
            if (scattered.size() < kChaseLines / 2) continue;  /* too little of this view is in use */
            Shuffle(scattered);
            Shuffle(grouped);
            far = ChaseNs(scattered.data(), scattered.size());
            near = ChaseNs(grouped.data(), grouped.size());
        }
        char what[48];
        snprintf(what, sizeof(what), "game memory, view at +0x%zX", view_start);
        EmitPair(emit, what, far, near, scattered.size(), grouped.size());
    }

    MemoryInfo text = {}, ro = {};
    u32 page_info = 0;
    if (R_FAILED(svcQueryMemory(&text, &page_info, reinterpret_cast<u64>(&_start)))) return;
    scattered.clear();
    grouped.clear();
    CodeAddresses(text.addr, text.size, false, scattered, grouped);
    Shuffle(scattered);
    Shuffle(grouped);
    { const double f = ChaseNs(scattered.data(), scattered.size()), n = ChaseNs(grouped.data(), grouped.size());
      EmitPair(emit, "text, read", f, n, scattered.size(), grouped.size()); }
    scattered.clear();
    grouped.clear();
    CodeAddresses(text.addr, text.size, true, scattered, grouped);
    Shuffle(scattered);
    Shuffle(grouped);
    { const double f = FetchNs(scattered.data(), scattered.size()), n = FetchNs(grouped.data(), grouped.size());
      EmitPair(emit, "text, run", f, n, scattered.size(), grouped.size()); }
    if (R_SUCCEEDED(svcQueryMemory(&ro, &page_info, text.addr + text.size)) && ro.size >= 64 * kPageSize) {
        scattered.clear();
        grouped.clear();
        CodeAddresses(ro.addr, ro.size, false, scattered, grouped);
        Shuffle(scattered);
        Shuffle(grouped);
        const double f = ChaseNs(scattered.data(), scattered.size()), n = ChaseNs(grouped.data(), grouped.size());
        EmitPair(emit, "read-only data", f, n, scattered.size(), grouped.size());
    }
}

#endif /* __SWITCH__ */
