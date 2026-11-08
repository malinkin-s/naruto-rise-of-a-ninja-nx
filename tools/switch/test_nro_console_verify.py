"""Unit tests for `nro_console_verify.py` (D7 harness).

Mirrors `test_ftp_run_summary.py` structure: report rendering, window-join/validity
gating, crash classification, symbolization.

Notes: `symbolize` in nx_crashes requires a real ELF file (llvm-addr2line) which is
not available in this environment; the symbolization test therefore exercises the
harness's delegation via a stubbed nx_crashes.symbolize and validates the harness
contract (offset substitution + no-elf guard). Real-ELF symbolization is documented
as environment-limited, not as a passed check.
"""

import unittest
from unittest.mock import patch

import nx_crashes
from nro_console_verify import (
    classify_crash,
    decide_verdict,
    fetch_crash_records,
    metrics_status_of,
    render_verification_report,
    symbolize_crash,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def make_game_segments(run_id="run_test_01"):
    """Return a game log with a unique START/END segment carrying a Renut marker."""
    start = (
        "[2026-11-02 12:00:00.000] [info] [measure] run=" + run_id
        + " START tick=1000 duration=30s"
    )
    end = (
        "[2026-11-02 12:00:31.000] [info] [measure] run=" + run_id
        + " END tick_start=1000 tick_end=31000 "
        "guest_ordinal_first=10 guest_ordinal_last=910 guest_events=901 guest_intervals=900 guest_fps=30.000 "
        "guest_p50=33.333 guest_p95=34.000 guest_p99=40.000 guest_max=45.000 guest_1pct_low=25.000 "
        "present_events=901 present_intervals=900 present_fps=30.000 present_p50=33.333 present_p95=34.000 present_p99=40.000 present_max=45.000 present_1pct_low=25.000 overflow=false"
    )
    return start + "\n" + end


def make_profile():
    return (
        "[measure] run=run_test_01 cpu_window_tick_start=5000 cpu_window_tick_end=15000 tick_hz=1000 "
        "[measure] run=run_test_01 renut_window_tick_start=1000 renut_window_tick_end=31000 tick_hz=1000\n"
        "[measure] run=run_test_01 cpu_window_tick_start=5000 cpu_window_tick_end=15000 tick_hz=1000\n"
        "[renut] 10.0 s: 300 game frames (30.00 fps), render thread busy 20.00 ms a frame (300 frames), GPU 15.00 ms a frame (300 frames); 9000 draws"
    )


def base_identity():
    return {
        "run_id": "run_test_01",
        "scenario": "nro-nx-fullspeed-v1",
        "scenario_version": "v1",
        "config_id": "config-720p-fullspeed-v1",
        "commit": "18ddecd356c9dff04f2af0dfa80d37b63d81cf40",
        "build_id": "nro-pgo-lto",
        "nro_sha256": "unknown",
        "shader_package_sha256": "unknown",
        "console_model": "unknown",
        "firmware": "unknown",
        "launch_method": "sphaira_forwarder",
        "forwarder_cpu_cores": 4,
        "forwarder_address_space": "39-bit",
        "mode": "handheld",
        "cpu_mhz": "1020",
        "gpu_mhz": "460",
        "ram_mhz": "unknown",
        "core_mask": "unknown",
        "render_resolution": "unknown",
        "warmup_class": "cold",
        "measured_start": "not measured",
        "measured_end": "not measured",
        "measured_duration": "not measured",
        "guest_ordinal_first": "not measured",
        "guest_ordinal_last": "not measured",
        "clock_changes": "unknown",
    }


def make_metrics_text():
    """A metrics text mimicking ftp_run_summary.render_report output (valid candidate)."""
    return (
        "# Console Measurement — run_test_01\n\n"
        "Evidence: FTP game log `naruto_NNN.log` (SHA-256 `unknown`). Raw logs were held in memory only.\n\n"
        "**Status: candidate (scene/config review required).** Segment: valid.\n"
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
class TestRendering(unittest.TestCase):
    def setUp(self):
        self.game_data = make_game_segments()
        self.profile_data = make_profile()

    def test_valid_segment_rendering(self):
        report = render_verification_report(
            base_identity(), "run_test_01", "naruto_NNN.log", self.game_data, self.profile_data,
            metrics_text=make_metrics_text(),
            crash_records=[],
        )
        for section in ("## Identity and validity", "## Acceptance procedure (canonical)",
                        "## Crash/error classification", "## Findings", "## Verdict"):
            self.assertIn(section, report)
        self.assertIn("valid", report)

    def test_render_delegates_metrics_to_ftp_run_summary(self):
        # With no pre-supplied metrics_text, render_report is invoked internally.
        with patch("nro_console_verify.render_report") as mock_report:
            mock_report.return_value = make_metrics_text()
            report = render_verification_report(
                base_identity(), "run_test_01", "naruto_NNN.log", self.game_data, self.profile_data,
                crash_records=[],
            )
        mock_report.assert_called_once()
        self.assertIn("delegated", report)

    def test_metric_status_normalized(self):
        status = "candidate (scene/config review required)"
        self.assertEqual(metrics_status_of(status), "candidate")

    def test_metrics_pending_when_no_segment(self):
        report = render_verification_report(
            base_identity(), "run_none", "naruto_NNN.log", "", "",
            metrics_text="pending", crash_records=[],
        )
        self.assertIn("pending", report)


# ---------------------------------------------------------------------------
# Validity gating
# ---------------------------------------------------------------------------
class TestValidityGating(unittest.TestCase):
    def setUp(self):
        self.game_data = make_game_segments()
        self.profile_data = make_profile()

    def test_partial_window_is_pending(self):
        game = make_game_segments()
        game = game.replace("END tick_start=1000 tick_end=31000 ", "END tick_start=1000 tick_end=32000 ")
        report = render_verification_report(
            base_identity(), "run_test_01", "naruto_NNN.log", game, self.profile_data,
            metrics_text=make_metrics_text(), crash_records=[],
        )
        self.assertIn("pending", report)

    def test_wrong_run_is_pending(self):
        report = render_verification_report(
            base_identity(), "run_wrong", "naruto_NNN.log", make_game_segments("run_wrong"),
            self.profile_data, metrics_text=make_metrics_text(), crash_records=[],
        )
        self.assertIn("pending", report)

    def test_clock_mismatch_is_pending(self):
        game = (
            "[2026-11-02 12:00:00.000] [info] [measure] run=run_test_01 START tick=1000 duration=30s\n"
            "[2026-11-02 12:00:31.000] [info] [measure] run=run_test_01 END tick_start=1000 tick_end=31000 "
            "guest_ordinal_first=10 guest_ordinal_last=910 guest_events=901 guest_intervals=900 guest_fps=30.000 "
            "guest_p50=33.333 guest_p95=34.000 guest_p99=40.000 guest_max=45.000 guest_1pct_low=25.000 "
            "present_events=901 present_intervals=900 present_fps=30.000 present_p50=33.333 present_p95=34.000 present_p99=40.000 present_max=45.000 present_1pct_low=25.000 overflow=false"
        )
        report = render_verification_report(
            base_identity(), "run_test_01", "naruto_NNN.log", game, self.profile_data,
            metrics_text=make_metrics_text(), crash_records=[],
        )
        self.assertIn("pending", report)

    def test_missing_metrics_is_pending(self):
        report = render_verification_report(
            base_identity(), "run_test_01", "naruto_NNN.log", make_game_segments(),
            self.profile_data, metrics_text="not measured", crash_records=[],
        )
        self.assertIn("pending", report)


# ---------------------------------------------------------------------------
# Crash classification
# ---------------------------------------------------------------------------
class TestCrashClassification(unittest.TestCase):
    def test_panic(self):
        text = "Aborted: game process terminated by signal 6\nThe software was closed because an error occurred"
        kind, _ = classify_crash(text)
        self.assertEqual(kind, "panic")

    def test_primitive_error(self):
        text = "Traceback (most recent call last)\n  File 'foo.py', line 1, in <module>\n  Exception: boom"
        kind, _ = classify_crash(text)
        self.assertEqual(kind, "primitive_error")

    def test_ambiguous(self):
        text = "Aborted: ...\nUnhandled Exception: boom"
        kind, _ = classify_crash(text)
        self.assertEqual(kind, "ambiguous")

    def test_unknown(self):
        kind, _ = classify_crash("some neutral report text with no crash markers")
        self.assertEqual(kind, "unknown")


# ---------------------------------------------------------------------------
# Decision verdict
# ---------------------------------------------------------------------------
class TestDecisionVerdict(unittest.TestCase):
    def test_valid_no_crash(self):
        verdict, reason = decide_verdict([], "valid")
        self.assertEqual(verdict, "valid")

    def test_invalid_on_crash(self):
        verdict, reason = decide_verdict([{"kind": "panic", "reason": "abort marker"}], "valid")
        self.assertEqual(verdict, "invalid")
        self.assertIn("crash", reason)

    def test_pending_when_no_crash_and_metrics_pending(self):
        verdict, reason = decide_verdict([], "pending")
        self.assertEqual(verdict, "pending")


# ---------------------------------------------------------------------------
# Symbolization (harness delegation via mocked nx_crashes.symbolize)
# ---------------------------------------------------------------------------
class TestSymbolization(unittest.TestCase):
    def test_symbolize_crash_delegates_to_nx_crashes(self):
        """The harness must call nx_crashes.symbolize; verify with a stub."""
        stub = lambda text, elf: (
            text.replace("0x10000000", "SYMBOLIZED_FUNC")
            if elf else text
        )
        with patch.object(nx_crashes, "symbolize", stub):
            result = symbolize_crash("naruto + 0x10000000\nnaruto + 0x20000000", "fake-elf")
        self.assertIn("SYMBOLIZED_FUNC", result)
        self.assertIn("SYMBOLIZED_FUNC", result)
        self.assertNotIn("0x10000000", result)  # offsets were symbolized, not left raw

    def test_symbolize_crash_returns_text_when_no_elf(self):
        result = symbolize_crash("naruto + 0x1234", None)
        self.assertEqual(result, "naruto + 0x1234")


# ---------------------------------------------------------------------------
# Fetch (no FTP, no ELF)
# ---------------------------------------------------------------------------
class TestFetchCrashes(unittest.TestCase):
    def test_fetch_without_ftp_returns_empty(self):
        records = fetch_crash_records(None, since=100)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
