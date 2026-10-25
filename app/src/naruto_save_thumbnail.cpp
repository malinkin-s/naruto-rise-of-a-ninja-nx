// The save thumbnail's race (from jorjbarbosa/naruto-rise-recomp app/src/save_thumbnail.cpp and engine_free.cpp,
// GPL-3.0; their analysis, kept below as they wrote it).
//
// Race on the save thumbnail.
//
// The render task of the capture (sub_8211D878, this[14] = the thumbnail
// structure) runs D3DXSaveTextureToFileInMemory on the reduced capture and
// calls the compression sub_82583C28(thumb): free(thumb[3]),
// thumb[3] = malloc(...), and zlib writes the thumbnail into thumb[3] + 4; at
// the end, thumb[4] = 1 (ready). The thread that writes the save reads
// thumb[3]/thumb[2] and, when done, calls sub_82583D28(thumb), which frees
// thumb[1] and thumb[3] and clears them, then frees the structure.
//
// The task can capture twice for one save: the main thread's per-frame copy
// of the task (820F01D8: enabled = pending, this[14] = this[15]) may run once
// more before the render thread's first capture clears the pending flag, and
// the task then captures again one render frame later. If the second capture
// meets a ready thumbnail still being written, its compression frees and
// reallocates thumb[3] while the save writer frees the same chunk in the
// middle of zlib. If the save writer has already freed the structure
// (sub_82653600, or sub_82651520 at once when a save is already running), the
// capture writes the thumbnail into a freed 32-byte chunk: the allocator's
// free list (trap 22, then the chunk handed out twice), a light map node or an
// interface object. Either way the game's heap is corrupted.
//
// One capture per request: the request (820ECD38, slot 124 of the renderer's
// table, called by sub_82651F88 with the new structure) is recorded, the
// capture runs only for the thumbnail of the last request that was neither
// captured nor freed, and any other capture returns as if it had finished
// (the two fields the function clears on entry and the return 1 of its
// success path). The first capture cannot meet the free: the game hands the
// thumbnail to the save writer only after thumb[4] = 1, the capture's last
// write (sub_82652210). With no request seen, a capture over a ready,
// unconsumed thumbnail (thumb[4] = 1 and thumb[3] != 0) is not redone.


#include <atomic>
#include <cstdint>
#include <cstring>

#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>

namespace {

// Guest words (big-endian) by address; the hooks get `base` from the recompiled code's arguments.
inline uint32_t Load32(const uint8_t* base, uint32_t a) {
  uint32_t v;
  std::memcpy(&v, base + a, 4);
  return __builtin_bswap32(v);
}
inline void Store32(uint8_t* base, uint32_t a, uint32_t v) {
  v = __builtin_bswap32(v);
  std::memcpy(base + a, &v, 4);
}

extern "C" void __imp__sub_8211D878(PPCContext& __restrict, uint8_t*);
extern "C" void __imp__sub_820ECD38(PPCContext& __restrict, uint8_t*);

std::atomic<uint32_t> skipped_captures{0};
std::atomic<uint32_t> captures{0};

// The last request as one word, its number (0 before any) above its
// thumbnail, so a free and a new request on other threads never mix one
// request's thumbnail with another's number; the number of the request whose
// thumbnail was freed and of the one whose capture ran.
std::atomic<uint64_t> request{0};
std::atomic<uint32_t> freed_seq{0};
std::atomic<uint32_t> captured_seq{0};

enum class Verdict { kUnknown, kCapture, kAgain, kFreed, kOther };

// Whether the capture of `thumb` may run, with the request it answers.
Verdict Decide(uint32_t thumb, uint32_t* seq) {
  const uint64_t last = request.load(std::memory_order_acquire);
  *seq = uint32_t(last >> 32);
  if (!*seq) return Verdict::kUnknown;
  if (thumb != uint32_t(last)) return Verdict::kOther;
  if (freed_seq.load(std::memory_order_acquire) == *seq) return Verdict::kFreed;
  if (captured_seq.load(std::memory_order_acquire) == *seq) return Verdict::kAgain;
  return Verdict::kCapture;
}

}  // namespace

namespace {
void NoteFree(uint32_t pointer) {
  if (!pointer) return;
  const uint64_t last = request.load(std::memory_order_acquire);
  if (pointer == uint32_t(last)) freed_seq.store(uint32_t(last >> 32), std::memory_order_release);
}
}  // namespace

REX_HOOK_RAW(sub_8211D878) {
  const uint32_t self = ctx.r3.u32;
  const uint32_t thumb = Load32(base, self + 56);
  uint32_t seq = 0;
  const Verdict verdict = thumb ? Decide(thumb, &seq) : Verdict::kUnknown;
  const char* skip = verdict == Verdict::kAgain   ? "already captured for its request"
                     : verdict == Verdict::kFreed ? "freed before its capture"
                     : verdict == Verdict::kOther ? "not the thumbnail of the last request"
                                                  : nullptr;
  if (!skip && verdict == Verdict::kUnknown && thumb && Load32(base, thumb + 16) == 1 &&
      Load32(base, thumb + 12) != 0)
    skip = "still in use";
  if (skip) {
    Store32(base, self + 8, 0);
    Store32(base, self + 60, 0);
    ctx.r3.u64 = 1;
    const uint32_t count = skipped_captures.fetch_add(1) + 1;
    if (count <= 32)
      REXLOG_INFO("[naruto] save thumbnail capture skipped: thumbnail {:08X} {} (#{})", thumb, skip, count);
    return;
  }
  __imp__sub_8211D878(ctx, base);
  if (verdict == Verdict::kCapture && ctx.r3.u32 == 1) {
    captured_seq.store(seq, std::memory_order_release);
    const uint32_t count = captures.fetch_add(1) + 1;
    if (count <= 32) REXLOG_INFO("[naruto] save thumbnail captured: thumbnail {:08X}, request #{}", thumb, seq);
  }
}

// The request of a capture (820ECD38, the thumbnail in r3): recorded before
// the task sees it.
REX_HOOK_RAW(sub_820ECD38) {
  static std::atomic<uint32_t> requests{0};
  uint32_t seq = requests.fetch_add(1) + 1;
  if (!seq) seq = requests.fetch_add(1) + 1;  // 0 means no request.
  request.store(uint64_t(seq) << 32 | ctx.r3.u32, std::memory_order_release);
  __imp__sub_820ECD38(ctx, base);
}

// The engine's free (sub_820C0018: the kind in r3, the memory in r4, the heap in r5): a requested thumbnail freed
// before its capture is not captured (the PC base's engine_free.cpp).
extern "C" void __imp__sub_820C0018(PPCContext& __restrict, uint8_t*);
REX_HOOK_RAW(sub_820C0018) {
  NoteFree(ctx.r4.u32);
  __imp__sub_820C0018(ctx, base);
}
