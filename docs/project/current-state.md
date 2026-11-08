# Current State — v0.1.4 Source Audit

Audit date: 2026-11-02. Read-only audit; no clean build or console run was performed. Command evidence: `git status --short --branch`, `git rev-parse HEAD`, `git tag --points-at HEAD`, `git submodule status`, `git ls-files .gitmodules`, and inspection of the cited files.

| Check | Result | Source | Gap |
|---|---|---|---|
| Branch and base | `main`, `18ddecd356c9dff04f2af0dfa80d37b63d81cf40`, tag `v0.1.4` | Git commands above | New documentation is uncommitted |
| Submodules | None listed; `sdk/` is a tracked tree | `git submodule status`, `git ls-tree HEAD sdk` | Third-party revisions inside SDK need inventory |
| Release behavior | Boot, menus, story, fights and saves are reported working | `README_ru.md` §State | No new run or full-game coverage |
| Known limits | Possible exit crash, black save thumbnail, no DLC engines; three-core audio can stutter | `README_ru.md` §State; `docs/archive/release-0.1.3.md` §Known issues | Reproduction on the release artifact unknown |
| Local tools | `docker`, `cmake`, `ninja`, `magick`, `llvm-nm`, host `rexglue` executable found | `command -v`; `test -x sdk/out/linux-amd64/Release/rexglue` | Docker image content and compiler version not independently verified |
| Local NRO trees | `out/nx` is non-PGO/non-LTO; `out/nx-pgo-lto` cache has PGO=use, LTO=ON and release shaders=ON. The installed console NRO hash matches local `out/nx-pgo-lto/naruto.nro` | `out/*/CMakeCache.txt`; `docs/project/console-install-snapshot.md` | Published release hash and source/build provenance remain unverified |
| Game input | Manifest needs own `default.xex`, `AI2C.dll`; shaders need `xeshader.sdb` | `app/naruto_manifest.toml`; `README_ru.md` §Build | Local files were not opened or validated |

## Build and launch path (documented, not executed in this audit)

1. Prepare own extracted disc in `game/`; fetch source dependencies with `python3 tools/fetch_thirdparty.py` and `tools/fetch_renut_deps.sh` (`README_ru.md` §Build). These require network and local game data at later stages.
2. Build host ReXGlue using `sdk/CMakePresets.json`; run `tools/codegen.sh` from the repository root. Codegen writes `app/generated/` and `out/codegen.log` (`tools/codegen.sh`).
3. Build a development NRO with `tools/switch/build.sh`. For the documented PGO/LTO release-style tree: `NX_BUILD_DIR=$PWD/out/nx-pgo-lto tools/switch/build.sh -reconfigure -DNARUTO_PGO=use -DNARUTO_SWITCH_LTO=ON -DSA2_RENUT_RELEASE_SHADERS=ON` (`docs/archive/HANDOFF.md` §Releasing; `pgo/README.md`). Preserve exact toolchain and PGO profile identity.
4. For acceptance runs, the owner transfers the selected NRO/required files over FTP, creates or updates a Sphaira HOME Menu forwarder with 4 CPU cores and 39-bit address space, and launches through it. Fetch logs over FTP and summarize per Run ID (`docs/performance/console-run-workflow.md`; owner confirmation 2026-11-02). The exact FTP upload command/service is not documented. `tools/switch/nxtest.sh` is a separate legacy netloader path and does not reproduce the accepted launch conditions.

**Unknown/build blockers:** published release NRO SHA-256, Docker image digest, installed devkitA64 version, host ReXGlue build provenance, PGO compatibility with current generated code, published shader-package hash, console firmware and exact FTP upload procedure. Installed NRO/config/shader hashes and FTP endpoint are now recorded in `docs/project/console-install-snapshot.md`; a match with a local NRO does not prove release provenance. Verify before claiming reproducibility. Do not use `tools/switch/package.sh` during an audit: it replaces the package's `game/` directory (`tools/switch/package.sh`). The later `tools/switch/ftp_run_summary.py` implementation reads full logs only into memory and retains a compact report; it has not yet been exercised against a new measurement build (`docs/performance/console-run-workflow.md`).
