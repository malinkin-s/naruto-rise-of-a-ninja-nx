#!/bin/bash
# Profile-guided optimisation, step 2 of 3 (from sa2-nx's tools/win/pgo_merge.ps1). Step 1 is the instrumented NRO
# (NX_BUILD_DIR=$PWD/out/nx-pgo tools/switch/build.sh -DNARUTO_PGO=generate ...), played on the console: it writes
# pgo/naruto_pgo_<N>.stream next to the NRO (one per session, app/src/naruto_pgo.cpp). Copy that folder to the PC and run
#   tools/pgo_merge.sh <folder with the .stream files>
# Every session's counts are added into the .gcda files of the profile folder (pgo/ at the root, the build's
# NARUTO_PGO_DIR: one .gcda per object, named by the object's path in the build tree), then their summary is filled in
# (tools/pgo_summary.py: the stream API writes it as zero). Step 3: build with -DNARUTO_PGO=use.
# gcov-tool merge-stream ADDS to .gcda files already there: a second run with the same streams would count them twice,
# so this stops when pgo/ already has .gcda files (move them aside first). gcov-tool runs in the devkitA64 container.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
streams=${1:?usage: tools/pgo_merge.sh <folder with naruto_pgo_*.stream>}
streams=$(cd "$streams" && pwd)
out="$root/pgo"
mkdir -p "$out"
if find "$out" -name '*.gcda' | grep -q .; then echo "$out already has .gcda files: move them aside first"; exit 1; fi
ls "$streams"/naruto_pgo_*.stream > /dev/null
n=$(ls "$streams"/naruto_pgo_*.stream | wc -l)
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:$root" -v "$streams:$streams:ro" -w "$root" naruto-nx/devkita64 bash -c "
  for f in $streams/naruto_pgo_*.stream; do
    echo merging \$f \$(du -h \$f | cut -f1)
    /opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcov-tool merge-stream \$f
  done"
count=$(find "$out" -name '*.gcda' | wc -l)
[ "$count" -gt 0 ] || { echo "no .gcda file in $out after merging: the streams name another folder (merge in the tree that built the instrumented NRO)"; exit 1; }
python3 "$root/tools/pgo_summary.py" "$out" "$n"
echo "$n session(s) merged into $count file(s) in $out"
