"""Validity checks for joining compact CPU and Renut measurement windows."""

import unittest

from ftp_run_summary import render_report


RUN = "run_test_01"
CONTROL_RUN = "run_control_00"
GAME_START = "[2026-11-02 12:00:00.000] [info] [measure] run=run_test_01 START tick=1000 duration=30s"
GAME_END = (
    "[2026-11-02 12:00:31.000] [info] [measure] run=run_test_01 END tick_start=1000 tick_end=31000 "
    "guest_ordinal_first=10 guest_ordinal_last=910 guest_events=901 guest_intervals=900 guest_fps=30.000 "
    "guest_p50=33.333 guest_p95=34.000 guest_p99=40.000 guest_max=45.000 guest_1pct_low=25.000 "
    "present_events=901 present_intervals=900 present_fps=30.000 present_p50=33.333 present_p95=34.000 "
    "present_p99=40.000 present_max=45.000 present_1pct_low=25.000 overflow=false"
)
RENUT = (
    "[2026-11-02 12:00:15.000] [info] [renut] 10.0 s: 300 game frames (30.00 fps), "
    "render thread busy 20.00 ms a frame (300 frames), GPU 15.00 ms a frame (300 frames); 9000 draws"
)
CPU = """[measure] run=run_test_01 cpu_window_tick_start=5000 cpu_window_tick_end=15000 tick_hz=1000
==== 10.0 s | mode: normal | game 30.0 fps | CPU total 200%
     clocks: CPU 1020.0 MHz, GPU 460.8 MHz, memory 1600.0 MHz | process cores 4 (mask 0xF)
-- thread 2408 "Main XThread": CPU 90.0%
-- thread 2416 "renut render": CPU 60.0%
     audio: 100 client blocks mixed, 0 requests without data"""


def game(marker="[measure] run=run_test_01 renut_window_tick_start=5000 renut_window_tick_end=15000 tick_hz=1000"):
    return "\n".join((GAME_START, "[2026-11-02 12:00:14.999] [info] " + marker, RENUT, GAME_END)).encode()


class SummaryValidityTest(unittest.TestCase):
    def report(self, game_log=None, cpu_log=CPU, control_id=None, control_report=None):
        return render_report(
            RUN,
            "naruto_001.log",
            game_log or game(),
            cpu_log.encode(),
            control_id=control_id,
            control_report_text=control_report,
        )

    def test_aligned_windows_are_candidate_only(self):
        report = self.report()
        self.assertIn("candidate (scene/config review required)", report)
        self.assertIn("guest ordinals 10–910", report)
        self.assertIn("| 5000–15000 | 2026-11-02T12:00:15 | 300 | 30.00 | 20.00 | 15.00 | 30.0 |", report)
        self.assertIn("| 5000–15000 | 30.0 | 200.0 | 90.0 | 60.0 |", report)

    def test_partial_renut_window_is_pending(self):
        marker = "[measure] run=run_test_01 renut_window_tick_start=0 renut_window_tick_end=10000 tick_hz=1000"
        self.assertIn("Status: pending", self.report(game(marker)))

    def test_wrong_cpu_run_is_pending(self):
        self.assertIn("Status: pending", self.report(cpu_log=CPU.replace(RUN, "another_run")))

    def test_clock_mismatch_is_pending(self):
        self.assertIn("Status: pending", self.report(cpu_log=CPU.replace("tick_hz=1000", "tick_hz=2000")))

    def test_no_prescribed_verdict_or_auto_actions(self):
        report = self.report()
        self.assertNotIn("## Bottleneck Verdict", report)
        self.assertNotIn("Prescribed Action", report)
        self.assertNotIn("MAIN_CPU_BOUND", report)

    def test_culling_table_parsed_if_nonzero(self):
        cull_lines = (
            "[2026-11-02 12:00:20.000] [info] [naruto-cull] Batch5: Batches tested: 100.0/fr, culled: 40.0/fr (40.0%) | Items tested: 1500.0/fr, culled: 600.0/fr (40.0%)\n"
            "[2026-11-02 12:00:20.001] [info] [naruto-cull] Batch5Dist: <50m: 300.0, 50-100m: 400.0, 100-150m: 200.0, 150-200m: 100.0, >200m: 500.0"
        )
        game_log = "\n".join((GAME_START, "[2026-11-02 12:00:14.999] [info] [measure] run=run_test_01 renut_window_tick_start=5000 renut_window_tick_end=15000 tick_hz=1000", RENUT, cull_lines, GAME_END)).encode()
        report = self.report(game_log=game_log)
        self.assertIn("| Modular Culling (Batch5) |", report)
        self.assertIn("1500.0 | 600.0 (40.0%)", report)
        self.assertIn("| Culling Distances |", report)

    def test_culling_table_suppressed_when_zero(self):
        zero_cull = (
            "[2026-11-02 12:00:20.000] [info] [naruto-cull] Batch5: Batches tested: 0.0/fr, culled: 0.0/fr (0.0%) | Items tested: 0.0/fr, culled: 0.0/fr (0.0%)\n"
            "[2026-11-02 12:00:20.001] [info] [naruto-cull] Batch5Dist: <50m: 0.0, 50-100m: 0.0, 100-150m: 0.0, 150-200m: 0.0, >200m: 0.0"
        )
        game_log = "\n".join((GAME_START, "[2026-11-02 12:00:14.999] [info] [measure] run=run_test_01 renut_window_tick_start=5000 renut_window_tick_end=15000 tick_hz=1000", RENUT, zero_cull, GAME_END)).encode()
        report = self.report(game_log=game_log)
        self.assertNotIn("| Modular Culling (Batch5) |", report)
        self.assertNotIn("| Culling Distances |", report)

    def test_multiple_segments_picks_latest(self):
        first_start = "[2026-11-02 11:00:00.000] [info] [measure] run=run_test_01 START tick=100 duration=30s"
        first_end = GAME_END.replace("tick_start=1000", "tick_start=100").replace("tick_end=31000", "tick_end=3100")
        game_log = "\n".join((first_start, first_end, GAME_START, "[2026-11-02 12:00:14.999] [info] [measure] run=run_test_01 renut_window_tick_start=5000 renut_window_tick_end=15000 tick_hz=1000", RENUT, GAME_END)).encode()
        report = self.report(game_log=game_log)
        self.assertIn("candidate (scene/config review required)", report)
        self.assertIn("monotonic ticks `1000`–`31000`", report)

    def test_control_comparison_table(self):
        control_report = """# Console Measurement — `run_control_00`
| Event stream | Events | Intervals | FPS | p50 / p95 / p99 / max interval (ms) | 1% low FPS |
|---|---:|---:|---:|---|---:|
| guest | 700 | 699 | 26.000 | 38.000 / 42.000 / 48.000 / 60.000 | 18.000 |
| present | 700 | 699 | 26.000 | 38.000 / 42.000 / 48.000 / 60.000 | 18.000 |

| Renut tick window | Log time at end | Frames | FPS | Render busy mean ms/frame | GPU mean ms/frame | Draws/frame |
|---|---|---:|---:|---:|---:|---:|
| 1000–11000 | 2026-11-02T11:00:15 | 260 | 26.00 | 32.00 | 30.00 | 50.0 |

| CPU tick window | Profile FPS | Total CPU% | Main CPU% | Render CPU% | Clocks CPU/GPU/RAM MHz | Cores / mask | Audio misses |
|---|---:|---:|---:|---:|---|---|---:|
| 1000–11000 | 26.0 | 220.0 | 95.0 | 80.0 | 1020.0/460.8/1600.0 | 4 / 0xF | 0.0 |
"""
        report = self.report(control_id="run_control_00", control_report=control_report)
        self.assertIn("## Comparison against Control (`run_control_00`)", report)
        self.assertIn("| Guest FPS (Swap) | 26.00 | 30.00 | +4.00 | ↑ |", report)
        self.assertIn("| Render busy mean (ms) | 32.00 | 20.00 | -12.00 | ↓ |", report)


if __name__ == "__main__":
    unittest.main()
