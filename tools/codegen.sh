#!/bin/bash
# The game's code into app/generated (never committed), then the optimised flavour's post-codegen steps.
#   tools/codegen.sh            full flavour (tools/post_codegen.sh)
#   NARUTO_VOLATILE=1 ...       direct calls only (guest memory stays volatile)
#   NARUTO_CLASSIC=1 ...        the generator's output only
# The stamps go first: the generator skips a tree whose inputs did not change and would leave the post-processed
# files of an earlier run in place.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
rm -f "$root"/app/generated/*/codegen.stamp
(cd "$root/app" && "$root/sdk/out/linux-amd64/Release/rexglue" codegen naruto_manifest.toml) > "$root/out/codegen.log" 2>&1 \
  || { tail -20 "$root/out/codegen.log"; exit 1; }
tail -1 "$root/out/codegen.log"
[ "$NARUTO_CLASSIC" = 1 ] || "$root/tools/post_codegen.sh"
