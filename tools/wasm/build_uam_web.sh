#!/bin/bash
# Builds tools/wasm/uam_web.cpp with Emscripten (Arch package emscripten: /usr/lib/emscripten) into out/uam-wasm/
# uam_web.mjs + .wasm, for the installer page (deko3d_shaders.bin made in the browser).
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
export PATH=/usr/lib/emscripten:$PATH
F="-DPIPE_ARCH_LITTLE_ENDIAN -DUTIL_ARCH_LITTLE_ENDIAN=1 -DUTIL_ARCH_BIG_ENDIAN=0"
emcmake cmake -S "$root/app/thirdparty/uam" -B "$root/out/uam-wasm" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  "-DCMAKE_C_FLAGS=$F" "-DCMAKE_CXX_FLAGS=$F" > /dev/null
ninja -C "$root/out/uam-wasm" uamlib
em++ -O2 -std=c++17 -I"$root/app/thirdparty/uam" "$root/tools/wasm/uam_web.cpp" "$root/out/uam-wasm/libuamlib.a" \
  -o "$root/out/uam-wasm/uam_web.mjs" -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=8MB -sMODULARIZE=1 -sEXPORT_ES6=1 \
  -sEXPORT_NAME=createUamWebModule -sEXPORTED_RUNTIME_METHODS=FS,ccall -sENVIRONMENT=web,worker,node \
  -sEXPORTED_FUNCTIONS=_uam_compile,_malloc,_free
ls -la "$root/out/uam-wasm/uam_web.mjs" "$root/out/uam-wasm/uam_web.wasm"
