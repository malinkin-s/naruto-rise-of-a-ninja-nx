# Reproducible Scenarios — Candidates

These are **candidates**, not validated Switch replays. The owner reports an existing save near a place that consistently drops below 30 FPS, with a CPU or GPU utilization display reaching 100% (owner statement, 2026-11-02). The save path/hash, route, display source and limiting subsystem are still unknown. Historical hot scenes: Konoha in `docs/culling-solutions-log.md` §1/§5; fight in `docs/port-journal.md` §Measurements. PC input examples exist in `tools/pc/inputs/`; the accepted Switch launch is the owner-operated Sphaira forwarder (`console-run-workflow.md`). `nxtest.sh` netloader input scripts are not evidence for that path.

| ID | Purpose / primary metric | Initial state | Input | Required checkpoints / abort |
|---|---|---|---|---|
| `village-view-v1` | Owner's nearby sub-30-FPS hotspot; first classify CPU/GPU/wait limit, then choose a module metric | Save menu shows `PLAYER SAVE 1`, lower `AUTOSAVE` selected, `The Leaf Village`, play time 01:04:12; owner confirms album item 3 is the immediate post-load rooftop position; save file/hash TBD | From the item-3 roof, reach the video's first frame by the large round tower (movement between these checkpoints not captured), cross the narrow bridge to the large tree, then stand facing the tree | Use the existing images once as positioning instructions; for each run record save identity, route/start event, observed clocks, draw count and log interval. Abort on wrong scene or load during interval; new media is optional |
| `village-route-v1` | Traversal/loading; frame-time outliers, IO/cache and audio | Frozen Konoha save TBD | `nx_konoha.nxinput` is a PC candidate only | Route landmarks, event times, save state; abort if route diverges |
| `fight-v1` | Fight effects; GPU/CPU frame cost and pacing | Match setup/character/arena TBD | PC `tools/pc/scenarios/fight.sh` is a candidate | Start, move sequence, end/timeout; abort on different AI/route outcome || `boot-menu-v1` | Functional regression and cold shader/load behavior | Fresh process, known user data | `input_script` candidate | Logos/menu/error counters; separate cold and warm |
| `save-load-v1` | Functional and IO regression | Copy of a known save, never the original | `new_game_to_autosave1.nxinput` is a PC candidate | Save created, reload state, thumbnail; abort on mismatched save |

Example schema (illustrative, not an executable file):

```yaml
id: village-view-v1
kind: performance
initial_state: {save_sha256: TBD, location: TBD, camera_checkpoint: TBD}
input: {format: manual-route-pending, path: TBD, sha256: TBD, start_event: TBD}
warmup: {end_event: TBD, shader_cache_class: warm}
measure: {start_event: TBD, end_event: TBD, primary_metric: classification-pending}
checkpoints: [{event: TBD, scene_or_draw_signature: TBD, optional_visual_rule: TBD}]
abort_on: [wrong_save, route_divergence, clock_change, missing_metrics, crash]
artifacts: [run_metadata, compact_log_summary, optional_metric_stream]
```

## Replay and state findings

`sdk/src/input/input_system.cpp` §input_record/input_replay uses `NXINPUT 1` state changes on an input-read clock capped at 100 ms between polls. `sdk/src/input/switch/switch_input_driver.cpp` §RouteRecording has separate `input_play`: elapsed milliseconds since a Minus-button start and a different line format. Neither proves identical game ticks or AI state. `tools/pc/scripted.sh` can copy a save snapshot (`SAVE=`), but its `grim`/`hyprctl` capture conflicts with `GEMINI.md` §Desktop Safety. If a visual regression needs evidence, use renderer captures (`tools/pc/frames.sh`, `app/src/naruto_test_shots.cpp`); performance runs do not require media.

**Future dev-only hook task, not implemented:** choose one canonical input format at the common input boundary; add an explicit start event after save load, a monotonic replay index, game tick/event markers, checkpoint hashes or stable scene identifiers, and abort on divergence. Keep real controller input available for an emergency stop. First measure whether frame/tick/event coupling preserves route under different frame rates, loading pauses and AI randomness. Do not assume a full memory state reset is safe; compare save-based resets before proposing one. Keep small non-content input recipes in Git only after review; saves, raw media and game data stay outside Git (`GEMINI.md` §Saves & Assets Safety).

## Owner capture reviewed on 2026-11-02

- DBI HTTP album `192.168.0.165:1234`, Naruto items 1–4 (1280×720 JPEG) and item 5 (21.87 s H.264 video). Content was viewed from temporary `/tmp` copies; no game media was committed. The save-selection image is item 2; the near-start rooftop view is item 3; the fixed hotspot view is item 4. Item 4 SHA-256: `60439b75dba4f7882a98108c6ed8cb3ca6f6b812d6a1d377de31beb7f7c4f430`; video item 5 SHA-256: `3d595a53ab5ccda8bf21b1748de403184d35d037164eeb298a05084aa9b7a315`.
- Item 3 visibly shows 30.8 FPS. Item 4 visibly shows 27.3 FPS, render output 1280×720, CPU clock around 1026 MHz, GPU 460.8 MHz and RAM around 1600 MHz. Its overlay shows a CPU utilization field at 100% and GPU around 65%. These are **single captured observations**, not a segment average or proof of a CPU bottleneck.
- The owner confirms album item 3 shows Naruto on the roof **immediately after loading the selected save** (owner correction, 2026-11-02). The video begins later on a roof near a large cylindrical structure; movement from the item-3 spawn to the video's first frame is not captured. In the video, Naruto runs along rooftops and across a bridge, stops by the large tree after roughly 9 s, and holds a near-stationary camera for the rest of the clip. The captured route is a candidate for a manual pilot, not yet a validated replay.
- The images/video were a one-time aid to name the location and route. **Routine performance runs use FTP logs and numeric metrics.** Do not ask for new screenshots or video unless log checkpoints cannot establish the same scene or a graphics defect needs direct evidence.

**Remaining checks:** identify which hashed autosave file the selected menu item loads; document the short item-3-to-video-start movement; repeat the spawn and fixed camera checkpoints after a fresh launch; associate a new FTP profile with that exact measured interval. Do not treat a CPU/GPU percentage alone as proof of the limiting stage; pair it with per-thread busy/wait and GPU frame time at observed stock clocks. A local `out/saves/nx_konoha/` directory exists (directory listing, 2026-11-02), but its identity relative to the console save is unknown; it was not opened. Later choose whether manual positioning suffices or tick/event-based replay is needed.

## Console save inventory — read-only FTP, 2026-11-02

The console save root is `/switch/naruto-nx/naruto/B13EBABEBABEBABE/555307E5/00000001/`. Each file below is 262,144 bytes; SHA-256 was computed from an in-memory FTP read. The save bytes were not retained or edited. The matching header files have no literal `The Leaf Village` marker in ASCII or UTF-16LE; FTP `MDTM` returns the same `1970-01-01` placeholder for all three.

| Directory / file | SHA-256 |
|---|---|
| `PlayerSave1.ninjasave/Save.dat` | `d9b347235a382ef7017ebeaab09620b6137fe0f11220e5f72917ea1ad4e0b0f0` |
| `KonohaAutosave.ninjasave/Save.dat` | `dfee437655e1141156f8d2fd383e30bf46b65029664d0a4506f37922c4066386` |
| `Autosave.ninjasave/Save.dat` | `bb00d3c4634ddfb6f2620c8c3ebb4668c159e05c85b31370568c2f2e4ba63f55` |

The latest game log (`naruto_041.log`, SHA-256 `31ddda6670befd84a7a8b085f85470abf7028acf59076cf1668ffb1acd38d934`) explicitly lists `PlayerSave1.ninjasave` as **Player Save 1**, `KonohaAutosave.ninjasave` as **Leaf Village Autosave**, and `Autosave.ninjasave` as **Autosave** at 17:57:05.570. At 17:57:36.454–36.569 it opens all three in sequence, consistent with menu inspection; at 17:57:39.493 it opens `PlayerSave1.ninjasave` again. This later open makes `PlayerSave1` a candidate for the gameplay load in that log, but there is no run-linked checkpoint proving it is the owner's pictured rooftop load. The lower `AUTOSAVE` menu item in the earlier capture maps by displayed name to `Autosave.ninjasave`; whether that capture and `naruto_041.log` are the same execution is **unknown**. Do not merge their save identities.

For `village-view-v1`, record the selected menu slot and the three hashes immediately before a measured run, plus the later single-file open and rooftop checkpoint in the same Run ID. Preserve all three files. The prepared diagnostic build and one-run TOML are listed in `docs/project/measurement-build-2026-11-02.md`.
