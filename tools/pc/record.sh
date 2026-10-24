#!/bin/bash
# Records a pad session for later automatic runs (sdk input_record).
#   tools/pc/record.sh NAME [SAVE_SNAPSHOT]
# Starts the PC build with an empty user data root (or a copy of SAVE_SNAPSHOT), so the replay, which starts from the
# same state, sees the same menus. Play with the pad (the window needs the focus), close the window when done.
# Writes: tools/pc/inputs/NAME.nxinput (the recording: pad states only, no game data), out/saves/NAME/ (the saves
# the session made: a snapshot for SAVE=), out/runs/rec_NAME/boot.log.
# Replay: REPLAY=tools/pc/inputs/NAME.nxinput tools/pc/scripted.sh NAME_replay SECONDS '' 'shot times'
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
name=$1; snap=${2:+$(realpath "$2")}
[ -n "$name" ] || { echo "usage: $0 NAME [SAVE_SNAPSHOT]"; exit 1; }
mkdir -p "$root/tools/pc/inputs" "$root/out/runs/rec_$name"
user="$root/out/saves/$name"; rm -rf "$user"; mkdir -p "$user"
[ -n "$snap" ] && cp -r "$snap"/. "$user/"
cd "$root/out/pc"
export LD_LIBRARY_PATH="$root/sdk/out/linux-amd64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
./naruto --game_data_root="$root/game" --gpu_plugin=xenos --user_data_root="$user" \
  --log_file="$root/out/runs/rec_$name/boot.log" --input_record="$root/tools/pc/inputs/$name.nxinput" || true
echo "recorded $(grep -c '^S ' "$root/tools/pc/inputs/$name.nxinput") pad states to tools/pc/inputs/$name.nxinput"
echo "saves: out/saves/$name"
