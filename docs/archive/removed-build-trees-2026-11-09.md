# Removed Local Build Trees — 2026-11-09

These local, untracked build trees were deleted during the repository cache cleanup that the owner approved on 2026-11-09. Only their identities are kept here, so that historical run reports that cite them can still be matched by hash.

| Former path | File | SHA-256 |
|---|---|---|
| `out/measurement-build-v014/` | `naruto.nro` | `353fbb6eff04506566cdf889f4b10de39a54e0f1fbe86933d993b477aef729ce` |
| `out/measurement-build-v014/` | `naruto.stripped.elf` | `9c5489ae2ed8f1376860de55ff74bffbf23554ec410bddb2a347159ebd759a3e` |
| `out/measurement-build-v014/` | `naruto.measure.toml` | `c1e02936931cad7a7b3f7397ac8ea56c83712e8d64111d5d13cf650e35812276` |
| `out/measurement-build-v014/` | `naruto.control.toml` | `c1e70b783e4badf48210c542863697021bfc804fe021b03b86a49adf93dc18af` |
| `out/measurement-preserve-v014/` | `naruto.nro` (original 0.1.4 NRO preserved before the diagnostic deployment) | `29ef5654af47671ff3b85537b3d2027c5dcbef430a0dd99debceb707ce4024e1` |
| `out/measurement-preserve-v014/` | `naruto.stripped.elf` | `b5b916902f572fcb4bd6b573ce7434ee7d7c66bac2e9fcf747c0c04f4f934818` |
| `out/nx/` (non-PGO, non-LTO, `SA2_RENUT_RELEASE_SHADERS=OFF` dev tree) | `naruto.nro` | `66bceb6a3a5175b57a29665228e6fa5a522df3c801fab9a483cbc932bc7dde6b` |
| `out/nx/` | `naruto.stripped.elf` | `19214d7f6c9efb45b5a04f22c869b316f8308f3802ba000b8c7538077b8b88aa` |

Retained: `out/nx-pgo-lto/naruto.nro` (`e9f15f71868eb9d939c81fcf6300df3f4bce59bb62205b887c7907e1c21f76bd`, the console-installed candidate for `run-gpu-opt-009`). `tools/switch/build.sh` recreates `out/nx/` on its next default build.
