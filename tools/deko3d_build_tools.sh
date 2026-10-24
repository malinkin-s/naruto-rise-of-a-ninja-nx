#!/usr/bin/env bash
# banjo-nx (deko3d renderer, docs/deko3d-renderer.md): the PC tools the deko3d shader chain needs, built into
# out/deko3d_tools: SPIRV-Cross (from UnleashedRecomp-NX's MoltenVK copy, Apache-2.0; a PC tool only) and uam
# (app/thirdparty/uam, SwitchWakerHD's patched 1.1.0) with devkitPro's MSYS2 clang (MinGW).
#   bash tools/deko3d_build_tools.sh [SPIRV-Cross source]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# naruto-nx: Linux; SPIRV-Cross from the SDK's MoltenVK copy (the same source sa2-nx/banjo-nx used), system clang.
SPIRV_CROSS_SRC="${1:-$ROOT/out/deko3d_tools/SPIRV-Cross}"  # KhronosGroup/SPIRV-Cross at adec7ac (the SDK MoltenVK copy revision; its symlink there has no source)
OUT="$ROOT/out/deko3d_tools"

mkdir -p "$OUT/spirv-cross-build" "$OUT/uam-build"
cmake -S "$SPIRV_CROSS_SRC" -B "$OUT/spirv-cross-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DSPIRV_CROSS_ENABLE_TESTS=OFF -DSPIRV_CROSS_SHARED=OFF \
    -DSPIRV_CROSS_ENABLE_C_API=OFF
ninja -C "$OUT/spirv-cross-build" spirv-cross
cmake -S "$ROOT/app/thirdparty/uam" -B "$OUT/uam-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
ninja -C "$OUT/uam-build" uam_tool
"$OUT/uam-build/uam" --version || true
ls -la "$OUT/spirv-cross-build/spirv-cross" "$OUT/uam-build/uam"
