#!/bin/bash
# Renut's host shaders for the Switch build, made on the host (the devkitA64 container has no DXC, SPIRV-Cross or uam):
# <build>/renut_gpu/host_shaders/<stem>.{spirv,deko3d}.h, which the build takes with RENUT_PREBUILT_HOST_SHADERS=ON
# (app/src/renut_engine/gpu/gpu.cmake). The same commands as gpu.cmake's renut_host_shader. Tools: the system's DXC
# (Arch directx-shader-compiler) and out/deko3d_tools (tools/deko3d_build_tools.sh).
#   tools/switch/host_shaders.sh [build dir, default out/nx]
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out="${1:-$root/out/nx}/renut_gpu/host_shaders"
src="$root/app/src/renut_engine/gpu/shaders/host"
tools="$root/out/deko3d_tools"
mkdir -p "$out"
while read -r stem profile; do
  flags=(-spirv -fvk-use-dx-layout)
  [[ $profile == vs_* ]] && flags+=(-fvk-invert-y)
  dxc -T "$profile" -E main -HV 2021 -all-resources-bound -Wno-ignored-attributes "${flags[@]}" \
      -Fh "$out/$stem.spirv.h" -Vn "g_${stem}_spirv" "$src/$stem.hlsl" >/dev/null
  python3 "$root/tools/deko3d_host_shader.py" --dxc /usr/bin/dxc --spirv-cross "$tools/spirv-cross-build/spirv-cross" \
      --uam "$tools/uam-build/uam" --profile "$profile" --stem "$stem" --src "$src/$stem.hlsl" --out "$out/$stem.deko3d.h"
  echo "$stem ($profile)"
done <<'LIST'
overlay_vs vs_6_0
overlay_ps ps_6_0
present_vs vs_6_0
present_ps ps_6_0
depth_resolve_ps ps_6_0
depth_resolve_ms_ps ps_6_0
texture_mip_ps ps_6_0
resolve_copy_ps ps_6_0
rectangle_list_gs gs_6_0
point_sprite_gs gs_6_0
stream_convert_cs cs_6_0
target_readback_cs cs_6_0
LIST
