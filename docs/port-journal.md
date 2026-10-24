# Naruto: Rise of a Ninja port journal

From `x360-switch-ports/skill/templates/port-journal.md`. The place to think, not a log of everything.

## The game

- Title: Naruto: Rise of a Ninja (Ubisoft Montreal, 2007). Title ID `555307E5` (naruto-rise-recomp docs/dlc.md).
  Region/edition: to confirm (the disc has `Credits_US.bik` and `Credits_EMEA.bik`; sound in en/fr).
- `default.xex` SHA-256 `f8fd8a979fb5451460f820303a6ca4c75e01fd943aed600983cb68fc491af7bd` (7,516,160 bytes).
  Title update: none in our files yet.
- Disc. Code modules (all XEX2):
  - `default.xex`: base 0x82000000, entry 0x821776A0. Draws (D3D9LTCG, XGRAPHC, D3DX9), audio (XAUDLTCG, X3DAUD,
    XMP), online (XONLINE, XHV, XRNMS).
  - `AI2C.dll`: base 0x88000000, entry 0x88399178, SHA-256 `ed760975…0d3d`. Imports only XBOXKRNL/XAPILIB/LIBCMT: the
    game's engine logic, no Direct3D. Character DLCs replace it with `AI2C@1/@2/@3.dll`, each a different code layout
    that needs its own recompiled module (entries 0x883A0CF8, 0x883ADD48, 0x883AEF88; naruto-rise-recomp docs/dlc.md).
  - `LinkApp.xex`: base 0x82000000, entry 0x8205A050, SHA-256 `6b4035d0…198a`. D3D9 (not LTCG) + XUI + XNET: a
    separate application (not in the PC base's manifest). Purpose to confirm.
- Direct3D / XDK build: **2.0.6274** for every library of all three modules (XEX static library list, key 0x200FF).
  Older than Renut's references (N&B 2.0.7645, SA2 2.0.21076); `default.xex` links the **LTCG** Direct3D.
- On the 360: logic in fixed steps, 1/30 s in the open world and menus, 1/60 s in fights; animation, physics and
  timers follow the step (naruto-rise-recomp docs/renderers.md). Video: Bink (`*.bik`). Shaders in `xeshader.sdb`.
- Existing work:
  - PC: jorjbarbosa/naruto-rise-recomp (GPL-3.0, ReXGlue SDK 0.10.0, v0.3.0-beta 2026-10-23), checked at `93feca6`.
    Plays menus, open world, missions and fights with its native renderer; not verified across the whole game.
  - Switch: nobody (refresh 2026-10-24T03:11Z, SwitchPorts README, GitHub search). Relatives: Android ARM64 port
    Masterllgod/naruto-rise-of-a-ninja-port-nativo (static recomp + Vulkan, from 2026-10-14); madkils PC port
    (translation patches).
- Go / no-go: **go** (game-selection.md, candidate 3, taken 2026-10-24): 360 exclusive, a working PC recompilation,
  30 Hz logic in the open world.

## Current stage

Stage: 6 early (the user's priority: the console first), with 3 done on the PC: menus, story, gameplay, a fight, saves.
The NRO without a renderer boots and runs on the console (automated over nxlink); next: Renut on deko3d.
Goal: codegen clean for `default.xex` + `ai2c.dll`, the missed-code sweep (SOL-CODE-1) done, every manifest fix with
evidence: done 2026-10-24. Stage 3 goal: boot, menus, gameplay, cutscenes, saves on the PC (SOL-ROUTE-2). Next: input
scripted input (SOL-TEST-2) done; next: play to the first real autosave and load it, a mission, a long session.

## Known (with evidence)

- XDK 2.0.6274 in all three modules — XEX header 0x200FF (scratch script `xexlibs.py`).
- The D3D device is 22,400 bytes (0x5780) — naruto-rise-recomp `app/src/gpu/d3d/device.h:575` `kDeviceBytes`.
  N&B 0x5E00, SA2 0x6080 (sa2 renut-renderer.md): Renut's offsets must all be re-read for this game.
- The Direct3D functions Renut hooks exist as separate functions despite LTCG; the PC base names them:
  Swap 0x821280B0, DrawIndexed 0x821024A8, DrawVertices 0x8212C7E8, BeginVertices 0x8212EA18, Resolve 0x8212D750,
  BlockOnFence 0x82139090, SetGammaRamp 0x8212B3E0, a window-scissor writer 0x82128270, the ring reserve 0x8212F608,
  a packet-writing leaf 0x8212F7E0, the scene flush 0x821083B8 — `app/src/gpu/d3d/*` (69 `REX_HOOK_RAW` in all).
- The PC base's renderer (`app/src/gpu/`, ~45,000 lines) = the same idea as Renut: hooks at the D3D level, the
  ring's packets discarded, draws translated on its own thread, shaders by XenosRecomp ahead of time — but:
  - its two back ends are written to the APIs directly: `backend/d3d12/backend.cpp` 3,841 lines (502 D3D12
    references), `backend/vulkan/backend.cpp` 1,977 lines (raw `vk*`); plume only in part. A Switch back end would be
    a third one from scratch behind `backend/backend.h` (45 virtual methods);
  - 42 of its files include `<windows.h>`;
  - PC features on the hot path: interpolated frames above 30 FPS (objects, camera, skinned poses, particles), MSAA,
    1.5x, 25 diagnostics files, a failure channel;
  - shaders compiled at build time from `xeshader.sdb` and embedded in the executable (fine on PC, not shippable on
    the Switch: SOL-SHIP-1);
  - occlusion queries (light glows only) answered with a fixed value; options-menu labels missing (open defect).
- The PC base's SDK patches we will likely need: `codegen-alt-version-dll-modules.patch` (DLC engines),
  `obdosdevices-relative-paths.patch`; the others are PC/Xenos specific.

- **Guest DLLs on the Switch are solved by sa2-nx** (its `Data_DLL.xex`, sa2-nx `adf3a4e`): CMake builds the module
  as a static archive, `ld -r --force-group-allocation` + `objcopy --localize-hidden --redefine-sym` make one object
  with renamed `ReXModule_Register_<name>` / `ReXModule_GetImageInfo_<name>` (`app/CMakeLists.txt:373-396`),
  `src/sa2_static_modules.cpp` registers them (`rex::system::RegisterStaticModule`), and
  `KernelState::LoadUserModule` looks there first (`sdk/src/system/kernel_state.cpp:769`). Registration of the function
  table happens **at load time**, keyed by guest path, with an image base/size check: four AI2C revisions sharing base
  0x88000000 can sit in one NRO because the game loads one per session (naruto-rise-recomp docs/dlc.md).
- The PC base's `codegen-alt-version-dll-modules.patch` (codegen only: snapshot each DLL image before the next one
  at the same base overwrites it; DLL-DLL overlap = alternative versions, a warning) does not apply to the sa2-nx
  fork as is (`git apply --check`: context at `project_recompiler.cpp:262`, sa2's `REXGLUE_DUMP_IMAGE` block); its
  logic is small and ports by hand. `obdosdevices-relative-paths.patch` applies cleanly.
- Both SDKs are upstream ReXGlue v0.10.0 (sa2-nx fork from `c94f5eb`, PC base manifest `sdk_version = "0.10.0"`):
  the PC base's seeds (`analysis-seeds.toml` 40 lines, `ai2c*-seeds.toml`) should carry over.

- **First codegen (2026-10-24)**: the sa2-nx SDK fork (`sdk/`, our two changes in
  `patches/sdk-naruto-on-sa2-fork.patch`), host `rexglue` built with `cmake --preset linux-amd64` (clang 22),
  `rexglue codegen app/naruto_manifest.toml` with the PC base's seeds: exit 0, 0 warnings, 13.8 s, 316 files;
  30,466 functions registered (24,123 `default.xex`, 6,343 `AI2C.dll`). Two lines
  `BaseHeap::Release failed because address is not a region start` (after AI2C's Validate and at exit): to check
  whether the second same-base DLL load path causes it (only one DLL now, so probably not; watch when DLC engines
  are added).
- **Same disc revision as the PC base**: every `sub_*` address their source names (116, hooks and helpers) is a
  function start in our codegen (`out/pc_hooks.txt` vs `SetFunction` list). Their hook map applies as is.

- **SOL-CODE-1 sweep (2026-10-24)**, tools from sa2-nx (`tools/`, GPL-3.0) with Naruto's code ranges from the PE
  section tables (`default` .text+BINK 0x820C0000-0x826CFE34, AI2C .text 0x88040000-0x883A0C20):
  - gaps + data pointers into gaps (`tools/gap_pass.py`, our one-pass take on `gap_fixpoint.py`): `default` 106 + 8
    accepted (2 passes, then fixpoint) in `app/gap-seeds.toml`, 36 of them targets of data words (vtables at
    0x8208C4xx-0x8208C9xx); AI2C 0 (1 candidate, rejected). Functions 23,857 -> 23,965.
  - `find_gaps.py` miscounted: the generator drops unreachable instructions (`b` after `b`), so "start + 4 x
    comments" ended functions early (sub_880412C8: 309 comments, 318 instructions, its tail 0x8804179C-0x880417BC
    reported as a gap). Fixed to measure from the last label: AI2C gaps >= 8 bytes 3,115 -> 11, `default` 624 -> 408
    (the rest: 305 data pairs inside .text, C++ EH data, 11 zero runs).
  - jump tables (`switch_check.py`): truncated 0, wrong targets 0, missed 0 in both modules. 6 "odd shapes" in
    `default` are function-pointer tables in .data/.rdata (every code value a registered function): safe.
    `pointer_audit.py` "built in code" 239 = inline jump tables after `bctr`: not entries.
  - setjmp/longjmp: `default` 0x822CC540/0x822CC220 (PC base seeds, the only functions storing/loading r1 through
    r3/r7); AI2C has none (no r1 store/load through any register but r1).
  - Exceptions: `default` imports RtlRaiseException, RtlUnwind, RtlCaptureContext; `sub_822D837C` restores a whole
    context and jumps to r3 (EH unwinding, called from sub_822CFB70 <- sub_822CFCB8/sub_822CFE28). The SDK's
    RtlUnwind is a stub that logs `[STUB] RtlUnwind called`: watch the PC logs for it.

- **First PC boots (2026-10-24)**, `app/` = the SDK's `init` template (`rexglue_setup_target(naruto GPU_PLUGINS
  xenos)`), Linux, clang 22, Release, RTX 3050 / Vulkan (Xenos emulation), run with `tools/pc/run.sh`:
  1. no GPU (`gpu_plugin not set`): the template builds without GPU plugins; fixed in CMake + `--gpu_plugin=xenos`;
  2. `Failed to load shared library for module 'ai2c.dll'`: the generated registry passes the bare name
     `naruto_AI2C`, which Windows' LoadLibrary resolves (".dll", the exe's folder) and dlopen does not. The PC base
     is Windows-only, so it never met this. Fixed in `sdk/src/core/dynlib_posix.cpp` (lib<name>.so next to the
     executable first; dlerror logged) — in `patches/sdk-naruto-on-sa2-fork.patch`;
  3. boot 4 (100 s): `Module 'ai2c.dll' registered 6343 functions`; logo (20 s), title screen "PRESS START BUTTON"
     (45 s), attract demo of Konoha (80 s); no fatal, no unregistered call, no `[STUB] RtlUnwind`; 45 pipelines;
     audio steady (1876 frames with data per 10 s, 0 silence). Screenshots kept locally only (game content).
  Log oddities to look at later: `game:\ERRasser.log` and `game:\Menu` opens fail (probably debug probes),
  `ShaderDumpxe:\CompareBackEnds` (debug device), `\Device\Image` open fails after the AI2C load.

- **Scripted input (2026-10-24)**: the sa2-nx SDK's `input_script` cvar (`'seconds:button[:hold],...'`, wall time
  from the first input poll; while set, user 0 reads only the script, focus not needed) driven by
  `tools/pc/scripted.sh NAME <scenario>`: own user data root per run (`SAVE=<snapshot>` copies saves in), window
  screenshots at given times (hyprctl + grim, window only) and a contact sheet, all in `out/runs/NAME/` (ignored).
  The PC base's `input_replay.cpp` (recording from a real pad) was not needed. Scenarios in `tools/pc/scenarios/`.
  The main menu comes up between 22 and 33 s from run to run, so scenarios press START every 4 s up to 34 s (it
  does nothing in the main menu) and choose from 40 s.
  - story1: Story Mode -> New Game -> "Saved Game Warning" -> intro (full moon) -> Konoha, Iruka's dialogue, HUD,
    tutorial hint; three save slots created (`XamContentCreate ... result 00000000`).
  - load1/load2 (`fight.sh`): Fight Mode -> Tournament -> Naruto vs Sasuke: fight HUD, timer, Sasuke's fire jutsu
    sequence, knock-downs; no errors.
  - load3 (`story_load.sh`): Load Game lists Autosave / Player Save 1, then "Damaged saved game": expected, the slots
    hold only the `UBISG` header (33 non-zero bytes of 262,144): New Game reserves them, progress is written at the
    first story autosave, which story1 did not reach.
  - `BaseHeap::Release failed because address is not a region start` x2-6 after saves and loads: no visible effect.
    XMA "silence ... no progress" bursts at the start of gameplay: listen for audio gaps later.

- **Pad recording (2026-10-24)**: `input_record=<file>` / `input_replay=<file>` added to the SDK's
  `input_system.cpp` (in `patches/sdk-naruto-on-sa2-fork.patch`): every change of user 0's pad (connection, buttons,
  triggers, full stick values) as `S <us> <connected> <buttons> <lt> <rt> <lx> <ly> <rx> <ry>`, timed on an input
  clock that advances only while the game polls, at most 100 ms between polls (idea from naruto-rise-recomp's
  `input_replay.cpp`), so loads without polling do not shift the presses. `tools/pc/record.sh NAME` records a session
  from an empty user data root into `tools/pc/inputs/NAME.nxinput` (pad states only, committed) and keeps its saves
  in `out/saves/NAME/`; `REPLAY=... tools/pc/scripted.sh` plays it back. Checked: a 25 s recording (START at 22.4 s,
  A at 24.3 s, a real pad) replayed to the Single Player Menu. The game is not deterministic (fight AI, load
  lengths): a replay follows the recorded path, not the same frames; long replays may drift.

- **Saves round-trip (2026-10-24)**: the user's 7-minute pad session (`tools/pc/record.sh first_autosave`: 6,438
  pad states, 4 story autosaves, `Autosave/Save.dat` with 6,499 non-zero bytes) still loaded as "Damaged saved
  game": the game creates `Autosave.ninjasave` and opens `autosave.ninjasave` (`XamContentCreate ... mode 3 -> none
  (result 00000003)`). Content names are case-insensitive on the console and on Windows, not on Linux. Fixed in
  `sdk/src/system/xam/content_manager.cpp` (`ChildIgnoringCase` for the package and its header). After: `mode 3 ->
  open (result 00000000)`, Load Game lists "Autosave, Old Gatehouse 00:03:54" and loads into the night scene with the
  jutsu scroll. Snapshot for scenarios: `out/saves/first_autosave` (local).
  - `tools/pc/scripted.sh` once captured the desktop (grim shoots a screen region; the game window was not on the
    visible workspace): it now shoots only when the window is on the active workspace and visible.
- **Replaying recordings (2026-10-24)**: the whole 7-minute session replayed matched the recording up to the first
  story autosave (New Game slots +25.6 s in both; autosave 1 at +97.3 s recorded, +98.3 s replayed), then drifted
  (autosave 2 at +128 s against +173 s). As the user expected: one press landing elsewhere changes everything after
  it. So recordings are cut right after an autosave (`tools/pc/trim_input.py`, ending with the pad released) and the
  next piece starts from that save. `new_game_to_autosave1.nxinput` (100 s, 758 states): autosave at +93.4 s with
  6,339 non-zero bytes, "MISSION UPDATE: Steal the Forbidden Scroll", Naruto idle after the end; its saves are the
  snapshot `out/saves/autosave1` for the next piece (`tools/pc/record.sh NAME out/saves/autosave1`).

- **First Switch NRO (2026-10-24)**, the user's priority: reach the console fast, renderer later. `tools/switch/build.sh`
  in Docker image `naruto-nx/devkita64` (devkitpro/devkita64 + `dkp-pacman -Syu`: devkitA64 r30, GCC 16.1, deko3d
  0.5.0, libnx 4.12.0; the published image had GCC 15.2), the sa2-nx toolchain file, Release (-O3), no LTO, no PGO.
  No renderer: `REXGLUE_SWITCH_NO_NVK=ON` with an empty `libvulkan.a` stub, no GPU plugin (the SDK's static loader
  wants xenos' two entry points: `app/src/naruto_no_gpu_plugin.cpp` answers "no plugin"). AI2C linked in as sa2-nx's
  Data_DLL (`ld -r` + `objcopy --localize-hidden --redefine-sym`, `app/src/naruto_static_modules.cpp`). Settings
  compiled in from `app/naruto_switch_defaults.toml` (`game_data_root = "sdmc:/switch/naruto-nx/game"`, logs on).
  Result: `out/nx/naruto.nro` 46 MB (text 45.5 MB, bss 5.3 MB), `_start` at 0, both AI2C entry points present.
  `tools/switch/package.sh` makes `out/nx/sdcard/switch/naruto-nx/{naruto.nro, game/}`.

- **Automated console runs over nxlink (2026-10-24)**: `NX_IP=<console> tools/switch/nxtest.sh NAME SECONDS ['input
  script'] [--cvar=...]` sends `out/nx/naruto.nro` with nxlink (from the Docker image, `--network host`) to hbmenu's
  netloader, written to `sdmc:/switch/naruto-nx/naruto.nro`, with `--log_network=<PC>:28780` (the SDK's TCP log
  sink: every log line plus stdout/stderr), `--test_exit_after_s=SECONDS` (new, `app/src/naruto_test_exit.cpp`:
  closes the window on the UI thread, so ReXApp::OnClosing terminates the title and exits; a hard exit 15 s later if
  the title hangs; checked on the PC: "Window closing ... Title terminated" at 20 s) and the optional input script. A
  Python listener writes `out/runs/NAME/nx.log`; the script ends with an error summary. Needs: hbmenu with title
  override + Y, the game already on the SD, TCP 28780 open on the PC (ufw).

- **First console boot (2026-10-24, boot3)**, no renderer, `nxtest.sh boot3 120`: 2 minutes, then `test_exit_after_s`
  closed it cleanly ("Window closing ... Title terminated"). Horizon layer, threads (19 host stacks, no creation
  failure), `audout 48000 Hz, 2 channels`, files from the SD (slow reads 8-13 ms per 160 KB of Naruto.SRA: the pack of
  SOL-PLAT-7 later), saves under `sdmc:/switch/naruto-nx/naruto/`, and AI2C linked into the NRO: `Module 'ai2c.dll'
  registered 6343 functions`. Same as the PC without a GPU plugin. boot2 had been closed by the user at 11 s (black
  screen looked hung): not a crash.
  - nxlink details: `-p naruto-nx/naruto.nro` (hbmenu's netloader puts /switch/ in front; `switch/...` gave "open:
    err=2"), program arguments after `--` (else nxlink's getopt takes them), the netloader does not reopen after the
    game exits, and a TCP probe of 28280 uses it up: `tools/switch/nx_wait.py` waits for it by UDP ("nxboot" ->
    "bootnx", sent from port 28771 so ufw lets the answer in).

- **Renut on Naruto, first frames (2026-10-24, PC, plume Vulkan)**: Renut vendored from sa2-nx, its device offsets
  retargeted (Naruto's private layout is N&B's, -8 from 0x2E2C on, -16 in places), four hooks on: D3D's hardware
  initialisation 8213ECE8 (Naruto's own creation runs, inlined in the game at 820E6B00; the hook then takes the device
  over: Renut's fence word, Renut's ring sink, Video::SetGuestDevice), KickOff 8212F608, BlockOnFence 8212F708, Swap
  82138A20. Result (`--sa2_renderer=renut`): "Guest D3D device (type 1) ... at 0x40001e00, fence 5, taken over", 60.0
  game fps through Renut's Swap, render thread 0.06-0.08 ms a frame, GPU 0.5-0.8 ms, 0 draws (draw hooks not on yet),
  clean exit. Next: ClearF, Resolve, resource destruction, the draws, then shaders.

- **Renut: draws reach the GPU (2026-10-24, PC)**: shaders dumped from xeshader.sdb (`tools/naruto_dump_shaders.py`:
  3,322 unique, 1,809 ps / 1,513 vs; none in default.xex's image) and translated by Renut's XenosRecomp in 1.6 min;
  shader objects registered after Naruto's own creation (820F5150 vs / 820F5348 ps, object +4 of the wrapper, physical
  part at +0x20 / +0x18); draws hooked (DrawIndexedVertices 82137E00, DrawVertices 82137A18, BeginVertices 821375A0
  with 5/4/20 in r4-r6); vertex declarations registered lazily from the object (Naruto 6274: element count at +0x18,
  D3DVERTEXELEMENT9 array at +0x34, no terminator). Result: 902-44,237 draws per 10 s, none dropped, 30 fps; the frame
  chain is right (tiles resolved into 0x404D3090 with 0x300, the composite into the device's front buffer 0x40000770,
  Swap presents it, Renut has its 1280x720 texture) but the captured frames are black: next, lockstep against the Xenos
  emulation (shaders, constants, textures, the resolve copy).
  - 1 fps after the Hyprland restart: Vulkan's swapchain acquire blocks while the window is off screen (gdb: render
    thread in plume::VulkanSwapChain::acquireTexture). Test runs use `--renut_vsync=false`; the game then runs at its
    own 30 fps through Renut's pacing (PresentationInterval at +13580). Frames come from the renderer
    (`tools/pc/frames.sh`), not from the screen.

- **Renut draws the title screen (2026-10-24, PC)**: bisected with `naruto_debug_clear_color` (red clears) and
  `naruto_debug_present` (present any texture): the present path worked, the draws left nothing; Vulkan validation
  clean for them; the composite's VS gets the right constants (identity) from the device. Turning Renut's
  optimisations off one by one: `sa2_renut_chain_reuse` (and so `sa2_renut_snapshot_deltas`) broke it; its verifier
  (`sa2_renut_chain_reuse_verify`) said "the reused targets differ": render/draw.cpp tested SA2's private byte ranges
  for "targets unchanged" (12816-12835) and "textures unchanged" (12920-13023). Now from the layout constants
  (Naruto 12432-12451, 12536-12639): the title screen renders correctly with every optimisation on. Gamma ramp
  retargeted to Naruto's +14988.
  - Test runs: the window goes to Hyprland workspace 2 (user's request; `tools/pc/launch.sh`, a runtime
    `hl.window_rule` through `hyprctl eval`: Hyprland 0.56 takes Lua, `hyprctl dispatch exec "[rules]"` no longer
    parses), core dumps off, frames from the renderer. Two Hyprland crashes during the runs were the desktop's
    (the user's diagnosis: /dev/shm exhausted by other software, an NVIDIA EGL readback crash), and so was the
    game's SIGBUS (guest memory pages failing while RAM was short): check `free` and `df /dev/shm` before runs.

## Open questions and hypotheses

| Question | Hypotheses | Cheapest experiment that separates them | Result |
|---|---|---|---|
| How do `ai2c.dll` (and DLC `ai2c@N.dll`) become part of one NRO? | (a) the sa2-nx SDK fork already handles `[[modules]]` statically; (b) needs a static module table in place of host DLLs | grep the sa2-nx SDK fork for module registration / `XexLoadImage` on Horizon | **(a)**, see Known "Guest DLLs" |
| Is our `default.xex` the revision the PC base's seeds and hook addresses were made for? | (a) yes (one retail disc revision); (b) another revision/region | first codegen with their `analysis-seeds.toml`: clean analysis and hooked addresses at function starts | **(a)**: all 116 `sub_*` addresses in their `app/src` are function starts in ours |
| Is `LinkApp.xex` ever run? | (a) system-link/online launcher, never in single player; (b) needed for a mode we want | grep the PC base and its logs for `LinkApp`/`XLaunchNewImage`; strings in `default.xex` | PC base: no reference |
| Does Renut's device-reading work with the 6274 device layout? | (a) same shadow registers and bound-object fields, only moved; (b) 6274 keeps state elsewhere (older private part) | diff the offsets the PC base reads (`d3d/device.*`, `state.*`) against Renut's `d3d_native.h` list | |
| Does the game raise exceptions in play (RtlUnwind is a stub)? | (a) never in normal play (the PC base plays through); (b) some path (shader compiler, file errors) | grep PC-boot logs for `[STUB] RtlUnwind` | |
| Do saves round-trip (write real progress, load it)? | (a) yes, slots are only pre-allocated so far; (b) a content/signature problem | play past the first story autosave (Save.dat with data), then Load Game | **neither**: a case-sensitive content lookup on Linux; fixed, loads |
| DLC support on the Switch: v1 or later? | 3 extra recompiled engines ≈ 3x the AI2C code in the NRO | size of generated `ai2c*` after codegen | |
| Can the 1020 MHz A57 hold 30 FPS in the open world? | game thread or render thread limits | stage 7 measurements | |

## Decisions

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-10-24 | **Renderer: Renut on plume/deko3d (sa2-nx), retargeted to XDK 6274 using the PC base's renderer as the map** (its addresses, device offsets with their source, and game-specific fixes: gamma, scissor, occlusion queries, resolve), not its engine. | (1) The PC base's renderer with a new deko3d back end. (2) A hybrid: the PC base's `d3d/` front end on a plume-deko3d implementation of its `Backend`. | Renut's deko3d back end, render-thread optimisations (SOL-REND-4: 17.6 -> 11.1 ms on sa2), shader chain and browser installer are console-proven in ~10 ports; the PC base's renderer has never run on a Switch, its back ends bypass plume (a third back end from scratch), it is Windows-bound (42 files), carries PC-only work on the hot path (interpolation, MSAA, diagnostics) and embeds game shaders. Its real value — the census and device layout of a 6274 Direct3D — is what SOL-REND-1 costs, and we get it by reading it. Option (2) is the fallback if the 6274 device turns out not to fit Renut's draw-time state reading (open question 3). |
| 2026-10-24 | SDK: the sa2-nx fork (SOL-ROUTE-1) + the PC base's DLC codegen patch ported by hand + its relative-paths patch. | Upstream 0.10.0 with the PC base's patches and a Horizon layer of our own. | The fork already has the Horizon layer and static guest modules; the PC base's other patches are PC/Xenos only. |
| 2026-10-24 | v1 links the base engine `ai2c.dll` only; the three DLC engines behind a CMake option (`NARUTO_DLC_ENGINES`), on by default once NRO size and memory are measured. | All four from the start. | Each engine is a full code module (3.8 MB XEX): 3 more of them grow the NRO and the link time before the base game boots. |
| 2026-10-24 | Frame rate on the Switch: the game's own (30 open world / 60 fights); no interpolation. | The PC base's interpolated 60 FPS. | SOL-REND-3: never decouple; interpolation is extra CPU on 1020 MHz. |

## Deviations from the default road

- **Older Direct3D than any Renut port (2.0.6274, LTCG)**: SOL-REND-1 expects matching against N&B (7645) with
  `d3d_match.py`; for this game the census comes from the PC base's hooks instead, then confirmed by call layout.
  If it works, add to solutions.md: "a PC recompilation with its own D3D-level renderer is the census".
- **Guest DLL modules (engine + 3 DLC revisions)**: not covered by the sa2-nx road; to be solved in stage 2.

## Measurements (console)

| Date | Build | Clocks | Scene | FPS / frame time spread | Game thread | Render thread | GPU |
|---|---|---|---|---|---|---|---|
