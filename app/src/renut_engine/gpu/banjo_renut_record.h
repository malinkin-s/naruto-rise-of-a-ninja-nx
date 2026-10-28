// banjo-nx (package 28b): banjo_renut_record_worker, Renut's renderer's command recording split across two threads.
//
// On the console the render thread was the limit (about 38 ms a frame at 1020 MHz), and a quarter of it was inside
// plume and NVK recording the Vulkan commands. While a command list is open the render thread now records into a
// proxy (the same plume::RenderCommandList calls, each one copied into a chunk of a command stream, its arrays with
// it), and a worker thread on another core plays the chunks on the real command list in the same order. Before the
// list is ended and submitted the render thread waits until the worker has played everything (Drain). The GPU gets
// the same commands in the same order, so the image is the same; what moves to the worker is the driver's work.
// banjo-nx's own renderer does the same (its deferred recording, -10-12 % a draw on the console in package 24b).
#pragma once

#include <cstdint>

namespace plume {
struct RenderBuffer;
struct RenderCommandList;
}

namespace banjo::renut_gpu::record {

// Render thread, when a list is opened (Video::EnsureCommandListLocked): the list to record into, the proxy over
// 'real' when banjo_renut_record_worker is on (and in-run A/B target 14 not in its off half), else 'real'.
plume::RenderCommandList *Wrap(plume::RenderCommandList *real);
// Render thread: every command recorded so far played on the real list (before it is ended and submitted).
void Drain();
// SetBlendConstant (backend.cpp) calls Vulkan on the real command buffer itself: on the proxy it is a command too.
// True when 'cmd' is the proxy (the constant is then recorded).
bool SetBlendConstants(plume::RenderCommandList *cmd, const float rgba[4]);
// True when 'cmd' is the proxy: banjo_renut_tuning's NVK prefetch hint is then given by the worker before it binds.
bool IsProxy(const plume::RenderCommandList *cmd);

// naruto-nx (2026-10-28): plume's deko3d extras take the list itself (plume_deko3d.h), so on the proxy they are commands
// too: the same arguments as plume::Deko3D*, forwarded to plume when 'cmd' is a real list. The worker plays them on the
// real list in order. Data the call points at is copied into the stream. Deko3DSetSharedWords is the one that keeps a
// pointer: plume reads the renderer's copy of the shared constants at every draw, so the worker keeps a copy of its own
// and applies every recorded push of the shared buffer to it, in stream order.
bool Deko3DBindUniform(plume::RenderCommandList *cmd, uint32_t slot, uint64_t address, uint32_t size);
bool Deko3DPushUniform(plume::RenderCommandList *cmd, uint64_t address, uint32_t ubo_size, uint32_t offset,
                       const void *data, uint32_t size);
bool Deko3DSetSharedWords(plume::RenderCommandList *cmd, const void *cpu, uint32_t size);
bool Deko3DNotifyTexturesDirty(plume::RenderCommandList *cmd);
bool Deko3DBindMemExport(plume::RenderCommandList *cmd, const plume::RenderBuffer *buffer);
bool Deko3DBindFetchData(plume::RenderCommandList *cmd, uint64_t address, uint32_t size);
void Shutdown();
void Report(int seconds);  // the "[renut] record worker" line

}  // namespace banjo::renut_gpu::record
