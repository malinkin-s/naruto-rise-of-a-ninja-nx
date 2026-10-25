# naruto-nx: handoff (2026-10-25)

Hand-off of the Naruto: Rise of a Ninja (Xbox 360) → Nintendo Switch port, written by Claude for the next agent
(Gemini). Read this first, then `docs/port-journal.md` (every step with its evidence and measurements) and
`README.md`. Talk to the user in **Russian**; work in **small steps**, say before each step what you expect and how to
measure it.

## 1. Where the project is

- **Released**: 0.1.1 (pre-release) — https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx/releases/tag/v0.1.1.
  The release holds only `naruto.nro` (no game data). Players make the game's shaders with the **installer page**
  https://malinkin-s.github.io/naruto-nx-installer/ (repo `malinkin-s/naruto-nx-installer`, local
  `~/Projects/naruto-nx-installer`): two files of their disc (`default.xex`, `xeshader.sdb`) in, a zip out
  (`naruto.nro`, `deko3d_glsl.bin`, `deko3d_shaders.bin` = shaders compiled for the console in advance).
- **Works on the console**: boot, menus, saves, cutscenes, story mode (Konoha, open world), fights, controller,
  sound. Konoha ground shadows fixed (Renut ignored the game's depth bias).
- **Performance, stock handheld clocks (CPU 1020 MHz, GPU 460.8 MHz)**:
  - fights: 32–47 FPS at 720p, 46–58 FPS at 480p (the game runs fights at 60);
  - Konoha: 20–30 FPS; **the worst spot (run `cpu2`, 480p, camera on the heaviest view, static) = 20 FPS**:
    render thread 93 % of core 1 (~47 ms busy a frame, ~3,780 draws a frame → ~12.4 µs a draw), a guest worker
    thread `XThread...62C0` 85 %, the game's main thread 80 % of core 0 (~40 ms a frame), GPU ~33 ms a frame even at
    480p. **All three cores are saturated: CPU-bound, the render thread first.**
  - With the CPU overclocked to 1785 MHz the open world is nearly a stable 30 (the user tested by hand).
  - Sound stutters when FPS drops well below 30 (the game's audio is fed by guest threads that starve).
- **Last commits**: `e520a82` (CPU step 2, generator options), `daec5a5` (CPU step 1, -fno-math-errno). Both are
  built in the `cpu2` run's NRO. Compare `out/runs/cpu2` with `out/runs/rel3` (before steps 1-2; same release build
  otherwise) — but the routes differ; for a fair A/B use the same spot and view.

## 2. The user's rules (keep them)

- Answers in Russian, short steps, hypotheses + the cheapest experiment before each step.
- **Never commit game data or code generated from it**: `game/`, `app/generated/`, `out/`, shader dumps, GLSL,
  DKSH, saves, `installer test/` are git-ignored. The release NRO must be built with `SA2_RENUT_RELEASE_SHADERS=ON`
  (no translated game shader inside).
- **Desktop safety** (Hyprland crashed twice): no screen grabs (no grim/hyprctl screenshots); frames only from the
  renderer (`tools/pc/frames.sh`, the console's `test_shots`); watch RAM (keep ≥ 3–4 GB free) and `/dev/shm`; PC runs
  clean `/dev/shm/xenia_memory_*` before/after (`tools/pc/shm_clean.sh`, done by `launch.sh`); PC game windows on
  workspace 2; no virtual input devices.
- The user builds and tests when they want to: give them the exact command (below) and say what to look at.
- The user sometimes overclocks by hand: **check the `clocks:` line of `rex_profile.log` before comparing runs**.
- Publishing (releases, Pages) needs the user's go-ahead.

## 3. Build and test

Host: Arch Linux. Switch builds run in Docker (`naruto-nx/devkita64`, devkitA64 r30 GCC 16.1).

```bash
tools/codegen.sh                      # the game's code into app/generated + post-codegen steps (both trees)
cmake --build out/pc -j6              # PC build (Renut on Vulkan); also regenerates code when inputs change
tools/switch/build.sh                 # dev NRO with the game's shaders built in: out/nx/naruto.nro
NX_BUILD_DIR=$PWD/out/nx-release tools/switch/build.sh [-reconfigure]   # release NRO (no game shaders)
```

Console test (the user only opens hbmenu's netloader; IP in `tools/switch/nx.env`, 192.168.0.165):

```bash
NX_NRO=$PWD/out/nx-release/naruto.nro tools/switch/nxtest.sh NAME 300 ''          # 5 minutes, the user plays
NX_PROFILE=1 NX_PROFILE_THREADS=Main tools/switch/nxtest.sh NAME 150 '<input script>'   # + stack samples of a thread
```

Results in `out/runs/NAME/`: `nx.log` (every log line; `[renut]` 10-s reports: FPS, render thread busy, GPU,
draws, caches), `rex_profile.log` (each thread's CPU, clocks, audio misses), `shot_<s>.png` + `sheet.jpg` (renderer
frames), `naruto.elf` (for `tools/switch_profile_report.py` and crash reports), crash reports fetched over the
console's FTP (port 5000, when the user turns it on). The release NRO needs `deko3d_glsl.bin` (+ ideally
`deko3d_shaders.bin`) from the installer beside it on the SD (already there on the user's card).

Useful one-liner, game-thread CPU per frame per 10-s interval:
```bash
awk '/^==== /{split($0,a,"game "); split(a[2],b," "); fps=b[1]} /audio:/{match($0,/[0-9]+ requests without data/); r=substr($0,RSTART,RLENGTH)+0} /"Main XThread/{match($0,/CPU [0-9.]+%/); c=substr($0,RSTART+4,RLENGTH-5); printf "%s fps | main %.1f ms | audio miss %d\n", fps, c*10/(fps>0?fps:1), r}' out/runs/NAME/rex_profile.log
```

PC: deterministic replay `REPLAY=tools/pc/inputs/new_game_to_autosave1.nxinput tools/pc/frames.sh NAME 125 20 60 50 ''
--sa2_renderer=renut --renut_vsync=false` (frames in `out/runs/NAME/`); without `--sa2_renderer=renut` the SDK's
Xenos emulation draws the reference picture. Use it to check a codegen change keeps the game logic (same scenes at
the same moments).

## 4. Architecture in brief

- ReXGlue SDK (fork of sa2-nx's, `sdk/`, our changes also in `patches/`), static recompilation of `default.xex`
  and the engine DLL `AI2C.dll` (linked into the NRO). Manifest `app/naruto_manifest.toml`.
- Optimised code generator: `app/codegen_flavor.toml` (registers as locals, float-mode options, step 2 options) +
  `tools/post_codegen.sh` (no-volatile guest memory, loop barriers, direct calls, store cards). Compile flags in
  `app/CMakeLists.txt` (`-ffp-contract=off -fno-strict-aliasing` are REQUIRED; `-fno-math-errno`).
- Renderer: Renut (Direct3D-level, from sa2-nx/banjo-nx) on plume's deko3d back end, `app/src/renut_engine/`,
  retargeted to Naruto's XDK 6274 (`docs/renut-retarget.md`, `docs/d3d-census.md`). Many `naruto_debug_*` cvars for
  diagnostics (skip/log by pixel shader, stencil, caches...).
- Player settings `naruto.toml` next to the NRO (template `app/naruto_switch.toml`); fixed settings
  `app/naruto_switch_defaults.toml`.
- Thread layout: game main thread alone on core 0, render thread pinned to core 1 (priority 0x2C), other guest
  threads on mask 0x7 (`naruto_guest_cores`, new default: fixed most audio starvation).

## 5. Next steps (in this order)

1. **Measure CPU steps 1-2** fairly: same spot/view as `cpu2` with the pre-step build, or keep `cpu2` as the new
   baseline for the worst spot (20 FPS, render thread 47 ms, main 40 ms, worker 85 %).
2. **Render thread (the first limit at the worst spot)**: ~12.4 µs a draw × ~3,780 draws. Gemini's own plan
   `out/gemini/plans/renut_render_thread_plan.md` and `out/gemini/openworld_cpu.md` §3: SharedConstants dedupe
   (0 reused now), redundant `Deko3DBindUniform` per draw, `banjo_gpu_bool_spec` off (no Naruto shader uses bool
   spec), dead device-snapshot chunks 11816..12428 in `backend/queued.cpp`. Measure with the `[renut]` lines.
3. **Codegen step 3b: `non_argument_as_local`** (r0/r2/r11/r12/f0/v32-63 as locals; sa2-nx: −5.6 % instructions,
   −8.8 % loads/stores). Needs sa2-nx's `tools/non_argument_audit.py` ported and a `non_argument_as_local_keep` list
   (stack probe, SEH funclets, r12 users). Test on the PC replay first (setjmp 0x822CC540 / longjmp 0x822CC220).
4. Other sa2-nx post-codegen steps (`~/Projects/cloned/sa2-nx/tools/post_codegen.py`): indirect call promotion,
   ro_constants, leaf/loop locals, guest CAS, flush-mode flow, vector byteswap, NEON shuffles, cold traps.
5. LTO (`NARUTO_SWITCH_LTO`, gave 2 % before step 3) and PGO later.
6. **Sound**: decouple the game's audio feed from the frame rate if possible (look at the XMA/audio threads and
   `SwitchAudioSystem` in `sdk/src/audio/switch/`), so music does not stutter during dips.
7. Not performance: the **save thumbnail** (black on Load Game): port the PC base's `WriteBackResolve`
   (`~/Projects/cloned/naruto-rise-recomp/app/src/gpu/d3d/resources.cpp`, the lock of a resolve destination at
   `sub_8212C7E8` reads the resolve back) onto Renut (template: `gpu/guest/photo_capture.cpp`,
   `ReadRenderTargetLocked`); the race guard is already in `app/src/naruto_save_thumbnail.cpp`. **Controls**: expose
   the SDK's input options in `naruto.toml`, the user chose **buttons by letter** (A = A) as the default; single
   Joy-Con jutsu assist (`out/gemini/plans/switch_controls_adaptation_plan.md`). The "Saved Game Warning" scroll border
   differs from the Xbox 360 (not investigated).

## 6. Releasing a new version

1. Bump `VERSION` in `app/CMakeLists.txt`; build the release NRO (`NX_BUILD_DIR=$PWD/out/nx-release ...`).
2. Pipeline lists from new console sessions (`switch/naruto-nx/pipeline_list.bin` over FTP) into
   `data/pipeline_lists/`; variants: `python3 tools/deko3d_variant_cache.py --list data/pipeline_lists/*.bin --glsl
   <installer GLSL> --emit-variants ~/Projects/naruto-nx-installer/release/deko3d_variants.json --dry-run`.
3. Installer manifest: `node test/naruto_manifest.mjs <game> out/nx-release/naruto.nro <version> out/deko3d_shaders/glsl_opt`
   in `~/Projects/naruto-nx-installer`; `node test/worker_node.mjs <default.xex> <xeshader.sdb>` runs the page's
   worker end to end.
4. GitHub release with `naruto.nro` + `SHA256SUMS.txt` (notes in English and Russian), then push the installer (its
   Pages workflow takes the NRO from the newest release, pre-releases included). README in both languages
   (`tools/readme_badges.py` for the status badge).

## 7. Where things are

| What | Where |
|---|---|
| Journal (read it) | `docs/port-journal.md` |
| Gemini task pipeline | `tools/gemini/` (`run_task.sh`, `rules.md`, `tasks/*.md`); reports `out/gemini/`, plans `out/gemini/plans/` |
| Reference ports | `~/Projects/cloned/sa2-nx` (docs on every optimisation round), `~/Projects/cloned/naruto-rise-recomp` (PC base) |
| Recent console runs | `out/runs/cpu2` (worst spot), `rel3`, `rel2`, `konoha2`, `cards2` (fight) |
| Recorded pad input | `tools/pc/inputs/*.nxinput` (PC replays; console replays drift with load times) |
