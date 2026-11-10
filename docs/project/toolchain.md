# Toolchain and Dependency Inventory

Audit date: 2026-11-09. Read-only checks. No package, image or pin was changed. Updates are separate tasks after a baseline (`ROADMAP.md` issues `pgo-refresh`, `deps-update`).

## Switch build container

| Item | Value | Evidence |
|---|---|---|
| Image | `naruto-nx/devkita64:latest`, ID `sha256:4b4785f5f78469e07361f99732b45ad74a0265a9bfafa5741034a097dd7403f1`, created 2026-10-24 | `docker inspect` |
| Base | `devkitpro/devkita64@sha256:1fc388c3a0d34bd2045a6dadcb1020e069d5f876a187fd705de14b4440c00282` (2026-02-19), then `dkp-pacman -Syu` | `tools/switch/build.sh` header, `docker inspect` |
| Compiler | devkitA64 r30-1, `aarch64-none-elf-gcc` 16.1.0 | `dkp-pacman -Q` inside the image |
| Packages | libnx 4.12.0-1, deko3d 0.5.0-1, uam 1.1.0-1, switch-tools 1.13.1-1, general-tools 1.4.4-1, switch-cmake 1.5.2-1, devkita64-cmake 1.1.3-1, switch-mesa 20.1.0-5, switch-zlib 1.3.1-1, switch-glm 0.9.9.7-2, devkitA64-gdb 14.1-1; container CMake 3.31.6 | `dkp-pacman -Q` |
| Freshness | `dkp-pacman -Sy && dkp-pacman -Qu` in a throwaway container listed no upgrades; libnx `v4.12.0` and deko3d `v0.5.0` are the newest upstream tags | 2026-11-09 check, `git ls-remote --tags` |

The image is a local build, not a registry digest. Rebuilding it with `-Syu` can silently change GCC or libnx. Record the image ID in every run report's build identity.

## Source dependencies

| Dependency | Project pin | Newest upstream (2026-11-09) | Gap / risk |
|---|---|---|---|
| ReXGlue SDK (`sdk/`, tracked tree with local changes) | v0.10.0, commit `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518` (`tools/fetch_thirdparty.py`). This is the "Release v0.10.0" merge commit on `main`: 2 commits ahead of tag `v0.10.0` (`f5337cd`) with zero file differences (GitHub compare API) | `v0.10.1` (tag `bd833a2`) | Patch release behind. `sdk/` carries local changes (`patches/sdk-naruto-on-sa2-fork.patch`, plus `7509546`), so any rebase needs codegen, a rebuild and a console run. Medium risk |
| sa2-nx renderer trees (plume, reblue-XenosRecomp, uam → `app/thirdparty/`) | `adf3a4e` (`tools/fetch_renut_deps.sh`) | `v1.0.6` `baf523b` | Several 1.0.4–1.0.6 features were ported by hand (clear repeat, 2 MB pages; `docs/archive/handoff-2026-11-09.md`). Needs a diff audit before bumping to avoid double application. Medium risk |
| dxc-bin | `737ac9f51c3d06f0cd1ee7e14dc065bafd52310d` | not checked | On Linux the system DXC is used instead: `directx-shader-compiler 1.10.2605.37-1` |
| PGO profile (`pgo/`, 211 `.gcda`) | 2026-10-29 session | n/a | **Stale:** `25159ed` and `7509546` changed app and SDK sources, so changed functions build without counts. Regenerate after the code stabilizes (changes binary identity) |

## Host tools (codegen, PC build, scripts)

| Tool | Version |
|---|---|
| Host `rexglue` | `sdk/out/linux-amd64/Release/rexglue`, reports `0.10.0.0-dev.unknown`, built 2026-10-24 (no commit provenance) |
| CMake / Ninja | 4.4.4 / 1.13.2 |
| Python | 3.15.2 (project scripts use only the standard library) |
| Clang / GCC | 23.1.3 / 16.2.1 |
| DXC | 1.10.2605.37 (`/usr/bin/dxc`) |

## Unknowns

- Published 0.1.5 NRO hash and which image ID built it.
- Whether `rexglue` in `sdk/out` was built from the current `sdk/` tree. Its version string lacks a commit.
