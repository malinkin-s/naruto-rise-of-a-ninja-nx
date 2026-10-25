#!/bin/bash
# Post-codegen steps of the optimised flavour (sa2-nx tools/post_codegen.py, its first three), on both generated trees.
# Run after every `rexglue codegen app/naruto_manifest.toml` (the generator rewrites the files without them):
#   1. tools/pch_no_volatile.py: guest loads/stores without volatile (masseffect-nx: +15-20 % fps);
#   2. tools/loop_barriers.py: a compiler barrier at loop headers, REQUIRED with 1 (GCC -O3 hoists a guest polling
#      loop's load out of the loop: the thread spins forever);
#   3. tools/direct_calls.py --redo: calls between unhooked functions made direct (inlinable);
#   4. tools/store_cards.py: every guest store outside the stack marks its 4 KB page's card, so Renut proves its cached
#      vertex and index copies by the cards instead of hashing them at every kick (sa2-nx: a quarter of the render
#      thread); then the strong g_banjo_store_cards = true goes into the generated code (src/naruto_renut_glue.cpp
#      keeps a weak false). NARUTO_NO_CARDS=1 skips it.
# NARUTO_VOLATILE=1 skips 1 and 2 (an A/B of the direct calls alone).
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
gen="$root/app/generated"
if [ "$NARUTO_VOLATILE" != 1 ]; then
  python3 "$root/tools/pch_no_volatile.py" "$gen/default/naruto_pch.h" "$gen/ai2c/naruto_pch.h"
  python3 "$root/tools/loop_barriers.py" "$gen/default" "$gen/ai2c"
fi
python3 "$root/tools/direct_calls.py" --redo
if [ "$NARUTO_NO_CARDS" != 1 ]; then
  for t in default ai2c; do python3 "$root/tools/store_cards.py" --gen "$gen/$t" --hot -; done
  flag="$gen/default/naruto_recomp.0.cpp"
  grep -q 'g_banjo_store_cards = true' "$flag" || printf '
// tools/post_codegen.sh: this code marks the store cards (tools/store_cards.py).
extern "C" const bool g_banjo_store_cards = true;
' >> "$flag"
fi
