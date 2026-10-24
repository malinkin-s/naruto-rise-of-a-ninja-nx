# New Game -> intro -> Konoha -> the first story autosave ("MISSION UPDATE: Steal the Forbidden Scroll", ~93 s on the
# input clock). The user's pad session (inputs/first_autosave.nxinput) cut at 100 s with tools/pc/trim_input.py:
# replayed whole, it drifted after this autosave (2nd autosave at 128 s instead of 173 s).
# After the run, out/runs/<name>/user is the snapshot for the next piece (kept as out/saves/autosave1).
REPLAY=${REPLAY:-$(dirname "${BASH_SOURCE[0]}")/../inputs/new_game_to_autosave1.nxinput}
SCRIPT=''
SECS=125
SHOTS='60 95 105 120'
