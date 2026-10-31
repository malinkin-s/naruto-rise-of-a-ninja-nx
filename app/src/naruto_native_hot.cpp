// Native hot functions for T_820F02C0 (D3D state and draw submission).
// sub_820FD5F8: vertex declaration stream mapping and hash table lookup.
// Profile prof_r1 showed sub_820FD5F8 alone is ~30% of T_820F02C0 CPU time.
#include <atomic>
#include <cstdint>
#include <cstring>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>

REXCVAR_DEFINE_BOOL(naruto_native_decl_hook, true, "Naruto/CPU",
                    "Native fast-path for sub_820FD5F8 with vertex declaration memo cache")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#include <rex/ppc/func.h>

namespace {

inline uint32_t Load32(const uint8_t* base, uint32_t a) {
  uint32_t v;
  std::memcpy(&v, base + a, 4);
  return __builtin_bswap32(v);
}

inline void Store32(uint8_t* base, uint32_t a, uint32_t v) {
  v = __builtin_bswap32(v);
  std::memcpy(base + a, &v, 4);
}

inline uint64_t Load64(const uint8_t* base, uint32_t a) {
  uint64_t v;
  std::memcpy(&v, base + a, 8);
  return __builtin_bswap64(v);
}

inline void Store64(uint8_t* base, uint32_t a, uint64_t v) {
  v = __builtin_bswap64(v);
  std::memcpy(base + a, &v, 8);
}

struct DeclLookupCache {
  uint32_t key = 0;
  uint32_t table = 0;
  uint32_t node = 0;
};
// 4-entry MRU cache: handles alternating mesh sequences without hash/list traversal.
// Sub_820FD5F8 is called only from T_820F02C0 (the single D3D draw submission thread).
static DeclLookupCache s_decl_cache[4]{};
static uint32_t s_decl_hand = 0;

extern "C" void __imp__sub_820FD5F8(PPCContext& __restrict, uint8_t*);
extern "C" void __imp__sub_820F03A0(PPCContext& __restrict, uint8_t*);
extern "C" void __imp__sub_820FA098(PPCContext& __restrict, uint8_t*);

// Fast-path: checks if stream state already matches in device registers, eliding the call to sub_820FA098.
inline void BindStreamFast(uint8_t* base, uint32_t stream_idx, uint32_t stream_arg, PPCContext& ctx) {
  constexpr uint32_t kDeviceState = 0x82C170D8;
  const uint32_t r29 = stream_arg ? Load32(base, stream_arg + 32) : 0;
  const uint32_t r28 = stream_arg ? Load32(base, stream_arg + 36) : 0;
  const uint32_t r27 = stream_arg ? Load32(base, stream_arg + 44) : 0;

  const uint32_t off2107 = (stream_idx + 2107) * 4;
  const uint32_t off2111 = (stream_idx + 2111) * 4;
  const uint32_t off2109 = (stream_idx + 2109) * 4;

  if (Load32(base, kDeviceState + off2107) == r29 &&
      Load32(base, kDeviceState + off2111) == r27 &&
      Load32(base, kDeviceState + off2109) == r28) {
    return;
  }

  ctx.r3.u64 = kDeviceState;
  ctx.r4.u64 = stream_idx;
  ctx.r5.u64 = stream_arg;
  __imp__sub_820FA098(ctx, base);
}

}  // namespace

REX_HOOK_RAW(sub_820FD5F8) {
  static const bool use_native = REXCVAR_GET(naruto_native_decl_hook);
  if (!use_native) {
    __imp__sub_820FD5F8(ctx, base);
    return;
  }

  const uint32_t r27_u32 = ctx.r3.u32;
  const uint32_t r30_u32 = ctx.r4.u32;
  const uint32_t table_base = r27_u32 + 24;

  // 1. Hash table lookup for vertex declaration node (64 buckets).
  const uint32_t r30_flags = Load32(base, r30_u32 + 8);
  if (!(r30_flags & 0x80000u)) {
    uint32_t node = 0;
    for (int i = 0; i < 4; ++i) {
      if (s_decl_cache[i].key == r30_u32 && s_decl_cache[i].table == table_base &&
          s_decl_cache[i].node != 0 && Load32(base, s_decl_cache[i].node) == r30_u32) {
        node = s_decl_cache[i].node;
        break;
      }
    }
    if (node == 0) {
      uint32_t h = (r30_u32 >> 6) ^ r30_u32;
      h = (h >> 6) ^ r30_u32;
      h = ((h >> 12) ^ h) & 0x3Fu;
      const uint32_t bucket_head = Load32(base, table_base + (h + 9) * 4);
      uint32_t curr = bucket_head;
      while (curr != 0) {
        if (Load32(base, curr) == r30_u32) {
          node = curr;
          break;
        }
        curr = Load32(base, curr + 12);
      }
      s_decl_cache[s_decl_hand & 3] = {r30_u32, table_base, node};
      s_decl_hand++;
    }
    Store32(base, table_base + 296, node);
  }

  // 2. State at 0x82C170D8 + 8416
  constexpr uint32_t kDeviceState = 0x82C170D8;
  const uint32_t r10_val = Load32(base, r30_u32 + 12);
  const uint32_t r11_val = r10_val ? Load32(base, r10_val + 40) : 0;
  if (Load32(base, kDeviceState + 8416) != r11_val) {
    if (r11_val != 0) {
      const uint32_t ptr_table = Load32(base, Load32(base, 0x82C0F008) + 16);
      Store32(base, ptr_table + 11812, r11_val);
      uint64_t flags = Load64(base, ptr_table + 16);
      flags |= 0x80000ULL;
      Store64(base, ptr_table + 16, flags);
    }
    Store32(base, kDeviceState + 8416, r11_val);
  }

  // 3. State at 0x82C170D8 + 8452
  const uint32_t r11_off28 = Load32(base, r30_u32 + 28);
  const uint32_t r4_val = r11_off28 ? Load32(base, r11_off28 + 32) : 0;
  if (Load32(base, kDeviceState + 8452) != r4_val) {
    ctx.r3.u64 = kDeviceState;
    ctx.r4.u64 = r4_val;
    __imp__sub_820F03A0(ctx, base);
  }

  // 4. Stream bindings via BindStreamFast (skips sub_820FA098 if streams already match)
  const uint32_t stream_count = Load32(base, r30_u32 + 24);
  uint32_t stream_idx = 0;
  if (static_cast<int32_t>(stream_count) > 0) {
    const uint32_t stream_ptrs = r30_u32 + 16;
    for (; stream_idx < stream_count; ++stream_idx) {
      const uint32_t stream_arg = Load32(base, stream_ptrs + stream_idx * 4);
      BindStreamFast(base, stream_idx, stream_arg, ctx);
    }
  }
  for (; stream_idx < 2; ++stream_idx) {
    BindStreamFast(base, stream_idx, 0, ctx);
  }

  // 5. Tail update and indirect vtable call
  const uint32_t r11_off3068 = Load32(base, r27_u32 + 3068);
  Store32(base, r27_u32 + 3060, r30_u32);
  if (r11_off3068 != 0) {
    uint64_t val = Load64(base, r30_u32 + 64);
    val &= 0xFFFFFFFFFFFFFF0FULL;
    Store64(base, r30_u32 + 64, val);
  }

  // vtable[6] call: 0x82C259E0 + (6 * 4) = 0x82C259F8
  const uint32_t vfunc = Load32(base, 0x82C259E0 + 24);
  ctx.r3.u64 = r27_u32;
  ctx.r4.u64 = r30_u32;

  static PPCFunc* s_vfunc_cached = nullptr;
  static uint32_t s_vfunc_target = 0;
  if (s_vfunc_target != vfunc || !s_vfunc_cached) {
    s_vfunc_cached = rex::runtime::ResolveIndirectFunction(vfunc);
    s_vfunc_target = vfunc;
  }
  if (s_vfunc_cached) {
    s_vfunc_cached(ctx, base);
  }

  Store32(base, r27_u32 + 3060, 0);
  Store32(base, r27_u32 + 320, 0);
}
