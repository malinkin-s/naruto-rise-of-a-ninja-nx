/**
 * @file        naruto_math_hooks.cpp
 * @brief       Native ARM64 NEON vectorization hooks for hot math functions
 *
 * Vectorized replacement for sub_8254EF68, the #1 hottest function on Core 0
 * in Naruto: Rise of a Ninja (matrix multiplication, ~4.1% of main thread time).
 */

#include <cmath>
#include <cstdint>
#include <cstring>

#include <rex/hook.h>
#include <rex/ppc/context.h>
#include <rex/ppc/func.h>

#include "cpu/sa2_enhancements.h"

#if defined(__aarch64__) || defined(_M_ARM64)
#include <arm_neon.h>
#else
#ifndef SIMDE_ENABLE_NATIVE_ALIASES
#define SIMDE_ENABLE_NATIVE_ALIASES
#endif
#include <simde/arm/neon.h>
#endif

SA2_ENHANCEMENT(g_neon_matrix_mul, naruto_cpu_neon_matrix_mul, sa2::enh::kCpu, true,
                "Native ARM64 NEON matrix multiplication (sub_8254EF68)");

namespace {

// Loads a 128-bit vector of 4 single-precision floats stored in big-endian format
// and converts to host little-endian single precision vector.
[[gnu::always_inline]] static inline float32x4_t LoadBEVector(const void* ptr) noexcept {
  const uint8x16_t raw = vld1q_u8(reinterpret_cast<const uint8_t*>(ptr));
  return vreinterpretq_f32_u8(vrev32q_u8(raw));
}

// Converts a host little-endian float vector to big-endian and stores to guest memory.
[[gnu::always_inline]] static inline void StoreBEVector(void* ptr, float32x4_t vec) noexcept {
  const uint8x16_t rev = vrev32q_u8(vreinterpretq_u8_f32(vec));
  vst1q_u8(reinterpret_cast<uint8_t*>(ptr), rev);
}

// Loads a single 32-bit big-endian IEEE-754 float
[[gnu::always_inline]] static inline float LoadBEFloat(const void* ptr) noexcept {
  uint32_t u;
  std::memcpy(&u, ptr, 4);
  u = __builtin_bswap32(u);
  float res;
  std::memcpy(&res, &u, 4);
  return res;
}

}  // namespace

// Declare original recompiled symbol for fallback
REX_EXTERN(__imp__sub_8254EF68);

/**
 * sub_8254EF68: 4x4 matrix multiplication with flag calculation.
 *
 * In guest registers:
 *   ctx.r3.u32: destination matrix pointer (dst)
 *   ctx.r4.u32: source matrix 1 (m1)
 *   ctx.r5.u32: source matrix 2 (m2)
 *
 * Each matrix is 64 bytes of 16 big-endian IEEE-754 floats, followed by uint32 flags at +64:
 *   If ((flags1 | flags2) & 8) == 0:
 *     Affine 4x3 multiplication (row 3 assumed [0, 0, 0, 1]).
 *   Else:
 *     Projective/non-affine multiplication (delegates to original __imp__sub_8254EF68).
 */
REX_HOOK_RAW(sub_8254EF68) {
  if (!g_neon_matrix_mul.active) [[unlikely]] {
    __imp__sub_8254EF68(ctx, base);
    return;
  }

  const uint32_t dst_addr = ctx.r3.u32;
  const uint32_t m1_addr = ctx.r4.u32;
  const uint32_t m2_addr = ctx.r5.u32;

  const uint8_t* const p1 = base + m1_addr;
  const uint8_t* const p2 = base + m2_addr;
  uint8_t* const pd = base + dst_addr;

  const uint32_t flags1 = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(p1 + 64));
  const uint32_t flags2 = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(p2 + 64));

  // If non-affine / projective (bit 8 set), delegate to original implementation
  if (((flags1 | flags2) & 8) != 0) [[unlikely]] {
    __imp__sub_8254EF68(ctx, base);
    return;
  }

  g_neon_matrix_mul.UseSampled();

  // Load rows of matrix 2 (B)
  float32x4_t b0 = LoadBEVector(p2 + 0);
  float32x4_t b1 = LoadBEVector(p2 + 16);
  float32x4_t b2 = LoadBEVector(p2 + 32);
  float32x4_t b3 = LoadBEVector(p2 + 48);

  // Guarantee affine structure for matrix 2: column 3 is [0, 0, 0, 1]^T
  b0 = vsetq_lane_f32(0.0f, b0, 3);
  b1 = vsetq_lane_f32(0.0f, b1, 3);
  b2 = vsetq_lane_f32(0.0f, b2, 3);
  b3 = vsetq_lane_f32(1.0f, b3, 3);

  // Row 0 (following PowerPC accumulator sequence for numerical precision parity)
  const float32x4_t a0 = LoadBEVector(p1 + 0);
  float32x4_t r0 = vmulq_laneq_f32(b1, a0, 1);
  r0 = vfmaq_laneq_f32(r0, b0, a0, 0);
  r0 = vfmaq_laneq_f32(r0, b2, a0, 2);

  // Row 1
  const float32x4_t a1 = LoadBEVector(p1 + 16);
  float32x4_t r1 = vmulq_laneq_f32(b1, a1, 1);
  r1 = vfmaq_laneq_f32(r1, b0, a1, 0);
  r1 = vfmaq_laneq_f32(r1, b2, a1, 2);

  // Row 2
  const float32x4_t a2 = LoadBEVector(p1 + 32);
  float32x4_t r2 = vmulq_laneq_f32(b1, a2, 1);
  r2 = vfmaq_laneq_f32(r2, b0, a2, 0);
  r2 = vfmaq_laneq_f32(r2, b2, a2, 2);

  // Row 3 (translation: (a3[1]*b1 + a3[0]*b0 + a3[2]*b2) + b3)
  const float32x4_t a3 = LoadBEVector(p1 + 48);
  float32x4_t r3 = vmulq_laneq_f32(b1, a3, 1);
  r3 = vfmaq_laneq_f32(r3, b0, a3, 0);
  r3 = vfmaq_laneq_f32(r3, b2, a3, 2);
  r3 = vaddq_f32(r3, b3);

  // Compute output flags:
  // bit 2 (0x4): preserved if set on either input
  // bit 1 (0x2): set if translation vector (Tx, Ty, Tz) is non-zero
  uint32_t dst_flags = 0;
  if ((flags1 | flags2) & 4) {
    dst_flags |= 4;
  }

  const uint32_t tx = vgetq_lane_u32(vreinterpretq_u32_f32(r3), 0);
  const uint32_t ty = vgetq_lane_u32(vreinterpretq_u32_f32(r3), 1);
  const uint32_t tz = vgetq_lane_u32(vreinterpretq_u32_f32(r3), 2);
  if (((tx | ty | tz) & 0x7FFFFFFF) != 0) {
    dst_flags |= 2;
  }

  // Store output to destination (safe against dst == m1 or dst == m2 aliasing)
  StoreBEVector(pd + 0, r0);
  StoreBEVector(pd + 16, r1);
  StoreBEVector(pd + 32, r2);
  StoreBEVector(pd + 48, r3);
  *reinterpret_cast<uint32_t*>(pd + 64) = __builtin_bswap32(dst_flags);

#if defined(__SWITCH__)
  // Store card invalidation for Renut vertex/index caching
  *(uint8_t*)(base + (dst_addr >> 12)) = 0;
  *(uint8_t*)(base + ((dst_addr + 64) >> 12)) = 0;
#endif
}

// =============================================================================
// Octree Element Traversal Fastpaths (sub_825E2838 & sub_825E2298)
//
// These high-frequency loops account for ~7.0% of Core 0 CPU time in movement.
// The native C++ hooks eliminate REX_LOOP_BARRIER() memory clobbers and PowerPC
// register bouncing, executing the loops directly with AArch64 registers.
// =============================================================================

SA2_ENHANCEMENT(g_octree_traversal_opt, naruto_cpu_octree_traversal_opt, sa2::enh::kCpu, true,
                "Native C++ octree node traversal loops (sub_825E2838 and sub_825E2298)");

REX_EXTERN(__imp__sub_825E2838);
REX_EXTERN(__imp__sub_825E24C0);

/**
 * sub_825E2838: Traverses active elements of an octree node, sets flag bit 0x4,
 * and conditionally dispatches elements with bit 0x40000 to sub_825E24C0.
 *
 * In guest registers:
 *   ctx.r3.u32: node address
 *   ctx.r4.u32: argument 1 (passed as r3 to sub_825E24C0)
 *   ctx.r5.u32: argument 2 (passed as r4 to sub_825E24C0)
 */
REX_HOOK_RAW(sub_825E2838) {
  if (!g_octree_traversal_opt.active) [[unlikely]] {
    __imp__sub_825E2838(ctx, base);
    return;
  }

  const uint32_t node_va = ctx.r3.u32;
  const uint64_t arg1 = ctx.r4.u64;
  const uint64_t arg2 = ctx.r5.u64;

  const uint8_t* const node_ptr = base + node_va;
  const uint32_t count = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(node_ptr + 8));
  if (count == 0) return;

  const uint32_t array_va = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(node_ptr + 4));
  const uint32_t* const items = reinterpret_cast<const uint32_t*>(base + array_va);

  for (uint32_t i = 0; i < count; ++i) {
    const uint32_t item_va = __builtin_bswap32(items[i]);
    uint32_t* const flags_ptr = reinterpret_cast<uint32_t*>(base + item_va + 4);
    uint32_t flags = __builtin_bswap32(*flags_ptr);
    flags |= 4;
    *flags_ptr = __builtin_bswap32(flags);
    if (flags & 0x40000) {
      ctx.r3.u64 = arg1;
      ctx.r4.u64 = arg2;
      ctx.r5.u64 = item_va;
      __imp__sub_825E24C0(ctx, base);
    }
  }
}

REX_EXTERN(__imp__sub_825E2298);
REX_EXTERN(__imp__sub_825E1EF0);

/**
 * sub_825E2298: Traverses elements of an octree node and calls sub_825E1EF0
 * for any element whose flags do NOT have bit 0x10200004 set.
 *
 * In guest registers:
 *   ctx.r3.u32: node address
 *   ctx.f1.f64: floating-point parameter (preserved and forwarded)
 */
REX_HOOK_RAW(sub_825E2298) {
  if (!g_octree_traversal_opt.active) [[unlikely]] {
    __imp__sub_825E2298(ctx, base);
    return;
  }

  const uint32_t node_va = ctx.r3.u32;
  const double f1_val = ctx.f1.f64;

  const uint8_t* const node_ptr = base + node_va;
  const uint32_t count = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(node_ptr + 8));
  if (count == 0) return;

  const uint32_t array_va = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(node_ptr + 4));
  const uint32_t* const items = reinterpret_cast<const uint32_t*>(base + array_va);

  for (uint32_t i = 0; i < count; ++i) {
    const uint32_t item_va = __builtin_bswap32(items[i]);
    const uint32_t flags = __builtin_bswap32(*reinterpret_cast<const uint32_t*>(base + item_va + 4));
    if ((flags & 0x10200004) == 0) {
      ctx.r3.u64 = item_va;
      ctx.f1.f64 = f1_val;
      __imp__sub_825E1EF0(ctx, base);
    }
  }
}
