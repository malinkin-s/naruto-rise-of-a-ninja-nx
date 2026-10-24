#!/bin/bash
# Builds the Switch NRO (out/nx/naruto.nro) in the devkitA64 container.
#   tools/switch/build.sh [-reconfigure] [extra cmake -D options...]
# Image: naruto-nx/devkita64 = devkitpro/devkita64 updated with dkp-pacman -Syu (devkitA64 r30, GCC 16.1; the published
# image still had GCC 15.2 on 2026-10-24). The repository is mounted at its own path, so the absolute paths in
# app/generated/*.cmake (written by the host codegen) hold inside the container.
# No renderer yet: Mesa's NVK driver is not linked (REXGLUE_SWITCH_NO_NVK); an empty libvulkan.a satisfies the SDK's
# check, the Vulkan headers come from sdk/thirdparty/vulkan-headers.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
build="$root/out/nx"
stub="$root/out/nx-deps/nvk-stub"
if [ ! -f "$stub/lib/libvulkan.a" ]; then mkdir -p "$stub/lib" && ar rc "$stub/lib/libvulkan.a"; fi
reconfigure=0; [ "$1" = "-reconfigure" ] && { reconfigure=1; shift; }
cfg=""
if [ $reconfigure = 1 ] || [ ! -f "$build/build.ninja" ]; then
  cfg="cmake -S '$root/app' -B '$build' -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE='$root/tools/switch/cmake/switch-devkitA64.cmake' -DDEVKITPRO=/opt/devkitpro \
    -DREXGLUE_SWITCH_NVK_SDK='$stub' -DREXGLUE_SWITCH_NO_NVK=ON $* &&"
fi
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:$root" -w "$root" naruto-nx/devkita64 \
  bash -c "$cfg cmake --build '$build' -j$(nproc)"
ls -la "$build"/*.nro
