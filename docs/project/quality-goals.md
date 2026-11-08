# Quality Goals and Scope

**Fact:** the game's own pacing is documented as 30 Hz in the open world and 60 Hz in fights (`docs/port-journal.md` §Decisions). `README_ru.md` §State reports 0.1.4 handheld stock 720p Konoha at 25–30 FPS; fight numbers at stock 720p are from an older release. These are historical reports, not a current baseline.

**Owner intent:** a native-feeling 720p port at stock Switch clocks. The exact meaning of “full speed” and the acceptance gate remain decisions after baseline. Do not reuse numerical targets from the superseded `port-dev-log.md`.

| Area | Mode / conditions | Desired behavior | Metric or check | Threshold | Status | Source |
|---|---|---|---|---|---|---|
| Game speed | World / fight | Native simulation speed | Gameplay-clock drift vs reference, checkpoint timing | TBD | Not measured | `docs/port-journal.md` §Decisions |
| FPS | Handheld 720p, stock clocks | Native mode cadence | Mean FPS per segment, 1% low | TBD | Historical only | `README_ru.md` §State |
| Frame pacing | Same | Even displayed intervals | Present-time distribution, long-frame count | TBD | Not measured | `app/src/renut_engine/perf/frame_stats.cpp`; protocol |
| Docked performance | Docked 720p, stock clocks | Same functional behavior | Same metrics, separate configuration | TBD | Not measured | `app/naruto_switch_defaults.toml` |
| Stability | Boot, play, save/load, exit | No lost progress or blocking failure | Run outcome, crash reports, save round-trip | TBD | Partial historical report | `README_ru.md` §State |
| Graphics | World, fight, transitions | Correct scene and UI | Captured-frame checkpoints, manual review | TBD | Partial historical report | `docs/culling-solutions-log.md` |
| Audio / input | Four-core Sphaira forwarder acceptance path | Playable sound and controls | Audio misses, route and input checkpoints | TBD | Historical report only | Owner workflow 2026-11-02; `README_ru.md` §State |
| Video | Bink scenes | Correct playback | Per-video checklist | TBD | Early scenes reported working | `README_ru.md` §State |
| Memory / IO | Long play and loads | No OOM or unbounded growth | Heap/cache peaks, load times, failures | TBD | Not measured | `docs/archive/release-0.1.3.md` §Known issues |
| DLC | Character engines | Owner decision | Functional checklist | TBD | Out of current implementation | `app/naruto_manifest.toml` |

## Owner decisions after baseline

1. Must both handheld and docked meet the same gate? Confirm 720p and stock clock policy; the accepted launch path uses a four-core/39-bit Sphaira forwarder (owner workflow 2026-11-02).
2. Define “full speed”: game-clock accuracy, average FPS, low-percentile FPS, displayed frame-time distribution and allowed interruptions. Set thresholds from baseline and desired experience, not from a convenient observed value.
3. Define required coverage: full base story, fights, videos, saves, DLC, optional modes and session length.
4. Three-core title override is outside the current acceptance path. Reopen it only as a separately scoped compatibility task; do not mix its data with forwarder runs.

Record numerical decisions in an ADR with baseline Run IDs. A mode marked **passes** needs the agreed scenario suite and repeatability protocol; an old release note cannot grant that status.
