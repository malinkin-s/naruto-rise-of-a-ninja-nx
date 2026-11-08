# Console Install Snapshot — 2026-11-02

Historical read-only FTP inspection of `192.168.0.165:5000`, root `/switch/naruto-nx`, before the diagnostic deployment below. This is an **installed-file snapshot**, not a valid benchmark run. No game assets or saves were opened during this original snapshot; no remote file was saved locally. Evidence: FTP `MLST` metadata and streaming SHA-256, compared with local `sha256sum` equivalent in memory. FTP directory `LIST`/`NLST`/`MLSD` returned no entries despite direct `CWD`, `SIZE`, `MLST` and `RETR` working. FTP modification times were reported as `1970-01-01` and cannot identify run age.

| Installed file | Size (FTP) | SHA-256 | Interpretation |
|---|---:|---|---|
| `naruto.nro` | 39,691,862 B | `29ef5654af47671ff3b85537b3d2027c5dcbef430a0dd99debceb707ce4024e1` | Matches local `out/nx-pgo-lto/naruto.nro`; differs from local `out/nx/naruto.nro` |
| `naruto.toml` | 5,181 B | `c1e70b783e4badf48210c542863697021bfc804fe021b03b86a49adf93dc18af` | Installed configuration identity only; settings not inspected |
| `deko3d_glsl.bin` | 26,868,200 B | `f99566a9f722f3336c6045f12beeeb36ce60200b332e43daceb47dd35f396ecf` | Installed shader-package identity |
| `deko3d_shaders.bin` | 7,665,464 B | `bb1ad155f6b504a7e21b31e9637e9751bf5cffea94d1123a1eb3be0e74a0887a` | Installed shader-cache identity |

`logs/rex/rex_profile.log` exists (34,463 B). A read-only in-memory parse found seven profile windows. Its **last** window reports CPU 1020.0 MHz, GPU 460.8 MHz, RAM 1600.0 MHz, process cores 4 (mask `0xF`), game 28.9 FPS and zero audio requests without data. The run's scene, start time, Build ID and measured interval are unknown; these values are **not** a baseline result. No full log was retained.

The profile was later updated to 45,070 B; its newer compact summary is `docs/performance/observations/profile-2026-11-02.md`. The two readings must not be treated as one identified run.

**Next verification:** identify whether this NRO is the published 0.1.4 artifact, record a fresh Run ID and scenario, and capture a profile whose time window is tied to the owner's hotspot save and camera. The hash match proves only equality with the local NRO file, not its source commit or release provenance.

## Diagnostic deployment — 2026-11-02

After the owner authorized FTP deployment, the diagnostic NRO and one-run TOML from `measurement-build-2026-11-02.md` were uploaded under temporary names, read back and hash-verified, then promoted to the normal paths. The previous files were renamed to backup paths before promotion. Final files and both backups were read back through FTP and SHA-256 checked; no game files or saves were modified. The `pilot-village-view-001` start flag had **not** been uploaded at this snapshot. The owner still needs to launch through the Sphaira forwarder and position the game before the flag is sent.

| Console path under `/switch/naruto-nx/` | SHA-256 | Role |
|---|---|---|
| `naruto.nro` | `6e8d07ca0bc33087617d859219cfc4b4b4c137a635c6c08550ce13fd2e98e50a` | Installed diagnostic build |
| `naruto.toml` | `c1e02936931cad7a7b3f7397ac8ea56c83712e8d64111d5d13cf650e35812276` | Installed one-run configuration, Run ID `pilot-village-view-001` |
| `naruto.nro.v014.bak` | `29ef5654af47671ff3b85537b3d2027c5dcbef430a0dd99debceb707ce4024e1` | Preserved previous NRO |
| `naruto.toml.v014.bak` | `c1e70b783e4badf48210c542863697021bfc804fe021b03b86a49adf93dc18af` | Preserved previous TOML |
