/**
 * @file    gpu/backend/render_thread.cpp
 */
#include "renut_engine/gpu/backend/render_thread.h"

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <utility>
#include <fmt/format.h>
#include <string>
#include <rex/frame_latency.h>
#include <rex/input/read_hook.h>  // sa2-nx (2026-10-20): late input on SA2's reads
#include <vector>

#include "renut_engine/perf/frame_stats.h"
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/backend/queued.h"
#include "renut_engine/gpu/backend/video.h"
#include "renut_engine/gpu/banjo_renut_tuning.h"

#include <rex/cvar.h>

// sa2-nx (2026-10-20): see g_done_waiters and Run.
REXCVAR_DEFINE_BOOL(sa2_renut_done_notify_waiters, true, "SA2/Renderer",
                    "Renut's render thread signals its work done (frames, fences, drains) only when a thread waits for "
                    "it: a signal is a kernel call on the Switch even with nobody waiting, and it made one after every "
                    "batch of work. Off: after every batch, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sa2_renut_prefetch_next, true, "SA2/Renderer",
                    "Renut's render thread asks for the next draw's capture (written on the game thread's core) to be "
                    "brought into its cache while it does the draw before it")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sa2_renut_wake_batch, 16, "SA2/Renderer",
                     "Renut's render thread, when it has caught up and sleeps, is woken by the game's draws only once "
                     "this many are queued (each wake is a kernel call on both threads; the fourth console run woke it "
                     "for almost every draw). Every other item (frames, fences, resources), every wait for it and a "
                     "2 ms timer still wake it at once. 1 or less: every draw wakes it, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sa2_renut_batch_clock, true, "SA2/Renderer",
                    "Renut's render thread reads the clock once per batch of work instead of once per item (about "
                    "1,800 items a frame in City Escape); its busy time per frame is the same sum")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sa2_renut_lockfree_queue, true, "SA2/Renderer",
                    "Renut's render thread takes its work from a lock-free ring (one compare-and-swap a push) instead "
                    "of a vector under the queue's mutex. Off: the mutex and the vector")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

namespace renut::gpu::render_thread {

namespace {

using Clock = std::chrono::steady_clock;

struct Item {
  std::function<void()> work;
  bool locked = true;  // run with State().mutex held
  const void *prefetch[2] = {};  // sa2-nx (2026-10-20, sa2_renut_prefetch_next): fetched while the item before runs
};

// sa2-nx (2026-10-20, sa2_renut_prefetch_next): the next item's data into the cache (its first lines).
inline void PrefetchItem(const Item &item) {
  if (const auto *a = static_cast<const char *>(item.prefetch[0])) {
    __builtin_prefetch(a);
    __builtin_prefetch(a + 64);
  }
  if (const auto *b = static_cast<const char *>(item.prefetch[1])) {
    __builtin_prefetch(b);
    __builtin_prefetch(b + 64);
    __builtin_prefetch(b + 128);
    __builtin_prefetch(b + 192);
  }
}

std::mutex g_mutex;
std::condition_variable g_work_cv;  // work queued, or stopping
// banjo-nx (banjo_renut_queue_notify_idle): the render thread is in g_work_cv.wait (under g_mutex). A push notifies only
// then: on the Switch every notify is a kernel call, about 1,500 a frame from the game threads, most of them while the
// render thread is busy and not waiting. The render thread reads the queue under g_mutex before it sleeps, so a push
// it has not seen is never missed.
bool g_render_waiting = false;
std::condition_variable g_done_cv;  // work done: frames, fences, drains; or stopped
// sa2-nx (2026-10-20, sa2_renut_done_notify_waiters): threads in g_done_cv's waits (under g_mutex). A done signal goes
// only when there is one: a waiter checks its condition under g_mutex before it counts itself and sleeps, and the
// state it waits for changes under g_mutex too, so no signal it needs is skipped.
int g_done_waiters = 0;
bool DoneNotifyAll() {
  static const bool on = REXCVAR_GET(sa2_renut_done_notify_waiters);
  return !on;
}
// sa2-nx (2026-10-20, sa2_renut_wake_batch): the draws queued before a sleeping render thread is woken (1: each).
size_t WakeBatch() {
  static const size_t n = size_t(std::max(1, int(REXCVAR_GET(sa2_renut_wake_batch))));
  return n;
}

// sa2-nx (2026-10-28, sa2_renut_lockfree_queue): the queue as a bounded ring of kRingSlots items (D. Vyukov's bounded
// MPMC queue, with the render thread its one consumer).
bool g_lockfree = false;
bool LockfreeOn() {
  return g_lockfree;
}
bool g_notify_idle = true;
size_t g_wake_batch = 16;

constexpr uint64_t kRingSlots = uint64_t(1) << 14;
constexpr uint64_t kRingAhead = 8;
struct alignas(64) RingSlot {
  std::atomic<uint64_t> seq{0};
  Item item;
};
RingSlot *g_ring = nullptr;
alignas(64) std::atomic<uint64_t> g_enqueue{0};
alignas(64) std::atomic<uint64_t> g_dequeue{0};
std::atomic<bool> g_waiting{false};
std::atomic<bool> g_accepting{false};

inline bool RingReady(uint64_t pos) {
  return g_ring[pos & (kRingSlots - 1)].seq.load(std::memory_order_acquire) == pos + 1;
}
inline bool RingReadySc(uint64_t pos) {
  return g_ring[pos & (kRingSlots - 1)].seq.load(std::memory_order_seq_cst) == pos + 1;
}

std::vector<Item> g_queue;
std::once_flag g_start_once;
std::atomic<bool> g_started{false};
std::thread::id g_thread_id;
bool g_running = false;   // the thread takes work
bool g_stopping = false;  // Stop: finish what is queued, then end
uint64_t g_items_queued = 0;
uint64_t g_items_done = 0;
uint64_t g_frames_queued = 0;
uint64_t g_frames_done = 0;
uint64_t g_fences_done = 0;  // fence completions written, plus callbacks reached
uint64_t g_callbacks_reached = 0;
uint64_t g_callbacks_run = 0;
// Fence completions waiting for their callbacks, in order.
struct PendingFence {
  u32 completion_va;
  u32 fence;
  uint64_t after_callback;
};
std::vector<PendingFence> g_pending_fences;

// Requires g_mutex.
void WriteFence(u32 completion_va, u32 fence) {
  if (auto *word = GuestPtr<be_u32>(completion_va))
    *word = fence;
  ++g_fences_done;
}

// Render thread only: time spent running work since the last frame ended, and
// when the running item started; of that time, how much it waited (WaitScope).
Clock::duration g_busy{};
Clock::time_point g_item_start{};
Clock::duration g_waited{};
thread_local bool t_render_thread = false;

void Execute(Item &item) {
  if (item.locked) {
    std::lock_guard lock(State().mutex);
    item.work();
  } else {
    item.work();
  }
}

// sa2-nx (2026-10-28, sa2_renut_lockfree_queue): Run with the ring.
constexpr size_t kRingRun = 256;
void RunRing() {
  static const bool batch_clock = REXCVAR_GET(sa2_renut_batch_clock);
  static const bool prefetch = REXCVAR_GET(sa2_renut_prefetch_next);
  uint64_t pos = g_dequeue.load(std::memory_order_relaxed);
  for (;;) {
    if (!RingReady(pos)) {
      g_waiting.store(true, std::memory_order_seq_cst);
      bool stopping = false;
      if (!RingReadySc(pos)) {
        std::unique_lock lock(g_mutex);
        g_render_waiting = true;
        if (WakeBatch() > 1) {
          while (!RingReady(pos) && !g_stopping)
            g_work_cv.wait_for(lock, std::chrono::milliseconds(2));
        } else {
          g_work_cv.wait(lock, [pos] { return RingReady(pos) || g_stopping; });
        }
        g_render_waiting = false;
        stopping = g_stopping;
      }
      g_waiting.store(false, std::memory_order_relaxed);
      if (!RingReady(pos)) {
        if (stopping)
          break;
        continue;
      }
    }
    const Clock::time_point start = Clock::now();
    if (batch_clock)
      g_item_start = start;
    size_t n = 0;
    Clock::time_point item_start = start;
    do {
      RingSlot &slot = g_ring[pos & (kRingSlots - 1)];
      if (prefetch && RingReady(pos + 1))
        PrefetchItem(g_ring[(pos + 1) & (kRingSlots - 1)].item);
      if (!batch_clock)
        g_item_start = item_start;
      Execute(slot.item);
      slot.item.work = nullptr;
      slot.seq.store(pos + kRingSlots, std::memory_order_release);
      ++pos;
      g_dequeue.store(pos, std::memory_order_relaxed);
      ++n;
      if (!batch_clock) {
        const Clock::time_point end = Clock::now();
        g_busy += end - item_start;
        item_start = end;
      }
    } while (n < kRingRun && RingReady(pos));
    if (batch_clock)
      g_busy += Clock::now() - start;
    bool wake;
    {
      std::lock_guard lock(g_mutex);
      g_items_done += n;
      wake = g_done_waiters > 0 || DoneNotifyAll();
    }
    if (wake)
      g_done_cv.notify_all();
  }
  {
    std::lock_guard lock(g_mutex);
    g_running = false;
  }
  g_accepting.store(false, std::memory_order_release);
  g_done_cv.notify_all();
}

void Run() {
  {
    std::lock_guard lock(g_mutex);
    g_thread_id = std::this_thread::get_id();
  }
#if defined(_WIN32)
  SetThreadDescription(GetCurrentThread(), L"renut render");
#elif defined(__SWITCH__) || defined(__linux__)
  pthread_setname_np(pthread_self(), "renut render");
#endif
  banjo::renut_gpu::OnRenderThreadStart();
  t_render_thread = true;
  if (LockfreeOn()) {
    RunRing();
    return;
  }
  std::vector<Item> batch;
  for (;;) {
    {
      std::unique_lock lock(g_mutex);
      g_render_waiting = true;
      if (WakeBatch() > 1) {
        while (g_queue.empty() && !g_stopping)
          g_work_cv.wait_for(lock, std::chrono::milliseconds(2));
      } else {
        g_work_cv.wait(lock, [] { return !g_queue.empty() || g_stopping; });
      }
      g_render_waiting = false;
      if (g_queue.empty())
        break;
      batch.swap(g_queue);
    }
    Clock::time_point start = Clock::now();
    static const bool batch_clock = REXCVAR_GET(sa2_renut_batch_clock);
    if (batch_clock) {
      g_item_start = start;
      static const bool prefetch = REXCVAR_GET(sa2_renut_prefetch_next);
      const size_t n = batch.size();
      for (size_t i = 0; i < n; ++i) {
        if (prefetch && i + 1 < n)
          PrefetchItem(batch[i + 1]);
        Execute(batch[i]);
      }
      g_busy += Clock::now() - start;
    } else {
      for (Item &item : batch) {
        g_item_start = start;
        Execute(item);
        const Clock::time_point end = Clock::now();
        g_busy += end - start;
        start = end;
      }
    }
    bool wake;
    {
      std::lock_guard lock(g_mutex);
      g_items_done += batch.size();
      wake = g_done_waiters > 0 || DoneNotifyAll();
    }
    if (wake)
      g_done_cv.notify_all();
    batch.clear();
  }
  {
    std::lock_guard lock(g_mutex);
    g_running = false;
  }
  g_done_cv.notify_all();
}

void Start() {
  if (g_started.load(std::memory_order_acquire)) [[likely]]
    return;
  struct SetStarted {
    ~SetStarted() { g_started.store(true, std::memory_order_release); }
  };
  const SetStarted set_started;
  std::call_once(g_start_once, [] {
    InstallLateInput();
    std::lock_guard lock(g_mutex);
    g_running = true;
    g_lockfree = REXCVAR_GET(sa2_renut_lockfree_queue);
    g_notify_idle = banjo::renut_gpu::QueueNotifyIdleOn();
    g_wake_batch = WakeBatch();
    if (LockfreeOn()) {
      g_ring = new RingSlot[kRingSlots];
      for (uint64_t i = 0; i < kRingSlots; ++i)
        g_ring[i].seq.store(i, std::memory_order_relaxed);
      g_accepting.store(true, std::memory_order_release);
    }
    banjo::renut_gpu::StartLongLivedThread(Run, 1024 * 1024);
    RGPU_INFO("Render thread started (lockfree={})", g_lockfree);
  });
}

void WakeForWaitLocked() {
  if (LockfreeOn()) {
    if (g_render_waiting && g_ring && RingReady(g_dequeue.load(std::memory_order_relaxed)))
      g_work_cv.notify_one();
    return;
  }
  if (g_render_waiting && !g_queue.empty())
    g_work_cv.notify_one();
}

bool PushRing(Item &&item, bool draw) {
  uint64_t pos = g_enqueue.load(std::memory_order_relaxed);
  RingSlot *slot;
  for (;;) {
    slot = &g_ring[pos & (kRingSlots - 1)];
    const uint64_t seq = slot->seq.load(std::memory_order_acquire);
    const int64_t diff = int64_t(seq - pos);
    if (diff == 0) {
      if (g_enqueue.compare_exchange_weak(pos, pos + 1, std::memory_order_relaxed))
        break;
    } else if (diff < 0) {
      if (t_render_thread) {
        static std::atomic<bool> logged{false};
        if (!logged.exchange(true))
          RGPU_WARN("Render thread queue full ({} items): the render thread's own item ran at once "
                    "(sa2_renut_lockfree_queue)", kRingSlots);
        return false;
      }
      if (g_waiting.load(std::memory_order_seq_cst)) {
        {
          std::lock_guard lock(g_mutex);
        }
        g_work_cv.notify_one();
      }
      std::this_thread::yield();
      pos = g_enqueue.load(std::memory_order_relaxed);
    } else {
      pos = g_enqueue.load(std::memory_order_relaxed);
    }
  }
  __builtin_prefetch(&g_ring[(pos + kRingAhead) & (kRingSlots - 1)], 1);
  slot->item = std::move(item);
  slot->seq.store(pos + 1, std::memory_order_seq_cst);
  const bool wake = (g_waiting.load(std::memory_order_seq_cst) &&
                     (!draw || pos + 1 - g_dequeue.load(std::memory_order_relaxed) >= g_wake_batch)) ||
                    !g_notify_idle;
  if (wake) {
    {
      std::lock_guard lock(g_mutex);
    }
    g_work_cv.notify_one();
  }
  return true;
}

void Push(std::function<void()> work, bool locked, const void *prefetch0 = nullptr,
          const void *prefetch1 = nullptr, bool draw = false) {
  if (!draw) {
    renut::gpu::FlushDrawBatch();
  }
  Start();
  if (LockfreeOn()) {
    Item item{std::move(work), locked, {prefetch0, prefetch1}};
    if (g_accepting.load(std::memory_order_acquire) && PushRing(std::move(item), draw))
      return;
    Execute(item);
    return;
  }
  {
    std::unique_lock lock(g_mutex);
    if (g_running && !g_stopping) {
      g_queue.push_back({std::move(work), locked, {prefetch0, prefetch1}});
      ++g_items_queued;
      const bool wake = (g_render_waiting && (!draw || g_queue.size() >= 1)) ||
                        !banjo::renut_gpu::QueueNotifyIdleOn();
      lock.unlock();
      if (wake)
        g_work_cv.notify_one();
      return;
    }
  }
  Item item{std::move(work), locked, {}};
  Execute(item);
}

} // namespace

void Queue(std::function<void()> work) {
  Push(std::move(work), true);
}

void QueueUnlocked(std::function<void()> work) {
  Push(std::move(work), false);
}

void QueuePrefetched(const void *prefetch0, const void *prefetch1, std::function<void()> work) {
  Push(std::move(work), true, prefetch0, prefetch1, true);  // sa2-nx: the game's draws (sa2_renut_wake_batch)
}

void QueueFenceCompletion(u32 completion_va, u32 fence, uint64_t after_callback) {
  QueueUnlocked([completion_va, fence, after_callback] {
    bool wake;
    {
      std::lock_guard lock(g_mutex);
      // Fences complete in order: behind one still waiting, this one waits too.
      if (g_pending_fences.empty() && after_callback <= g_callbacks_run)
        WriteFence(completion_va, fence);
      else
        g_pending_fences.push_back({completion_va, fence, after_callback});
      wake = g_done_waiters > 0 || DoneNotifyAll();  // sa2-nx
    }
    if (wake)
      g_done_cv.notify_all();
  });
}

void QueueCallbackMarker(uint64_t seq) {
  QueueUnlocked([seq] {
    bool wake;
    {
      std::lock_guard lock(g_mutex);
      g_callbacks_reached = std::max(g_callbacks_reached, seq);
      ++g_fences_done;  // wakes WaitForFenceProgress: there is a callback to run
      wake = g_done_waiters > 0 || DoneNotifyAll();  // sa2-nx
    }
    if (wake)
      g_done_cv.notify_all();
  });
}

uint64_t CallbacksReached() {
  std::lock_guard lock(g_mutex);
  return g_callbacks_reached;
}

void CallbacksRun(uint64_t seq) {
  bool wake;
  {
    std::lock_guard lock(g_mutex);
    g_callbacks_run = std::max(g_callbacks_run, seq);
    size_t written = 0;
    for (; written < g_pending_fences.size(); ++written) {
      const PendingFence &p = g_pending_fences[written];
      if (p.after_callback > g_callbacks_run)
        break;
      WriteFence(p.completion_va, p.fence);
    }
    g_pending_fences.erase(g_pending_fences.begin(), g_pending_fences.begin() + written);
    wake = g_done_waiters > 0 || DoneNotifyAll();  // sa2-nx
  }
  if (wake)
    g_done_cv.notify_all();
}

bool WaitForFenceProgress(std::chrono::milliseconds timeout) {
  renut::gpu::FlushDrawBatch();
  std::unique_lock lock(g_mutex);
  if (!g_running || g_stopping)
    return false;
  const uint64_t seen = g_fences_done;
  WakeForWaitLocked();  // sa2-nx (sa2_renut_wake_batch)
  ++g_done_waiters;  // sa2-nx (sa2_renut_done_notify_waiters)
  g_done_cv.wait_for(lock, timeout,
                     [seen] { return g_fences_done != seen || !g_running || g_stopping; });
  --g_done_waiters;
  return g_running && !g_stopping;
}

// banjo-nx (2026-10-19, input latency, banjo_late_input): the game reads its controller at the start of a frame, and
// when the render thread is the slower of the two its frame then waits: the Swap below waits for the frame before to be
// done. The slack of a frame is that wait plus the delay its read already had: how much later the read could have been
// without the frame reaching the render thread any later. The next frame's first read is delayed by the least slack of
// the last kSlackFrames frames less kLateInputMarginUs (rex::latency::SetFrameReadDelayFunction): a frame whose game
// work runs long eats into the margin, and a run of them shrinks the delay; with the game thread or the frame cap the
// limit there is no wait, and the delay goes to 0.
namespace {
constexpr uint32_t kSlackFrames = 16;
constexpr uint64_t kLateInputMarginUs = 2000;
// banjo-nx (2026-10-19, latency batch 3): the most the read is delayed: 80 % of the game's frame interval (averaged over
// the frames at QueueFrame), at most kLateInputCeilingUs. A fixed 30 ms held it back where the GPU is the limit: the
// console's 18 fps scenes (package 35) delayed 30.0 ms with more slack than that.
constexpr uint64_t kLateInputCeilingUs = 60000;
std::atomic<uint64_t> g_frame_interval_us{0};
uint64_t g_last_queue_us = 0;
uint64_t g_slack_us[kSlackFrames] = {};
uint32_t g_slack_next = 0;
uint32_t g_slack_count = 0;
std::atomic<uint32_t> g_applied_delay_us{0};
std::atomic<uint64_t> g_delay_total_us{0}, g_delay_frames{0};

uint32_t LateInputDelay() {
  if (!banjo::renut_gpu::LateInputOn() || g_slack_count < kSlackFrames) {
    g_applied_delay_us.store(0, std::memory_order_relaxed);
    return 0;
  }
  uint64_t least = UINT64_MAX;
  for (uint64_t s : g_slack_us)
    least = std::min(least, s);
  const uint64_t interval = g_frame_interval_us.load(std::memory_order_relaxed);
  const uint64_t ceiling = std::min(kLateInputCeilingUs, interval * 4 / 5);
  const uint64_t delay = least > kLateInputMarginUs ? std::min(least - kLateInputMarginUs, ceiling) : 0;
  g_applied_delay_us.store(uint32_t(delay), std::memory_order_relaxed);
  g_delay_total_us.fetch_add(delay, std::memory_order_relaxed);
  g_delay_frames.fetch_add(1, std::memory_order_relaxed);
  return uint32_t(delay);
}
}  // namespace

void InstallLateInput() {
  rex::latency::SetFrameReadDelayFunction(&LateInputDelay);
  // sa2-nx (2026-10-20): SA2's SDK did not call the delay or the probe at the controller reads (banjo-nx's input system
  // does), so late input never ran on SA2: the read hook does both now.
  rex::input::SetReadHook([] {
    rex::latency::BeforeInputRead();
    rex::latency::NoteInputRead();
  });
}

std::string LateInputReport() {
  const uint64_t frames = g_delay_frames.exchange(0, std::memory_order_relaxed);
  const uint64_t total = g_delay_total_us.exchange(0, std::memory_order_relaxed);
  return frames ? fmt::format("late input: the first controller read of a frame delayed {:.1f} ms on average ({} "
                              "frames)",
                              double(total) / 1000.0 / double(frames), frames)
                : std::string("late input: no delay");
}

uint64_t QueueFrame(std::function<void()> work) {
  {
    std::lock_guard lock(g_mutex);
    ++g_frames_queued;
  }
  QueueUnlocked([work = std::move(work)] {
    work();
    // The frame's work includes this item's (the present); Run adds the whole
    // item afterwards, so what is left of it counts to the next frame.
    const Clock::duration so_far = Clock::now() - g_item_start;
    const double busy_ms =
        std::chrono::duration<double, std::milli>(g_busy + so_far - g_waited).count();
    g_busy = -so_far;
    g_waited = {};
    frame_stats::OnRenderThreadFrame(busy_ms);
    bool wake;
    {
      std::lock_guard lock(g_mutex);
      ++g_frames_done;
      wake = g_done_waiters > 0 || DoneNotifyAll();  // sa2-nx
    }
    if (wake)
      g_done_cv.notify_all();
  });
  const auto waiting = std::chrono::steady_clock::now();
  std::unique_lock lock(g_mutex);
  WakeForWaitLocked();  // sa2-nx (sa2_renut_wake_batch)
  ++g_done_waiters;  // sa2-nx (sa2_renut_done_notify_waiters)
  g_done_cv.wait(lock, [] {
    return !g_running || g_stopping || g_frames_queued - g_frames_done <= kMaxFramesAhead;
  });
  --g_done_waiters;
  const uint64_t done = g_frames_done;
  lock.unlock();
  const auto waited = std::chrono::steady_clock::now() - waiting;
  frame_stats::OnGameThreadWait(std::chrono::duration<double, std::milli>(waited).count(),
                              frame_stats::WaitKind::kFramesAhead);
  // banjo-nx (2026-10-19, banjo_late_input): this frame's slack (the game thread only: one Swap at a time).
  {
    // The game's frame interval (the game thread only), averaged over about 16 frames.
    const uint64_t at = uint64_t(
        std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch())
            .count());
    if (g_last_queue_us && at > g_last_queue_us) {
      const uint64_t gap = std::min<uint64_t>(at - g_last_queue_us, 1'000'000);
      const uint64_t avg = g_frame_interval_us.load(std::memory_order_relaxed);
      g_frame_interval_us.store(avg ? avg + (int64_t(gap) - int64_t(avg)) / 16 : gap, std::memory_order_relaxed);
    }
    g_last_queue_us = at;
  }
  g_slack_us[g_slack_next] =
      uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(waited).count()) +
      g_applied_delay_us.exchange(0, std::memory_order_relaxed);
  g_slack_next = (g_slack_next + 1) % kSlackFrames;
  g_slack_count = std::min(g_slack_count + 1, kSlackFrames);
  return done;
}

uint64_t FramesDone() {
  std::lock_guard lock(g_mutex);
  return g_frames_done;
}

void Drain() {
  renut::gpu::FlushDrawBatch();
  std::unique_lock lock(g_mutex);
  if (!g_running || std::this_thread::get_id() == g_thread_id)
    return;
  const uint64_t target = LockfreeOn() ? g_enqueue.load(std::memory_order_acquire) : g_items_queued;
  WakeForWaitLocked();  // sa2-nx (sa2_renut_wake_batch)
  ++g_done_waiters;  // sa2-nx (sa2_renut_done_notify_waiters)
  g_done_cv.wait(lock, [target] { return !g_running || g_items_done >= target; });
  --g_done_waiters;
}

WaitScope::WaitScope() : start_(Clock::now()), counted_(t_render_thread) {}

WaitScope::~WaitScope() {
  if (counted_)
    g_waited += Clock::now() - start_;
}

void Stop() {
  renut::gpu::FlushDrawBatch();
  {
    std::lock_guard lock(g_mutex);
    if (!g_running || g_stopping)
      return;
    g_stopping = true;
  }
  g_accepting.store(false, std::memory_order_release);
  g_work_cv.notify_all();
  g_done_cv.notify_all();
}

} // namespace renut::gpu::render_thread
