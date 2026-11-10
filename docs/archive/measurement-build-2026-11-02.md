# Prepared Measurement Build — 2026-11-02

**Status:** built, locally verified and installed through FTP with owner authorization; not yet launched or measured on Switch. This is a diagnostic artifact, not release 0.1.5 or a new baseline. Base HEAD: `18ddecd356c9dff04f2af0dfa80d37b63d81cf40` (`v0.1.4`) with uncommitted telemetry changes. The tracked C++ source diff SHA-256 at build time was `7d8a75620f3886553b6d1dbd57ab4a3f1f4bc3179b574ab1235a39757e1c7175`. No game code generation or clean rebuild was performed.

| Item | Value / evidence |
|---|---|
| Build ID | `build-20261105-18ddecd-measure-pgo-lto-01` |
| Build tree and command | Existing `out/nx-pgo-lto`, `ninja -C out/nx-pgo-lto -j2 naruto` inside `naruto-nx/devkita64`; 57 Ninja steps, link exited 0 |
| Toolchain image ID | `sha256:4b4785f5f78469e07361f99732b45ad74a0265a9bfafa5741034a097dd7403f1` (`docker image inspect`) |
| Flags | `NARUTO_PGO=use`, `NARUTO_SWITCH_LTO=ON`, `NARUTO_SWITCH_LTO_JOBS=2`, `SA2_RENUT_RELEASE_SHADERS=ON` (`out/nx-pgo-lto/CMakeCache.txt`) |
| Diagnostic NRO | `out/measurement-build-v014/naruto.nro`, SHA-256 `353fbb6eff04506566cdf889f4b10de39a54e0f1fbe86933d993b477aef729ce` |
| Matching unstripped ELF | `out/measurement-build-v014/naruto`, SHA-256 `f99bd4fa3b3985074fcdb26f2f621725cf1e084699a8dbb5fd687f77fa8d406d` |
| Prepared one-run TOML | `out/measurement-build-v014/naruto.measure.toml`, SHA-256 `c1e02936931cad7a7b3f7397ac8ea56c83712e8d64111d5d13cf650e35812276`, Run ID `pilot-village-view-001` |
| Prepared FTP start flag | `out/measurement-build-v014/measure_start_pilot-village-view-001.flag`, SHA-256 `3d36709885057e5222fa092f79e89036ff0d1123354b0cf22dc6176d62dd021d`; contains only the Run ID and newline |
| Installed TOML source | FTP `/switch/naruto-nx/naruto.toml`, SHA-256 `c1e70b783e4badf48210c542863697021bfc804fe021b03b86a49adf93dc18af`; candidate adds explicit `log_to_file=true`, `switch_profile_report=true`, Run ID and 30-second duration; parsed with `tomllib` |
| Control / restore TOML | Exact FTP copy at `out/measurement-build-v014/naruto.control.toml`, same SHA-256 `c1e70b783e4badf48210c542863697021bfc804fe021b03b86a49adf93dc18af`; use with the same diagnostic NRO for overhead comparison and restoration |
| Preserved 0.1.4 local NRO | `out/nx-pgo-lto/naruto.nro` restored to SHA-256 `29ef5654af47671ff3b85537b3d2027c5dcbef430a0dd99debceb707ce4024e1`, matching the installed NRO at the earlier FTP snapshot (`console-install-snapshot.md`) |

The local PGO/LTO object tree now contains the diagnostic object files while its public NRO/ELF files were restored from `out/measurement-preserve-v014/`. Use the hash-bound files under `out/measurement-build-v014/` for diagnostic identity; do not infer an object tree's identity from the restored NRO. `strings` on the diagnostic NRO finds the Run ID, Renut tick-window, start-flag and segment-summary format strings. The build used existing generated game code and PGO data, so it does not establish a reproducible clean build. The 0.1.4 NRO remains the comparison artifact. The diagnostic NRO/TOML are now installed; their prior versions are preserved as console `.v014.bak` files (`console-install-snapshot.md` §Diagnostic deployment).

**Next validation:** the owner launches through the existing four-core/39-bit Sphaira forwarder and freezes the rooftop/tree view. Only then send the unique FTP start flag. Parse both logs with `tools/switch/ftp_run_summary.py pilot-village-view-001` and compare against an otherwise identical run of the **same NRO** with an empty Run ID to estimate overhead (`docs/performance/console-run-workflow.md`).
