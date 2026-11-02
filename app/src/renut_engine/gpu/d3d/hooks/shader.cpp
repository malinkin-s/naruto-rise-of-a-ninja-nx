/**
 * @file    gpu/d3d/hooks/shader.cpp
 * @brief   Shader creation. The renderer owns the shader objects: each is a
 *          record keyed to its XenosRecomp cache entry by container hash.
 *
 * The ~150 shaders N&B compiles from HLSL at boot (hcg*ShaderCreateByHlsl)
 * reach D3DDevice_CreateVertexShader/CreatePixelShader too, so a cache miss
 * here is captured to disk for the next shader cache build.
 *
 * Shaders loaded with asset bundles are D3D objects the bundle already holds,
 * set up in place by XGRegisterVertexShader/XGRegisterPixelShader. Those stay
 * guest objects; the host side is kept per object address, keyed by the same
 * container hash.
 */
#include <cstring>
#include <memory>
#include <mutex>
#include <unordered_map>

#include <xxhash.h>
#include <utility>
#include <vector>

#include <rex/hook.h>

#include "renut_engine/gpu/banjo_renut_select.h"
#include <rex/types.h>

#include "renut_engine/gpu/render/draw.h"
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/backend/render_thread.h"
#include "renut_engine/gpu/guest/resources.h"
#include "renut_engine/gpu/render/pipeline.h"
#include "renut_engine/gpu/render/shader_library.h"
#include "renut_engine/gpu/backend/video.h"

using namespace renut::gpu;

namespace {

// Where D3DDevice_CreateVertexShader / CreatePixelShader (0x8264E8B0 /
// 0x8264E6A8) lay out a shader object: the container's virtual part copied
// after the D3D header, and a pointer to its physical part (literal constants
// and microcode). Objects in bundles have the same layout.
constexpr u32 kVertexShaderContainer = 0x368;
constexpr u32 kVertexShaderPhysical = 0x20;
constexpr u32 kPixelShaderContainer = 0x28;
constexpr u32 kPixelShaderPhysical = 0x18;

// Guest shader objects registered in place, by object address. The render
// thread's (State().mutex).
std::unordered_map<u32, std::unique_ptr<ShaderRecord>> g_guest_shaders;

// Recent FindShaderLocked results (two lookups a draw otherwise, one under a
// shared lock). An entry goes when its shader does (ForgetShader): both kinds
// are destroyed on the render thread, the only user, so a memo'd record is
// alive. (Checking the record registry's generation instead missed whenever
// any record came or went, which busy levels do all the time.) State().mutex.
// A miss is kept too (record null): draws keep binding addresses that are no
// shader of the kind (depth-only passes), and those cost a registry lookup and
// a map search a draw. A shader made at an address forgets it first (both are
// in order with the draws on the render thread). va 0 is an empty entry
// (FindShaderLocked never looks it up).
struct ShaderMemo {
  u32 va = 0;
  ShaderRecord *record = nullptr;
};
// A table per kind, a set of four entries per cache line, the most recent
// first. A single direct-mapped table for both kinds had the shaders of a busy
// level (Showdown Town binds hundreds a frame) evicting each other every frame,
// and each miss was a registry lookup and a map search.
constexpr u32 kShaderMemoWays = 4;
constexpr u32 kShaderMemoSetBits = 10;
struct alignas(64) ShaderMemoSet {
  ShaderMemo way[kShaderMemoWays];
};
static_assert(sizeof(ShaderMemoSet) == 64);
ShaderMemoSet g_shader_memo[2][1u << kShaderMemoSetBits];

u32 KindIndex(RecordKind kind) {
  return kind == RecordKind::PixelShader ? 1 : 0;
}

ShaderMemoSet &ShaderMemoSetFor(u32 kind_index, u32 shader_va) {
  return g_shader_memo[kind_index][(shader_va * 0x9E3779B1u) >> (32 - kShaderMemoSetBits)];
}

// The last shader found of each kind: consecutive draws mostly keep their
// shaders, and this is one compare where the memo is a cache miss.
ShaderMemo g_last_shader[2];

void ForgetShader(u32 shader_va) {
  for (u32 kind = 0; kind < 2; ++kind) {
    for (ShaderMemo &memo : ShaderMemoSetFor(kind, shader_va).way) {
      if (memo.va == shader_va)
        memo = {};
    }
    if (g_last_shader[kind].va == shader_va)
      g_last_shader[kind] = {};
  }
}

} // namespace

namespace renut::gpu {

ShaderRecord *FindShaderLocked(u32 shader_va, RecordKind kind) {
  if (!shader_va)
    return nullptr;
  const u32 kind_index = KindIndex(kind);
  ShaderMemo &last = g_last_shader[kind_index];
  if (last.va == shader_va)
    return last.record;
  ShaderMemo *ways = ShaderMemoSetFor(kind_index, shader_va).way;
  u32 hit = 0;
  while (hit < kShaderMemoWays && ways[hit].va != shader_va)
    ++hit;
  ShaderMemo found;
  if (hit < kShaderMemoWays) {
    found = ways[hit];
  } else {
    hit = kShaderMemoWays - 1;  // the least recent goes
    ShaderRecord *record = FindRecord<ShaderRecord>(shader_va, kind);
    if (!record) {
      auto it = g_guest_shaders.find(shader_va);
      record = it != g_guest_shaders.end() && it->second->kind == kind ? it->second.get() : nullptr;
    }
    found = {shader_va, record};
  }
  for (u32 i = hit; i > 0; --i)
    ways[i] = ways[i - 1];
  ways[0] = found;
  last = found;
  return found.record;
}

void ReleaseGuestShaderLocked(u32 shader_va) {
  if (g_guest_shaders.erase(shader_va))
    ForgetShader(shader_va);
}

// sa2-nx (2026-10-20): the game's own vertex declarations, by object address (render thread).
namespace {
std::unordered_map<u32, std::unique_ptr<VertexDeclarationRecord>> g_guest_declarations;
}  // namespace

const VertexDeclarationRecord *FindGuestDeclarationLocked(u32 declaration_va) {
  auto it = g_guest_declarations.find(declaration_va);
  return it != g_guest_declarations.end() ? it->second.get() : nullptr;
}

void ReleaseGuestDeclarationLocked(u32 declaration_va) {
  if (g_guest_declarations.erase(declaration_va))
    ForgetVertexDeclarationLocked(declaration_va);
}

void BuildDeclarationLayout(VertexDeclarationRecord &declaration) {
  declaration.layout =
      BuildHostVertexLayout(declaration.elements.data(), u32(declaration.elements.size()));
  // FNV-1a over what the input layout depends on.
  uint64_t hash = 0xCBF29CE484222325ull;
  auto mix = [&hash](uint64_t v) { hash = (hash ^ v) * 0x100000001B3ull; };
  for (const plume::RenderInputElement &e : declaration.layout.input_elements) {
    mix(e.location);
    mix(uint64_t(e.format));
    mix(e.slotIndex);
    mix(e.alignedByteOffset);
  }
  for (u32 s = 0; s < kMaxVertexStreams; ++s)
    mix(declaration.layout.streams[s].host_stride);
  declaration.layout_hash = hash;
}

const VertexDeclarationRecord *ShaderFetchDeclarationLocked(ShaderRecord &vs) {
  if (vs.fetch_declaration_built)
    return vs.fetch_declaration.get();
  vs.fetch_declaration_built = true;
  if (!vs.entry || !vs.entry->vertexInputCount)
    return nullptr;
  auto declaration = std::make_unique<VertexDeclarationRecord>();
  const ShaderVertexInput *inputs = g_shaderVertexInputs + vs.entry->vertexInputOffset;
  for (u32 i = 0; i < vs.entry->vertexInputCount; ++i) {
    const ShaderVertexInput &input = inputs[i];
    // Stream n's fetch constant is Xenos index 95 - n (d3d::StreamFetchIndex).
    const u32 first_stream_fetch = d3d::kFirstVertexFetchIndex;
    if (input.fetchIndex < first_stream_fetch || input.fetchIndex > 95)
      continue;
    const u32 stream = 95 - input.fetchIndex;
    const u32 type = FetchDeclType(input.format, input.flags & 1, input.flags & 2);
    if (type == kDeclTypeUnused)
      continue;
    GuestVertexElement element{};
    element.Stream = u16(stream);
    element.Offset = u16(input.offsetDwords * 4);
    element.Type = type;
    element.Method = 0;
    element.Usage = input.usage;
    element.UsageIndex = input.usageIndex;
    declaration->elements.push_back(element);
    if (stream < d3d::kMaxStreams && !vs.fetch_strides[stream])
      vs.fetch_strides[stream] = input.strideDwords * 4u;
  }
  if (declaration->elements.empty())
    return nullptr;
  BuildDeclarationLayout(*declaration);
  vs.fetch_declaration = std::move(declaration);
  return vs.fetch_declaration.get();
}

plume::RenderShader *GetHostShader(ShaderRecord *shader) {
  if (!shader || !shader->entry)
    return nullptr;
  // Built already: draws call this under State().mutex, which destruction
  // (DestroyShaderRecord) takes too, and only this function sets 'host'.
  if (plume::RenderShader *host = shader->host.get())
    return host;
  std::lock_guard lock(shader->host_mutex);
  if (!shader->host) {
    shader->host = CreateCachedShader(Video::Device(), *shader->entry);
    if (!shader->host) {
      RGPU_ERROR("Creating shader {:016X} failed", shader->hash);
      shader->entry = nullptr;  // don't retry every draw
      return nullptr;
    }
  }
  return shader->host.get();
}

void DestroyVertexDeclarationRecord(VertexDeclarationRecord *declaration) {
  if (!declaration)
    return;
  std::lock_guard lock(State().mutex);
  ForgetVertexDeclarationLocked(declaration->self_va);
  DestroyRecord(declaration);
}

void DestroyShaderRecord(ShaderRecord *shader) {
  if (!shader)
    return;
  // Pipelines built from it keep their own compiled copy; only the module goes.
  {
    auto &s = State();
    std::lock_guard lock(s.mutex);
    ForgetShader(shader->self_va);
    std::lock_guard shader_lock(shader->host_mutex);
    shader->host.reset();
  }
  DestroyRecord(shader);
}

} // namespace renut::gpu

namespace {

u32 CreateShaderRecord(const be_u32 *function, bool pixel) {
  if (!function)
    return 0;
  const auto *container = reinterpret_cast<const uint8_t *>(function);
  const auto *header = reinterpret_cast<const d3d::ShaderContainer *>(container);
  if ((u32(header->flags) & 0xFFFFFF00u) != 0x102A1100u) {
    RGPU_ERROR("Create{}Shader: not a shader container (flags {:08X})", pixel ? "Pixel" : "Vertex",
               u32(header->flags));
    return 0;
  }

  auto *shader = CreateRecord<ShaderRecord>(pixel ? RecordKind::PixelShader
                                                  : RecordKind::VertexShader);
  if (!shader)
    return 0;
  const auto type = pixel ? d3d::ResourceType::PixelShader : d3d::ResourceType::VertexShader;
  shader->x360.resource.Common = kCommonD3DCreated | u32(type);
  shader->x360.resource.ReferenceCount = 1u;

  shader->hash = HashShaderContainer(container);
  shader->entry = FindShaderEntry(shader->hash);
  if (!shader->entry)
    CaptureMissingShader(container, pixel, shader->hash);
  PipelineShaderLoaded(shader->entry);
  // Draws before it may have found no shader at the address (FindShaderLocked).
  render_thread::Queue([va = shader->self_va] { ForgetShader(va); });
  return shader->self_va;
}

// The host side of a shader object the guest set up in place: its container is
// the virtual part inside the object followed by the physical part.
void RegisterGuestShader(u32 shader_va, u32 physical_va, bool pixel) {
  const u32 container_va = shader_va + (pixel ? kPixelShaderContainer : kVertexShaderContainer);
  const auto *header = GuestPtr<const d3d::ShaderContainer>(container_va);
  const u8 *physical = physical_va < 0x20000000u ? GuestPhysicalPtr<const u8>(physical_va)
                                                 : GuestPtr<const u8>(physical_va);
  if (!header || !physical)
    return;
  const u32 flags = header->flags;
  const u32 virtual_size = header->virtualSize;
  const u32 physical_size = header->physicalSize;
  if ((flags & 0xFFFFFF00u) != 0x102A1100u || ((flags & 1) != 0) == pixel ||
      virtual_size < sizeof(d3d::ShaderContainer) || virtual_size > 0x10000 ||
      physical_size == 0 || physical_size > 0x100000) {
    RGPU_ERROR("XGRegister{}Shader {:08X}: no shader container at {:08X} (flags {:08X})",
               pixel ? "Pixel" : "Vertex", shader_va, container_va, flags);
    return;
  }
  std::vector<uint8_t> container(size_t(virtual_size) + physical_size);
  std::memcpy(container.data(), header, virtual_size);
  std::memcpy(container.data() + virtual_size, physical, physical_size);
  const uint64_t hash = HashShaderContainer(container.data());
  const RecordKind kind = pixel ? RecordKind::PixelShader : RecordKind::VertexShader;
  // Captured here, where its container is at hand, only when the cache lacks it.
  if (!FindShaderEntry(hash))
    CaptureMissingShader(container.data(), pixel, hash);

  // In order with the draws that use it (render thread).
  render_thread::Queue([shader_va, pixel, hash, kind] {
    auto &shader = g_guest_shaders[shader_va];
    if (shader && shader->hash == hash && shader->kind == kind)
      return;
    // A different shader in the same memory: pipelines keep their own compiled
    // copy of the old one, so its module can go now. Draws before it may also
    // have found none there (FindShaderLocked).
    ForgetShader(shader_va);
    shader = std::make_unique<ShaderRecord>();
    shader->kind = kind;
    shader->self_va = shader_va;
    shader->hash = hash;
    shader->entry = FindShaderEntry(hash);
    PipelineShaderLoaded(shader->entry);
  });
}

// void XGRegisterVertexShader(D3DVertexShader *pShader, void *pPhysicalPart) [0x8264E7B8]
// As the original: the header (a vertex shader of one reference), and for
// each of its bind slots (two when the container's flag 0x20 is set) the
// vertex fetch instructions copied from the microcode into the slot.
void XGRegisterVertexShader_hook(u32 shader, u32 physical) {
  auto *bytes = GuestPtr<u8>(shader);
  if (!bytes)
    return;
  auto word = [bytes](u32 offset) -> be_u32 & {
    return *reinterpret_cast<be_u32 *>(bytes + offset);
  };
  std::memset(bytes, 0, kVertexShaderContainer);
  word(kVertexShaderPhysical) = physical;
  word(0x00) = 6u;            // Common: D3DRTYPE_VERTEXSHADER
  word(0x04) = 1u;            // ReferenceCount
  word(0x14) = 0xFFFF0000u;   // BaseFlush
  const u32 slots = (u32(word(kVertexShaderContainer)) & 0x20) ? 2 : 1;
  for (u32 slot = 0; slot < slots; ++slot) {
    const u32 bind = 0x28 + slot * 0x1A0;
    const u32 table = u32(word(0x380 + slot * 8));
    const u32 fetches = u32(word(table + 0x384));
    const u32 microcode = u32(word(kVertexShaderPhysical)) + u32(word(table + 0x368));
    const u32 list = table + 0x368 + (u32(word(table + 0x380)) + 9) * 4;
    for (u32 i = 0; i < fetches; ++i) {
      const u32 source = (u32(word(list + i * 4)) & 0xFFF) * 12 + microcode;
      const u32 destination = shader + bind + 0x1C + i * 12;
      if (destination != source) {
        u8 *to = GuestPtr<u8>(destination);
        const u8 *from = GuestPtr<const u8>(source);
        if (to && from)
          std::memmove(to, from, 12);
      }
    }
    word(bind) = 0xFFFFFFFFu;
  }
  RegisterGuestShader(shader, physical, false);
}

// void XGRegisterPixelShader(D3DPixelShader *pShader, void *pPhysicalPart) [0x8264E670]
void XGRegisterPixelShader_hook(u32 shader, u32 physical) {
  auto *bytes = GuestPtr<u8>(shader);
  if (!bytes)
    return;
  auto *words = reinterpret_cast<be_u32 *>(bytes);
  std::memset(bytes, 0, kPixelShaderContainer);
  words[0] = 7u;            // Common: D3DRTYPE_PIXELSHADER
  words[1] = 1u;            // ReferenceCount
  words[5] = 0xFFFF0000u;   // BaseFlush
  words[6] = physical;      // the physical part (+0x18)
  RegisterGuestShader(shader, physical, true);
}

// D3DVertexShader *D3DDevice_CreateVertexShader(const DWORD *pFunction) [0x8264E8B0]
u32 D3DDevice_CreateVertexShader_hook(mapped_u32 function) {
  return CreateShaderRecord(static_cast<const be_u32 *>(function), false);
}

// D3DPixelShader *D3DDevice_CreatePixelShader(const DWORD *pFunction) [0x8264E6A8]
u32 D3DDevice_CreatePixelShader_hook(mapped_u32 function) {
  return CreateShaderRecord(static_cast<const be_u32 *>(function), true);
}

// D3DVertexDeclaration *D3DDevice_CreateVertexDeclaration(
//     const D3DVERTEXELEMENT9 *pVertexElements) [0x8264EA90]
u32 D3DDevice_CreateVertexDeclaration_hook(rex::MappedPtr<GuestVertexElement> elements) {
  if (!elements)
    return 0;
  auto *declaration = CreateRecord<VertexDeclarationRecord>(RecordKind::VertexDeclaration);
  if (!declaration)
    return 0;
  declaration->x360.resource.Common =
      kCommonD3DCreated | u32(d3d::ResourceType::VertexDeclaration);
  declaration->x360.resource.ReferenceCount = 1u;

  const GuestVertexElement *element = elements;
  for (u32 i = 0; i < 64 && u32(element[i].Type) != kDeclTypeUnused; ++i)
    declaration->elements.push_back(element[i]);
  BuildDeclarationLayout(*declaration);
  return declaration->self_va;
}

// void D3DVertexShader_Bind(D3DVertexShader *pShader, DWORD Flags,
//     D3DVertexDeclaration *pDecl, const DWORD *pStreamStrides, DWORD Index) [0x82657048]
// Patches a CVertexShader's vertex fetches to a declaration and the strides of
// streams 0..(highest stream in the declaration). Draws take their input layout
// from a declaration record instead, so nothing is patched; the declaration and
// strides are kept for draws that rely on the bind: N&B binds its shaders when
// it creates them and then draws with no declaration set, or with a zero
// SetStreamSource stride.
void D3DVertexShader_Bind_hook(u32 shader_va, u32 /*flags*/, u32 declaration_va,
                               mapped_u32 stream_strides, u32 /*index*/) {
  // The declaration and strides as they are now; the shader record is the
  // render thread's (draws read it), so it is updated there, in order.
  const auto *declaration =
      FindRecord<VertexDeclarationRecord>(declaration_va, RecordKind::VertexDeclaration);
  if (!declaration)
    return;
  auto bound = std::make_shared<VertexDeclarationRecord>(*declaration);
  std::vector<std::pair<u32, u32>> strides;  // stream, stride
  if (stream_strides) {
    const auto *guest_strides = static_cast<const be_u32 *>(stream_strides);
    for (const GuestVertexElement &element : declaration->elements) {
      const u32 stream = element.Stream;
      if (stream < d3d::kMaxStreams)
        strides.emplace_back(stream, u32(guest_strides[stream]));
    }
  }
  render_thread::Queue([shader_va, bound, strides = std::move(strides)] {
    auto *shader = FindShaderLocked(shader_va, RecordKind::VertexShader);
    if (!shader)
      return;
    shader->bound_declaration = std::make_unique<VertexDeclarationRecord>(*bound);
    for (const auto &[stream, stride] : strides)
      shader->bound_strides[stream] = stride;
  });
}

} // namespace

// ---------------------------------------------------------------------------
// sa2-nx (2026-10-20): SA2's hooks (N&B's addresses in brackets)
// ---------------------------------------------------------------------------
// SA2's shader objects stay the game's: its D3DDevice_CreateVertexShader / CreatePixelShader (sub_8255E750 /
// sub_8255E568) copy the container into the object and call XGRegisterVertexShader / XGRegisterPixelShader on it
// (the same object layout as N&B's: the container at +0x368 / +0x28, the physical part's pointer at +0x20 / +0x18).
// So the two XGRegister functions are the hooks: SA2's own code first, then the host side keyed by the container's
// hash (RegisterGuestShader). The vertex declarations stay the game's too: the host side is kept per object.

namespace {

// The host side of a declaration the game's Direct3D made from pElements (D3DVERTEXELEMENT9[], up to D3DDECL_END:
// Stream 0xFF), in order with the draws.
void RegisterGuestDeclaration(u32 declaration_va, const GuestVertexElement *elements) {
  auto declaration = std::make_shared<VertexDeclarationRecord>();
  declaration->x360.resource.Common = u32(d3d::ResourceType::VertexDeclaration);
  declaration->self_va = declaration_va;
  for (u32 i = 0; i < 64 && u32(elements[i].Stream) != 0xFF && u32(elements[i].Type) != kDeclTypeUnused; ++i)
    declaration->elements.push_back(elements[i]);
  BuildDeclarationLayout(*declaration);
  render_thread::Queue([declaration_va, declaration] {
    ForgetVertexDeclarationLocked(declaration_va);
    g_guest_declarations[declaration_va] = std::make_unique<VertexDeclarationRecord>(*declaration);
  });
}

}  // namespace

// void XGRegisterVertexShader(D3DVertexShader*, void *pPhysicalPart) [sub_8255E658; N&B 0x8264E7B8]
[[maybe_unused]] static void renut_sa2_disabled_sub_8255E658([[maybe_unused]] PPCContext& ctx, [[maybe_unused]] uint8_t* base) {
  const u32 shader = ctx.r3.u32, physical = ctx.r4.u32;
  RENUT_SA2_ONLY(__imp__sub_8255E658(ctx, base));
  RegisterGuestShader(shader, physical, false);
}

// void XGRegisterPixelShader(D3DPixelShader*, void *pPhysicalPart) [sub_8255DBF8; N&B 0x8264E670]
[[maybe_unused]] static void renut_sa2_disabled_sub_8255DBF8([[maybe_unused]] PPCContext& ctx, [[maybe_unused]] uint8_t* base) {
  const u32 shader = ctx.r3.u32, physical = ctx.r4.u32;
  RENUT_SA2_ONLY(__imp__sub_8255DBF8(ctx, base));
  RegisterGuestShader(shader, physical, true);
}

// D3DVertexDeclaration *D3DDevice_CreateVertexDeclaration(const D3DVERTEXELEMENT9*) [sub_8255E198; N&B 0x8264EA90]
[[maybe_unused]] static void renut_sa2_disabled_sub_8255E198([[maybe_unused]] PPCContext& ctx, [[maybe_unused]] uint8_t* base) {
  const u32 elements_va = ctx.r3.u32;
  RENUT_SA2_ONLY(__imp__sub_8255E198(ctx, base));
  const u32 declaration = ctx.r3.u32;
  if (const auto *elements = declaration ? GuestPtr<const GuestVertexElement>(elements_va) : nullptr)
    RegisterGuestDeclaration(declaration, elements);
}

// ---------------------------------------------------------------------------
// naruto-nx (2026-10-24): Naruto's shader objects (docs/d3d-census.md). Naruto builds them from xeshader.sdb in two
// game functions, 820F5150 (vertex) and 820F5348 (pixel), each taking a wrapper whose +4 holds the new D3D shader
// object (the PC base registers them at the same two places: app/src/gpu/shaders/shaders.cpp). The objects have N&B's
// layout (container at +0x368 / +0x28); the physical part's address is at +0x20 (vertex) / +0x18 (pixel).
// ---------------------------------------------------------------------------
REX_EXTERN(__imp__sub_820F5150);
REX_EXTERN(__imp__sub_820F5348);
namespace {
void NarutoRegisterShader(PPCContext &ctx, uint8_t *base, bool pixel) {
  const u32 wrapper = ctx.r3.u32;
  if (pixel)
    __imp__sub_820F5348(ctx, base);
  else
    __imp__sub_820F5150(ctx, base);
  const u32 shader = wrapper ? u32(*GuestPtr<const be_u32>(wrapper + 4)) : 0;
  if (!shader)
    return;
  const u32 physical = *GuestPtr<const be_u32>(shader + (pixel ? 0x18u : 0x20u));
  RegisterGuestShader(shader, physical, pixel);
}
}  // namespace
BANJO_RENUT_HOOK_RAW(sub_820F5150) {  // the game's vertex shader object from xeshader.sdb
  NarutoRegisterShader(ctx, base, false);
}
BANJO_RENUT_HOOK_RAW(sub_820F5348) {  // the game's pixel shader object from xeshader.sdb
  NarutoRegisterShader(ctx, base, true);
}

// ---------------------------------------------------------------------------
// naruto-nx: MRU cache for Jade Engine shader key lookups (sub_820F5A80 for VS, sub_820F5B68 for PS).
// The key object in r4 has vtable at +0 and 64-bit shader key at +8.
// A thread-local MRU cache avoids recurring binary tree / map searches in guest code on every draw call.
// ---------------------------------------------------------------------------
REX_EXTERN(__imp__sub_820F5A80);
REX_EXTERN(__imp__sub_820F5B68);

namespace {
struct ShaderLookupEntry {
  u32 dict = 0;
  u64 key = 0;
  u32 wrapper = 0;
};
}  // namespace

BANJO_RENUT_HOOK_RAW(sub_820F5A80) {
  const u32 dict = ctx.r3.u32;
  const u32 key_obj = ctx.r4.u32;
  if (!key_obj) {
    __imp__sub_820F5A80(ctx, base);
    return;
  }
  const auto *pk = GuestPtr<const be_u64>(key_obj + 8);
  const u64 key = pk ? u64(*pk) : 0;
  thread_local ShaderLookupEntry cache[1024]{};
  const u32 slot = u32(((key ^ (key >> 32)) * 0x9E3779B97F4A7C15ull) >> 54);
  ShaderLookupEntry &e = cache[slot];
  if (e.dict == dict && e.key == key && e.wrapper != 0) {
    ctx.r3.u64 = e.wrapper;
    return;
  }
  __imp__sub_820F5A80(ctx, base);
  if (ctx.r3.u32) {
    e = {dict, key, ctx.r3.u32};
  }
}

BANJO_RENUT_HOOK_RAW(sub_820F5B68) {
  const u32 dict = ctx.r3.u32;
  const u32 key_obj = ctx.r4.u32;
  if (!key_obj) {
    __imp__sub_820F5B68(ctx, base);
    return;
  }
  const auto *pk = GuestPtr<const be_u64>(key_obj + 8);
  const u64 key = pk ? u64(*pk) : 0;
  thread_local ShaderLookupEntry cache[1024]{};
  const u32 slot = u32(((key ^ (key >> 32)) * 0x9E3779B97F4A7C15ull) >> 54);
  ShaderLookupEntry &e = cache[slot];
  if (e.dict == dict && e.key == key && e.wrapper != 0) {
    ctx.r3.u64 = e.wrapper;
    return;
  }
  __imp__sub_820F5B68(ctx, base);
  if (ctx.r3.u32) {
    e = {dict, key, ctx.r3.u32};
  }
}

// ---------------------------------------------------------------------------
// naruto-nx: Native C++ implementations of D3D9 & Jade Engine hot shader/matrix/resource routines on Core 2.
// Avoids emulated AltiVec unaligned lvlx/lvrx/vperm/vmsum4fp128 loops and redundant store-card marking on D3DDevice
// and stack temporaries.
// ---------------------------------------------------------------------------

// D3DDevice_SetVertexShaderConstantF internal (r3=dev, r4=start_reg, r5=src_va, r6=vec4_count, r7=dirty_mask)
BANJO_RENUT_HOOK_RAW(sub_821315C0) {
  const u32 dev = ctx.r3.u32;
  const u32 start_reg = ctx.r4.u32;
  const u32 src_va = ctx.r5.u32;
  const u32 count = ctx.r6.u32;
  if (count) {
    std::memcpy(base + dev + ((start_reg + 120u) << 4), base + src_va, count * 16u);
  }
  auto *pending = reinterpret_cast<be_u64 *>(base + dev);
  *pending = u64(*pending) | ctx.r7.u64;
}

// D3DDevice_SetPixelShaderConstantF internal (r3=dev, r4=start_reg, r5=src_va, r6=vec4_count, r7=dirty_mask)
BANJO_RENUT_HOOK_RAW(sub_821316A8) {
  const u32 dev = ctx.r3.u32;
  const u32 start_reg = ctx.r4.u32;
  const u32 src_va = ctx.r5.u32;
  const u32 count = ctx.r6.u32;
  if (count) {
    std::memcpy(base + dev + ((start_reg + 376u) << 4), base + src_va, count * 16u);
  }
  auto *pending = reinterpret_cast<be_u64 *>(base + dev + 8);
  *pending = u64(*pending) | ctx.r7.u64;
}

// XMMatrixTranspose (r3=dst_va, r4=src_va)
BANJO_RENUT_HOOK_RAW(sub_822DF688) {
  const u32 dst_va = ctx.r3.u32;
  u32 m[16];
  std::memcpy(m, base + ctx.r4.u32, 64);
  const u32 out[16] = {
      m[0], m[4], m[8],  m[12],
      m[1], m[5], m[9],  m[13],
      m[2], m[6], m[10], m[14],
      m[3], m[7], m[11], m[15],
  };
  std::memcpy(base + dst_va, out, 64);
  if (dst_va - ctx.r1.u32 >= 0x10000u) {
    base[dst_va >> 12] = 0;
    base[(dst_va + 63u) >> 12] = 0;
  }
}

// XMMatrixMultiply (r3=dst_va, r4=a_va, r5=b_va)
BANJO_RENUT_HOOK_RAW(sub_822DF4F8) {
  const u32 dst_va = ctx.r3.u32;
  const auto *pa = reinterpret_cast<const be_f32 *>(base + ctx.r4.u32);
  const auto *pb = reinterpret_cast<const be_f32 *>(base + ctx.r5.u32);
  float a[4][4], b[4][4];
  for (int i = 0; i < 4; ++i) {
    for (int j = 0; j < 4; ++j) {
      a[i][j] = float(pa[i * 4 + j]);
      b[i][j] = float(pb[i * 4 + j]);
    }
  }
  be_f32 out[16];
  for (int i = 0; i < 4; ++i) {
    const float a0 = a[i][0], a1 = a[i][1], a2 = a[i][2], a3 = a[i][3];
    out[i * 4 + 0] = a0 * b[0][0] + a1 * b[1][0] + a2 * b[2][0] + a3 * b[3][0];
    out[i * 4 + 1] = a0 * b[0][1] + a1 * b[1][1] + a2 * b[2][1] + a3 * b[3][1];
    out[i * 4 + 2] = a0 * b[0][2] + a1 * b[1][2] + a2 * b[2][2] + a3 * b[3][2];
    out[i * 4 + 3] = a0 * b[0][3] + a1 * b[1][3] + a2 * b[2][3] + a3 * b[3][3];
  }
  std::memcpy(base + dst_va, out, 64);
  if (dst_va - ctx.r1.u32 >= 0x10000u) {
    base[dst_va >> 12] = 0;
    base[(dst_va + 63u) >> 12] = 0;
  }
}

// Jade VS vec4 constant setter (r3=shader_obj, r4=slot, r5=src_va, r6=vec4_count)
BANJO_RENUT_HOOK_RAW(sub_821017C8) {
  const u32 shader_obj = ctx.r3.u32;
  const u32 slot = ctx.r4.u32;
  const u32 src_va = ctx.r5.u32;
  const int32_t max_count = int32_t(*reinterpret_cast<const be_u32 *>(base + shader_obj + ((slot + 34u) << 2)));
  const int32_t count = std::min<int32_t>(ctx.r6.s32, max_count);
  const u32 mgr = *reinterpret_cast<const be_u32 *>(base + 0x82C0F008u);
  const u32 dev = *reinterpret_cast<const be_u32 *>(base + mgr + 16u);
  const int32_t start_reg = int16_t(*reinterpret_cast<const be_u16 *>(base + shader_obj + ((slot + 4u) << 1)));
  const u32 first_group = u32(start_reg) >> 2;
  const u32 last_group = u32(start_reg + count - 1) >> 2;
  const u32 diff = std::min<u32>((last_group - first_group) & 0x7Fu, 0x3Fu);
  const u64 srad = u64(int64_t(0x8000000000000000ull) >> diff);
  const u64 mask = (first_group & 0x40u) ? 0ull : (srad >> (first_group & 0x3Fu));
  if (count > 0) {
    std::memcpy(base + dev + ((u32(start_reg) + 120u) << 4), base + src_va, u32(count) * 16u);
  }
  auto *pending = reinterpret_cast<be_u64 *>(base + dev);
  *pending = u64(*pending) | mask;
}

// Jade VS scalar float array constant setter (r3=shader_obj, r4=slot, r5=src_va, r6=count)
BANJO_RENUT_HOOK_RAW(sub_82101828) {
  const u32 shader_obj = ctx.r3.u32;
  const u32 slot = ctx.r4.u32;
  const u32 src_va = ctx.r5.u32;
  const int32_t max_count = int32_t(*reinterpret_cast<const be_u32 *>(base + shader_obj + ((slot + 34u) << 2)));
  const int32_t count = std::min<int32_t>(ctx.r6.s32, max_count);
  if (count <= 0)
    return;
  const u32 mgr = *reinterpret_cast<const be_u32 *>(base + 0x82C0F008u);
  const u32 dev = *reinterpret_cast<const be_u32 *>(base + mgr + 16u);
  const int32_t base_reg = int16_t(*reinterpret_cast<const be_u16 *>(base + shader_obj + ((slot + 4u) << 1)));
  u64 mask = 0;
  for (int32_t i = 0; i < count; ++i) {
    const u32 reg = u32(base_reg + i);
    u32 raw_float = 0;
    std::memcpy(&raw_float, base + src_va + u32(i) * 4u, 4);
    u32 vec4[4] = {raw_float, 0, 0, 0};
    std::memcpy(base + dev + ((reg + 120u) << 4), vec4, 16);
    const u32 group = reg >> 2;
    if (!(group & 0x40u))
      mask |= 0x8000000000000000ull >> (group & 0x3Fu);
  }
  auto *pending = reinterpret_cast<be_u64 *>(base + dev);
  *pending = u64(*pending) | mask;
}

// Jade PS scalar float constant setter (r3=shader_obj, r4=slot, f1=value)
BANJO_RENUT_HOOK_RAW(sub_821018E0) {
  const u32 shader_obj = ctx.r3.u32;
  const u32 slot = ctx.r4.u32;
  const u32 mgr = *reinterpret_cast<const be_u32 *>(base + 0x82C0F008u);
  const u32 dev = *reinterpret_cast<const be_u32 *>(base + mgr + 16u);
  const u32 reg = u32(int32_t(int16_t(*reinterpret_cast<const be_u16 *>(base + shader_obj + ((slot + 4u) << 1)))));
  const be_f32 val(float(ctx.f1.f64));
  u32 vec4[4] = {0, 0, 0, 0};
  std::memcpy(&vec4[0], &val, 4);
  std::memcpy(base + dev + ((reg + 376u) << 4), vec4, 16);
  const u32 group = reg >> 2;
  if (!(group & 0x40u)) {
    auto *pending = reinterpret_cast<be_u64 *>(base + dev + 8u);
    *pending = u64(*pending) | (0x8000000000000000ull >> (group & 0x3Fu));
  }
}

// Jade resource ID lookup (called 8x per material in sub_82105648)
BANJO_RENUT_HOOK_RAW(sub_820F2990) {
  const u32 obj = ctx.r3.u32;
  const u32 id = ctx.r4.u32;
  if (ctx.r4.s32 == -1) {
    ctx.r3.u64 = 0;
    return;
  }
  if (id & 0x8000u) {
    const u32 idx = *reinterpret_cast<const be_u32 *>(base + obj + (((id & 0x7FFFu) + 405u) << 2));
    const u32 mgr = *reinterpret_cast<const be_u32 *>(base + 0x82C0F008u);
    const u32 p1 = *reinterpret_cast<const be_u32 *>(base + mgr + 536u);
    const u32 p2 = *reinterpret_cast<const be_u32 *>(base + p1 + 32u);
    ctx.r3.u64 = u32(*reinterpret_cast<const be_u32 *>(base + p2 + (idx << 2)));
    return;
  }
  if ((id & 0x1000000u) == 0x1000000u) {
    const u32 off = (id << 2) & 0x3FFFFFCu;
    const u32 mgr = *reinterpret_cast<const be_u32 *>(base + 0x82C0F008u);
    const u32 p1 = *reinterpret_cast<const be_u32 *>(base + mgr + 536u);
    const u32 p2 = *reinterpret_cast<const be_u32 *>(base + p1 + 32u);
    ctx.r3.u64 = u32(*reinterpret_cast<const be_u32 *>(base + p2 + off));
    return;
  }
  const u32 count = *reinterpret_cast<const be_u32 *>(base + obj + 4u);
  if (count <= id) {
    ctx.r3.u64 = 0;
    return;
  }
  const u32 arr = *reinterpret_cast<const be_u32 *>(base + obj);
  ctx.r3.u64 = u32(*reinterpret_cast<const be_u32 *>(base + arr + (id << 2)));
}

// naruto-nx (2026-10-24): Naruto's vertex declarations, registered lazily from the object itself (the draw hooks call
// this with the bound declaration, device +11812, before queuing the draw). Naruto's D3DVertexDeclaration (XDK 6274),
// read from live objects: Common 0x00100005 (type 5), the element count at +0x18 and the D3DVERTEXELEMENT9 array
// (12 bytes each) at +0x34, without the D3DDECL_END terminator. Re-registered when the object's elements change.
void NarutoNoteDeclaration(u32 declaration_va) {
  if (!declaration_va)
    return;
  // 64-entry direct-mapped cache: avoids repeated XXH3 hashing and mutex contention across all scene vertex declarations.
  thread_local u32 seen_va[64]{};
  const u32 slot = (declaration_va >> 5) & 63u;
  if (seen_va[slot] == declaration_va)
    return;
  const auto *words = GuestPtr<const be_u32>(declaration_va);
  if (!words || u32(words[0]) != 0x00100005u)
    return;
  const u32 count = std::min<u32>(u32(words[0x18 / 4]), 63);
  const auto *elements = GuestPtr<const GuestVertexElement>(declaration_va + 0x34);
  const uint64_t hash = XXH3_64bits(elements, size_t(count) * sizeof(GuestVertexElement)) ^ count;
  seen_va[slot] = declaration_va;
  static std::mutex mutex;
  static std::unordered_map<u32, uint64_t> seen;
  {
    std::lock_guard lock(mutex);
    auto [it, inserted] = seen.try_emplace(declaration_va, hash);
    if (!inserted && it->second == hash)
      return;
    it->second = hash;
  }
  GuestVertexElement copy[64];
  std::memcpy(copy, elements, size_t(count) * sizeof(GuestVertexElement));
  copy[count] = {};
  copy[count].Stream = 0xFF;  // D3DDECL_END
  copy[count].Type = kDeclTypeUnused;
  RegisterGuestDeclaration(declaration_va, copy);
}

// naruto-nx (2026-10-24, temporary diagnostic): the bound vertex shader's container hashed from guest memory now,
// to see whether Naruto's D3D patches the microcode after creation (its fetches, by the declaration).
uint64_t NarutoHashShaderNow(u32 shader_va, bool pixel) {
  if (!shader_va)
    return 0;
  const u32 container_va = shader_va + (pixel ? kPixelShaderContainer : kVertexShaderContainer);
  const auto *header = GuestPtr<const d3d::ShaderContainer>(container_va);
  const u32 physical_va = *GuestPtr<const be_u32>(shader_va + (pixel ? 0x18u : 0x20u));
  const u8 *physical = physical_va < 0x20000000u ? GuestPhysicalPtr<const u8>(physical_va) : GuestPtr<const u8>(physical_va);
  if (!header || !physical)
    return 0;
  const u32 virtual_size = header->virtualSize, physical_size = header->physicalSize;
  if (virtual_size > 0x10000 || physical_size > 0x100000)
    return 0;
  std::vector<uint8_t> container(size_t(virtual_size) + physical_size);
  std::memcpy(container.data(), header, virtual_size);
  std::memcpy(container.data() + virtual_size, physical, physical_size);
  return HashShaderContainer(container.data());
}
