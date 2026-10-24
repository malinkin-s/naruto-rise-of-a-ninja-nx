#!/usr/bin/env python3
"""Cuts a pad recording (tools/pc/record.sh, sdk input_record) at a time on its input clock.

  python3 -I tools/pc/trim_input.py IN.nxinput OUT.nxinput SECONDS

Keeps the states up to SECONDS and ends with the pad released (connected, nothing pressed, sticks centred), so a cut
in the middle of a press or a stick push does not leave it held for the rest of the replay. Long recordings drift
(the game is not deterministic: one press landing in another menu changes everything after it), so recordings are
cut at a known point, such as right after an autosave, and the next piece starts from that save.
"""
import sys

src, dst, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
limit = int(secs * 1e6)
lines = open(src).read().splitlines()
assert lines and lines[0].startswith("NXINPUT"), "not an input_record file"
kept = [l for l in lines[1:] if l.startswith("S ") and int(l.split()[1]) <= limit]
kept.append(f"S {limit} 1 0000 0 0 0 0 0 0")
open(dst, "w").write("\n".join([lines[0]] + kept) + "\n")
print(f"{len(kept) - 1} of {len(lines) - 1} states kept up to {secs:g} s -> {dst}")
