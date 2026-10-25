#!/bin/bash
# The game shaders' GLSL package for the Switch build (app/out/renut_switch/deko3d_glsl*.{bin,cpp}; game data, never
# committed), from tools/deko3d_shaders.py's GLSL in out/deko3d_shaders/glsl/glsl:
#   1. tools/deko3d_glsl_opt.py with every pass but scale1 and fragscale: those fold the texture scale code to 1x,
#      and Renut then keeps every target at 1280x720 (PackageScales, silently), so sa2_render_height_* (480 handheld)
#      would do nothing. Only the 97 shaders that read the scale code differ (2026-10-25);
#   2. tools/deko3d_shader_package.py -> app/out/renut_switch (taken by app/cmake/naruto_renut_gpu.cmake).
# Then tools/switch/build.sh.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
passes=$(cd "$root/tools" && python3 -c "
import sys; sys.argv = ['x']
import deko3d_glsl_opt as d
print(','.join(n for n, _ in d.PASSES if n not in ('scale1', 'fragscale')))")
python3 "$root/tools/deko3d_glsl_opt.py" --in "$root/out/deko3d_shaders/glsl/glsl" --out "$root/out/deko3d_shaders/glsl_opt" \
  --passes "$passes"
python3 "$root/tools/deko3d_shader_package.py" --glsl "$root/out/deko3d_shaders/glsl_opt" --out "$root/app/out/renut_switch"
