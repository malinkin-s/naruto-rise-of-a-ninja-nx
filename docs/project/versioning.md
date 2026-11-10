# Versioning and Artifacts

`release version` names a published package; `commit SHA` identifies source; `Build ID` identifies one build configuration and toolchain; `artifact hash` identifies exact bytes; `scenario/config ID` fixes the test recipe, including FTP deployment and forwarder configuration; `Run ID` identifies one execution. One binary may have many Run IDs. Source: `docs/archive/HANDOFF.md` §Releasing (release/installer hash coupling), `docs/performance/console-run-workflow.md` (accepted run path).

Proposed names: `build-YYYYMMDD-<shortsha>-<config>-NN`; `scenario-name-vN`; `cfg-<mode>-<resolution>-<clock-policy>-vN`; a **short unique** Run ID such as `pilot-village-view-001`. The on-console marker requires a Run ID of at most 64 ASCII letters, digits, hyphens or underscores; keep the full build/scenario/config identity in run metadata rather than the Run ID string. Do not encode a measured FPS in an ID. Increment config ID for any changed TOML, clock/core policy, compiler/toolchain, PGO profile, shader package or build flag. Record SHA-256 of the NRO and shader files separately.

Example metadata (illustrative; no run is claimed):

```yaml
run_id: pilot-village-view-001
release_version: null
commit: 18ddecd356c9dff04f2af0dfa80d37b63d81cf40
build_id: TBD
nro_sha256: TBD
shader_package_sha256: TBD
scenario_id: village-01-v1
config_id: cfg-handheld-720p-stock-v1
result: unmeasured
```

Keep source documentation, compact console-log summaries, aggregate tables, reproducible scenario definitions and non-sensitive input recipes in Git. Do not retain full console logs: stream or stage them temporarily in `/tmp`, extract the summary, then remove them (`AGENTS.md` §Log Handling). Keep game data, generated code, saves, shader packages, NROs, per-frame metric streams and captures outside Git. Store each run's immutable binary, ELF, configuration, metrics and media under a unique directory outside the repository, then link a durable location or digest from its report. The storage service is an owner decision; no external upload is implied.

Increase SemVer only for a user-facing published release. Builds and runs do not change the release version. Confirm the published NRO hash against the installer manifest before release (`docs/archive/HANDOFF.md` §Releasing).
