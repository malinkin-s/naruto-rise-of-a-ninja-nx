# Run Report — TEMPLATE

Status: `valid / invalid / pending`; evidence class: `fact / hypothesis / unknown`. Never fill a missing value by inference. See `measurement-protocol.md` and `docs/project/versioning.md`.

```yaml
run_id: TBD
timestamp_utc: TBD
scenario_id: TBD
scenario_version: TBD
config_id: TBD
purpose: baseline | A | B | regression
hypothesis_or_issue: TBD
commit: TBD
build_id: TBD
nro_sha256: TBD
elf_sha256: TBD
shader_package_sha256: TBD
toml_sha256: TBD
toolchain_digest: TBD
console_model: TBD
firmware: TBD
launch_method: sphaira_forwarder
forwarder_cpu_cores: 4
forwarder_address_space: 39-bit
ftp_deployment_record: TBD
ftp_log_source_timestamps: TBD
mode: handheld | docked
cpu_mhz: TBD
gpu_mhz: TBD
ram_mhz: TBD
core_mask: TBD
render_resolution: TBD
save_sha256: TBD
replay_sha256: TBD
warmup_class: cold | warm
warmup_end_event: TBD
measurement_start_event: TBD
measurement_end_event: TBD
background_services: TBD
temperature_or_proxy: unknown
status: pending
invalid_reason: null
```

## Checkpoints and observed result

| Checkpoint/event | Expected | Observed | Evidence path/hash |
|---|---|---|---|
| TBD | TBD | TBD | TBD |

Measured segment guest-frame ordinals (first/last): TBD / TBD. Matching CPU/Renut windows must be fully inside the segment; list excluded partial windows and why.

| Metric | Value | Unit / aggregation | Source artifact |
|---|---:|---|---|
| Guest Swaps; host presents; mean FPS | TBD | counts and elapsed seconds, name event clock | TBD |
| Present intervals; 1% low / p50 / p95 / p99 / max | not measured | per-frame stream, definition and sample count required | TBD |
| Swap-to-Swap work/paced sleep/late/hitches; game-clock drift | TBD | segment total or mean; independent checkpoint for drift | TBD |
| Main/game draw/render CPU and waits | TBD | per-thread CPU% and wait ms; aligned window | TBD |
| Render busy; GPU time; draw count | TBD | mean ms/frame and draws/frame; aligned window | TBD |
| Pipeline builds; memory/IO; audio misses | TBD | counts, bytes, peak/latency with collection interval | TBD |

Artifacts: compact console log summary (`console-log-summary-template.md`), optional numeric metric-stream location and SHA-256 (outside Git), NRO/ELF hashes. Media is optional for scene identification or visual defects, never a routine performance requirement. Do not retain a full console log in the project. Conclusion: observed change, uncertainty/spread, regressions, and next falsifying test. Reviewer/owner decision: TBD.
