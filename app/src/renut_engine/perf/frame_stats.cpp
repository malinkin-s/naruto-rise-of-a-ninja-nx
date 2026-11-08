// banjo-nx: the frame statistics Renut's renderer reports into (renut_engine/perf/frame_stats.h, copied from Renut by
// tools/renut_gpu_import.py). Renut's own frame_stats.cpp also hooks the game's main loop (appMainTickPreDraw /
// appMainDraw), which banjo-nx's FPS code hooks already, so this keeps the numbers without those hooks: a game frame is
// one D3DDevice_Swap, its length the time between two.
#include "renut_engine/perf/frame_stats.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <string>

#include <rex/cvar.h>
#include <rex/logging.h>

#if defined(__SWITCH__)
#include <switch.h>
extern "C" const char* RexSwitchLogDir(void);
extern "C" void RexSwitchPerfResetWindow(void);
#endif

REXCVAR_DEFINE_STRING(naruto_measure_run_id, "", "Naruto/Measurement",
                      "Unique Run ID for a console measurement; empty uses auto-generated Run ID")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(naruto_measure_duration_s, 30, "Naruto/Measurement",
                     "Duration in seconds of the measurement segment")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Counter 0 of the console profiler: presented frames, which the Status Monitor overlay's FPS (SaltyNX) and the
// profiler's "game N fps" are made from (sdk/src/ui/switch_perf.cpp; a stub on the PC, me_pc_stubs.cpp).
extern "C" void RexSwitchPerfCount(unsigned id);

#include "profiler/profiler.h"                      // the on-screen profiler's GPU, present and render thread rows
#include "renut_engine/gpu/banjo_renut_tuning.h"  // the [renut] report and its in-run A/B

namespace renut::frame_stats {

namespace {

using Clock = std::chrono::steady_clock;

#if defined(__SWITCH__)
constexpr size_t kMaxIntervals = 8192;

struct Intervals {
  std::array<double, kMaxIntervals> ms{};
  size_t count = 0;
  bool overflow = false;
  uint64_t events = 0;
  Clock::time_point first{}, last{};

  void Add(Clock::time_point now) {
    if (events && count < ms.size())
      ms[count++] = std::chrono::duration<double, std::milli>(now - last).count();
    else if (events)
      overflow = true;
    if (!events) first = now;
    last = now;
    ++events;
  }
};

// The two event streams are kept in memory and reduced to one short log line after the segment.
// No raw frame trace is written to the SD card.
struct Measurement {
  bool active = false, done = false;
  Clock::time_point start{};
  uint64_t start_tick = 0;
  uint64_t first_guest_ordinal = 0, last_guest_ordinal = 0;
  Intervals guest, present;
  std::string run_id;
  uint64_t frames = 0;
  double render_busy_sum_ms = 0.0;
  double gpu_sum_ms = 0.0;
  uint64_t gpu_frames = 0;
  double wait_fence_sum_ms = 0.0;
  double wait_ahead_sum_ms = 0.0;
};

bool ValidRunId(const std::string& id) {
  if (id.empty() || id.size() > 64) return false;
  for (char c : id)
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-' || c == '_'))
      return false;
  return true;
}

const std::string& RunId() {
  static const std::string id = REXCVAR_GET(naruto_measure_run_id);
  return id;
}

struct Distribution {
  double p50 = 0, p95 = 0, p99 = 0, max = 0, low1_fps = 0;
};

Distribution Describe(Intervals& intervals) {
  Distribution d;
  if (!intervals.count) return d;
  std::sort(intervals.ms.begin(), intervals.ms.begin() + intervals.count);
  const auto percentile = [&](double q) {
    const size_t index = size_t(std::ceil(q * double(intervals.count))) - 1;
    return intervals.ms[index];
  };
  d.p50 = percentile(0.50);
  d.p95 = percentile(0.95);
  d.p99 = percentile(0.99);
  d.max = intervals.ms[intervals.count - 1];
  const size_t slowest = size_t(std::ceil(double(intervals.count) * 0.01));
  double sum_ms = 0;
  for (size_t i = intervals.count - slowest; i < intervals.count; ++i) sum_ms += intervals.ms[i];
  if (sum_ms > 0) d.low1_fps = 1000.0 * double(slowest) / sum_ms;
  return d;
}

double EventFps(const Intervals& intervals) {
  if (intervals.events < 2) return 0;
  const double seconds = std::chrono::duration<double>(intervals.last - intervals.first).count();
  return seconds > 0 ? double(intervals.events - 1) / seconds : 0;
}
#endif

struct State {
  std::mutex mutex;
  Snapshot snap;
  Clock::time_point last_frame{};
  Clock::time_point window_start{};
  int window_frames = 0;
  double window_worst = 0.0;
  double gpu_sum = 0.0, render_sum = 0.0, wait_sum = 0.0;
  int gpu_n = 0, render_n = 0;
  // naruto-nx: the 10 s log of the game thread's waits by kind.
  Clock::time_point log_start{};
  int log_frames = 0, log_fence_n = 0, log_ahead_n = 0;
  double log_fence_ms = 0.0, log_ahead_ms = 0.0, log_fence_max = 0.0;
#if defined(__SWITCH__)
  Measurement measurement;
#endif
};

State& S() {
  static State s;
  return s;
}

#if defined(__SWITCH__)
void FinalizeMeasurementLocked(State& s) {
  Measurement& m = s.measurement;
  const uint64_t end_tick = armGetSystemTick();
  m.active = false;
  m.done = true;
  const Distribution guest = Describe(m.guest);
  const Distribution present = Describe(m.present);
  const double render_busy_mean = m.frames ? (m.render_busy_sum_ms / double(m.frames)) : 0.0;
  const double gpu_mean = m.gpu_frames ? (m.gpu_sum_ms / double(m.gpu_frames)) : 0.0;
  const double wait_fence_mean = m.frames ? (m.wait_fence_sum_ms / double(m.frames)) : 0.0;
  const double wait_ahead_mean = m.frames ? (m.wait_ahead_sum_ms / double(m.frames)) : 0.0;

  REXLOG_INFO("[measure] run={} END tick_start={} tick_end={} guest_ordinal_first={} guest_ordinal_last={} "
              "guest_events={} guest_intervals={} "
              "guest_fps={:.3f} guest_p50={:.3f} guest_p95={:.3f} guest_p99={:.3f} guest_max={:.3f} "
              "guest_1pct_low={:.3f} present_events={} present_intervals={} present_fps={:.3f} "
              "present_p50={:.3f} present_p95={:.3f} present_p99={:.3f} present_max={:.3f} "
              "present_1pct_low={:.3f} overflow={} "
              "render_busy_ms={:.2f} gpu_ms={:.2f} wait_fence_ms={:.2f} wait_ahead_ms={:.2f}",
              m.run_id, m.start_tick, end_tick, m.first_guest_ordinal, m.last_guest_ordinal,
              m.guest.events, m.guest.count, EventFps(m.guest),
              guest.p50, guest.p95, guest.p99, guest.max, guest.low1_fps, m.present.events, m.present.count,
              EventFps(m.present), present.p50, present.p95, present.p99, present.max, present.low1_fps,
              m.guest.overflow || m.present.overflow,
              render_busy_mean, gpu_mean, wait_fence_mean, wait_ahead_mean);
}
#endif

}  // namespace

extern "C" void RexSwitchToggleMeasurement(void) {
#if defined(__SWITCH__)
  State& s = S();
  std::lock_guard lock(s.mutex);
  const auto now = Clock::now();
  if (!s.measurement.active) {
    s.measurement.active = true;
    s.measurement.done = false;
    s.measurement.start = now;
    s.measurement.start_tick = armGetSystemTick();
    s.measurement.first_guest_ordinal = 0;
    s.measurement.last_guest_ordinal = 0;
    s.measurement.guest = {};
    s.measurement.present = {};
    s.measurement.frames = 0;
    s.measurement.render_busy_sum_ms = 0.0;
    s.measurement.gpu_sum_ms = 0.0;
    s.measurement.gpu_frames = 0;
    s.measurement.wait_fence_sum_ms = 0.0;
    s.measurement.wait_ahead_sum_ms = 0.0;

    std::string id = RunId();
    if (id.empty()) {
      static int s_run_counter = 1;
      id = "village-view-" + std::to_string(s_run_counter++);
    }
    s.measurement.run_id = id;
    RexSwitchPerfResetWindow();
    REXLOG_INFO("[measure] run={} START tick={} duration={}s",
                s.measurement.run_id, s.measurement.start_tick,
                REXCVAR_GET(naruto_measure_duration_s));
  } else {
    FinalizeMeasurementLocked(s);
  }
#endif
}

extern "C" bool RexSwitchGetMeasurementStatus(renut::frame_stats::MeasurementStatus* out) {
  if (!out) return false;
#if defined(__SWITCH__)
  State& s = S();
  std::lock_guard lock(s.mutex);
  out->active = s.measurement.active;
  out->done = s.measurement.done;
  out->total_duration_seconds = float(REXCVAR_GET(naruto_measure_duration_s));
  if (s.measurement.active) {
    const auto now = Clock::now();
    out->elapsed_seconds = std::chrono::duration<float>(now - s.measurement.start).count();
    out->live_fps = s.snap.fps;
    out->live_ms = s.snap.frame_ms;
    std::snprintf(out->run_id, sizeof(out->run_id), "%s", s.measurement.run_id.c_str());
  } else if (s.measurement.done) {
    out->elapsed_seconds = out->total_duration_seconds;
    out->live_fps = s.snap.fps;
    out->live_ms = s.snap.frame_ms;
    std::snprintf(out->run_id, sizeof(out->run_id), "%s", s.measurement.run_id.c_str());
  }
  return true;
#else
  *out = {};
  return false;
#endif
}

void OnGameFrame(uint64_t game_frame_ordinal) {
  banjo::renut_gpu::StatsGameFrame();
  State& s = S();
  std::lock_guard lock(s.mutex);
  const auto now = Clock::now();
#if defined(__SWITCH__)
  if (s.measurement.active) {
    Measurement& m = s.measurement;
    if (now - m.start < std::chrono::seconds(REXCVAR_GET(naruto_measure_duration_s))) {
      m.guest.Add(now);
      if (!m.first_guest_ordinal) m.first_guest_ordinal = game_frame_ordinal;
      m.last_guest_ordinal = game_frame_ordinal;
      ++m.frames;
    } else {
      FinalizeMeasurementLocked(s);
    }
  }
#endif
  if (s.last_frame != Clock::time_point{}) {
    const double ms = std::chrono::duration<double, std::milli>(now - s.last_frame).count();
    Snapshot& snap = s.snap;
    if (snap.history_count < Snapshot::kHistory) {
      snap.history[snap.history_count++] = float(ms);
    } else {
      std::copy(snap.history + 1, snap.history + Snapshot::kHistory, snap.history);
      snap.history[Snapshot::kHistory - 1] = float(ms);
    }
    s.window_worst = std::max(s.window_worst, ms);
    ++s.window_frames;
  } else {
    s.window_start = now;
  }
  s.last_frame = now;
  if (s.log_start == Clock::time_point{}) s.log_start = now;
  ++s.log_frames;
  if (const double log_s = std::chrono::duration<double>(now - s.log_start).count(); log_s >= 10.0) {
    REXLOG_INFO("[renut] game thread waits, {:.1f} s, {} frames: fences {} ({:.2f} ms a frame, longest {:.2f} ms), "
                "for the render thread (frames ahead) {} ({:.2f} ms a frame)",
                log_s, s.log_frames, s.log_fence_n, s.log_fence_ms / s.log_frames, s.log_fence_max, s.log_ahead_n,
                s.log_ahead_ms / s.log_frames);
    s.log_start = now;
    s.log_frames = s.log_fence_n = s.log_ahead_n = 0;
    s.log_fence_ms = s.log_ahead_ms = s.log_fence_max = 0.0;
  }
  const double window = std::chrono::duration<double>(now - s.window_start).count();
  if (window >= 1.0 && s.window_frames) {
    Snapshot& snap = s.snap;
    snap.fps = s.window_frames / window;
    snap.frame_ms = window * 1000.0 / s.window_frames;
    snap.worst_ms = s.window_worst;
    snap.cpu_ms = std::max(0.0, snap.frame_ms - s.wait_sum / s.window_frames);
    if (s.gpu_n) {
      snap.gpu_ms = s.gpu_sum / s.gpu_n;
      snap.gpu_known = true;
    }
    if (s.render_n) {
      snap.render_thread_ms = s.render_sum / s.render_n;
      snap.render_thread_known = true;
    }
    s.window_start = now;
    s.window_frames = 0;
    s.window_worst = 0.0;
    s.gpu_sum = s.render_sum = s.wait_sum = 0.0;
    s.gpu_n = s.render_n = 0;
  }
}

void OnGpuFrame(double ms) {
  banjo::renut_gpu::StatsGpuFrame(ms);
  banjo::profiler::SetGpuFrameMs(ms);  // the profiler window's "GPU Frame" (package 27: nobody fed it before)
  State& s = S();
  std::lock_guard lock(s.mutex);
#if defined(__SWITCH__)
  if (s.measurement.active) {
    s.measurement.gpu_sum_ms += ms;
    ++s.measurement.gpu_frames;
  }
#endif
  s.gpu_sum += ms;
  ++s.gpu_n;
}

void OnRenderThreadFrame(double busy_ms) {
  banjo::renut_gpu::StatsRenderThreadFrame(busy_ms);
  // The profiler window (package 27): the render thread's frame ends with its present, so this is also the time
  // between two host presents ("Present"); one thread, as RecordHostPresent needs.
  banjo::profiler::SetRenderThreadMs(busy_ms);
  banjo::profiler::RecordHostPresent();
  // Package 27c: the presented frame for the console's FPS. Only banjo-nx's own renderer (and the SDK's) counted
  // them, so with Renut's renderer the Status Monitor kept an old value (19.7) and the profile said "game 0.0 fps".
  RexSwitchPerfCount(0);
  State& s = S();
  std::lock_guard lock(s.mutex);
#if defined(__SWITCH__)
  if (s.measurement.active) {
    s.measurement.present.Add(Clock::now());
    s.measurement.render_busy_sum_ms += busy_ms;
  }
#endif
  s.render_sum += busy_ms;
  ++s.render_n;
}

void OnGameThreadWait(double ms, WaitKind kind) {
  State& s = S();
  std::lock_guard lock(s.mutex);
#if defined(__SWITCH__)
  if (s.measurement.active) {
    if (kind == WaitKind::kFence) s.measurement.wait_fence_sum_ms += ms;
    else s.measurement.wait_ahead_sum_ms += ms;
  }
#endif
  s.wait_sum += ms;
  if (kind == WaitKind::kFence) {
    ++s.log_fence_n;
    s.log_fence_ms += ms;
    s.log_fence_max = std::max(s.log_fence_max, ms);
  } else {
    ++s.log_ahead_n;
    s.log_ahead_ms += ms;
  }
}

Snapshot Get() {
  State& s = S();
  std::lock_guard lock(s.mutex);
  return s.snap;
}

}  // namespace renut::frame_stats
