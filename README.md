<p align="center">
  <img src="docs/media/banner.svg" alt="Naruto: Rise of a Ninja — Nintendo Switch port" width="100%">
</p>

<p align="center">
  <b>English</b> · <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <img alt="stage" src="https://img.shields.io/badge/stage-6%20%C2%B7%20on%20console-5CA382?style=flat-square&labelColor=1C2024">
  <img alt="platform" src="https://img.shields.io/badge/platform-Nintendo%20Switch%20(homebrew)-7FA0B4?style=flat-square&labelColor=1C2024">
  <img alt="renderer" src="https://img.shields.io/badge/renderer-Renut%20%C2%B7%20deko3d-7FA0B4?style=flat-square&labelColor=1C2024">
  <img alt="licence" src="https://img.shields.io/badge/licence-GPL--3.0-C2AC63?style=flat-square&labelColor=1C2024">
</p>

A Nintendo Switch (homebrew NRO) port of **Naruto: Rise of a Ninja** (Ubisoft Montreal, 2007, Xbox 360 exclusive).
The game's PowerPC code is statically recompiled with [ReXGlue](https://github.com/rexglue/rexglue-sdk); the Xbox 360 GPU is not
emulated: Direct3D calls are drawn by Renut, a Direct3D-level renderer, on deko3d, the Switch's native graphics API.

> [!IMPORTANT]
> Work in progress. The game boots and is playable on the console up to a fight, but it is slow and not ready for
> playing. There are no releases yet. The repository has no game data and no code made from it: you need your own
> copy of the game.

## Status

**Stage 6 (Switch) of the port, as of 2026-10-24.** The NRO runs on a real console: logos, menus, loading a save and
a full fight, with the right picture. Next: frame rate.

| Area | Switch | Notes |
|---|---|---|
| Boot, Scaleform logos, menus | **Works** | 24–29 FPS in menus |
| Saves on the SD card | **Works** | Created, listed and loaded (`sdmc:/switch/naruto-nx/`) |
| Fights | **Works, slow** | Picture right, no artifacts seen; 15–25 FPS (the game runs fights at 60) |
| Open world (first story scene) | **Renders, slow** | ~7 FPS; artifacts seen once, being investigated |
| Bink video (cutscenes) | Partly checked | The intro plays; the story cutscenes still to check |
| Controller | Scripted input checked | Automated runs press buttons; a long session by hand still to do |
| Audio | Not checked | |
| Character DLC (3 extra engines) | Not yet | Behind a CMake option, after memory is measured |
| Performance work | Not started | No LTO/PGO, no precompiled shader cache, debug logging still on |

On the PC (Linux, the same code with Renut on Vulkan): intro, menus, Konoha with villagers, dialogue, the tutorial,
a fight, and saves that are written and loaded back, at 30 FPS.

### What was solved to get here

- **Older Direct3D than any earlier Renut port** (XDK 2.0.6274, LTCG): the private device layout, functions and
  offsets were mapped using the PC recompilation's renderer as a reference ([docs/d3d-census.md](docs/d3d-census.md),
  [docs/renut-retarget.md](docs/renut-retarget.md)).
- **3,322 game shaders** from `xeshader.sdb` translated (XenosRecomp → DXC → SPIRV-Cross → uam for deko3d).
- **Tiled rendering**: the game draws its 3D scene in three 1280×256 tiles with 4× MSAA (the Xbox 360's EDRAM);
  Renut's targets now cover all tiles.
- **The game engine `ai2c.dll`** is linked into the NRO as a static module.
- **Automated console tests over nxlink** (`tools/switch/nxtest.sh`): the game runs for a set time, sends its log and
  renderer frames to the PC, and exits by itself.

The full story, with evidence for every step, is in [docs/port-journal.md](docs/port-journal.md).

## Screenshots

Taken from the renderer on a Nintendo Switch (half size, 640×360), automated run of 2026-10-24.

<table>
  <tr>
    <td><img src="docs/media/switch_menu.jpg" alt="Single player menu"></td>
    <td><img src="docs/media/switch_jutsu_select.jpg" alt="Jutsu list"></td>
  </tr>
  <tr>
    <td align="center"><sub>Single player menu</sub></td>
    <td align="center"><sub>Jutsu list before a fight</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_versus.jpg" alt="Naruto vs Sasuke"></td>
    <td><img src="docs/media/switch_fight.jpg" alt="Fight arena"></td>
  </tr>
  <tr>
    <td align="center"><sub>Match intro</sub></td>
    <td align="center"><sub>The forest arena</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_fight_close.jpg" alt="Fight, close"></td>
    <td><img src="docs/media/switch_fight_jutsu.jpg" alt="Jutsu in a fight"></td>
  </tr>
  <tr>
    <td align="center"><sub>Naruto and Sasuke</sub></td>
    <td align="center"><sub>A jutsu prompt</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_rasengan.jpg" alt="Jutsu cut-in"></td>
    <td><img src="docs/media/switch_scaleform.jpg" alt="Scaleform logo"></td>
  </tr>
  <tr>
    <td align="center"><sub>Jutsu cut-in</sub></td>
    <td align="center"><sub>Boot logos</sub></td>
  </tr>
</table>

## How it is built

| Part | From |
|---|---|
| Recompiled code | ReXGlue SDK, the [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx) fork (Horizon layer, static guest modules) |
| PC base and reference | [jorjbarbosa/naruto-rise-recomp](https://github.com/jorjbarbosa/naruto-rise-recomp): seeds, hooks, the Direct3D map |
| Renderer | Renut (masterspike52) on plume's deko3d back end, from sa2-nx, retargeted to Naruto's Direct3D |
| Toolchain | devkitA64 (GCC 16.1) in Docker, libnx, deko3d |

### Building (outline)

You need your own game files in `game/` (the extracted disc, `default.xex` at the top).

```bash
python3 tools/fetch_thirdparty.py           # SDK third-party sources
tools/fetch_renut_deps.sh                   # plume, XenosRecomp, uam, imgui (from sa2-nx)
# host rexglue (sdk/, cmake --preset linux-amd64), then:
rexglue codegen app/naruto_manifest.toml    # recompiled code into app/generated/ (never committed)
tools/deko3d_build_tools.sh                 # SPIRV-Cross and uam for the shader chain
tools/switch/host_shaders.sh                # Renut's own shaders for deko3d
tools/switch/build.sh                       # out/nx/naruto.nro
tools/switch/package.sh                     # out/nx/sdcard/ -> copy to the SD card
```

On the console, start hbmenu with title override (hold R while starting a game, for the full memory) and pick
Naruto: Rise of a Ninja.

## Credits

- [jorjbarbosa/naruto-rise-recomp](https://github.com/jorjbarbosa/naruto-rise-recomp): the PC recompilation this
  port stands on.
- [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx): the Switch template, the SDK fork and Renut on deko3d.
- Renut by masterspike52; plume; XenosRecomp; uam; deko3d and libnx by the devkitPro and switchbrew teams.
- The [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk).

## Licence and disclaimer

GPL-3.0, see [LICENSE](LICENSE). This is a fan project, not affiliated with or endorsed by Ubisoft, Bandai Namco,
Shueisha, Microsoft or Nintendo. *Naruto* and the game's assets belong to their owners. No game files are
distributed here: build it from a copy of the game you own.
