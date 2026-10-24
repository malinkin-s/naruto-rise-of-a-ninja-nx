#!/bin/bash
# Scripted PC run (SOL-TEST-2): the SDK's input_script plus window screenshots at given times.
#   tools/pc/scripted.sh NAME SECONDS 'input script' 'shot times...'
#   e.g. tools/pc/scripted.sh title 60 '10:START,20:A' '15 25 40'
# Input script format: 'seconds:button[:hold],...' from the first input poll (sdk input_system.cpp).
# REPLAY=<file.nxinput> (optional): play a recorded pad session (tools/pc/record.sh) instead of the input script.
# SAVE=<dir> (optional): a snapshot of user data (out/saves/<name>) copied into the run's own user data root, so every
# run starts from the same saves (empty without it).
# Output: out/runs/NAME/{boot.log,shot_<t>.png,sheet.jpg,user/}. Screenshots are game content: they stay in out/ (ignored).
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
[ -n "$REPLAY" ] && REPLAY=$(realpath "$REPLAY")
[ -n "$SAVE" ] && SAVE=$(realpath "$SAVE")
#   tools/pc/scripted.sh NAME tools/pc/scenarios/<x>.sh       (a scenario file sets SCRIPT, SECS, SHOTS)
if [ -f "$2" ]; then . "$2"; name=$1; secs=$SECS; script=$SCRIPT; shots=$SHOTS
else name=$1; secs=$2; script=$3; shots=$4; fi
dir="$root/out/runs/$name"; rm -rf "$dir"; mkdir -p "$dir"
mkdir -p "$dir/user"
[ -n "$SAVE" ] && cp -r "$SAVE"/. "$dir/user/"
cd "$root/out/pc"
export LD_LIBRARY_PATH="$root/sdk/out/linux-amd64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
timeout "$secs" ./naruto --game_data_root="$root/game" --gpu_plugin=xenos --log_file="$dir/boot.log" --user_data_root="$dir/user" \
  $( [ -n "$REPLAY" ] && echo "--input_replay=$REPLAY" || echo "--input_script=$script" ) \
  > "$dir/stdout.txt" 2>&1 &
tpid=$!
sleep 2
pid=$(pgrep -P "$tpid" -x naruto || pgrep -n -x naruto)
python3 -I - "$pid" "$dir" $shots <<'PY'
import json, subprocess, sys, time
pid, out, times = int(sys.argv[1]), sys.argv[2], [float(t) for t in sys.argv[3:]]
start = time.monotonic() - 2  # the game started ~2 s before this
for t in times:
    time.sleep(max(0, t - (time.monotonic() - start)))
    c = [c for c in json.loads(subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True).stdout)
         if c["pid"] == pid]
    if not c:
        print(f"no window at {t:g} s"); continue
    geo = "%d,%d %dx%d" % (*c[0]["at"], *c[0]["size"])
    subprocess.run(["grim", "-g", geo, f"{out}/shot_{t:g}.png"])
PY
wait "$tpid" || true
# Contact sheet of the screenshots (out/runs/NAME/sheet.jpg).
shots_png=$(ls "$dir"/shot_*.png 2>/dev/null | sort -t_ -k2 -g)
if [ -n "$shots_png" ]; then
  for f in $shots_png; do
    magick "$f" -resize 400x -gravity north -background white -splice 0x18 -pointsize 15 \
      -annotate +0+1 "$(basename "${f%.png}")" "$dir/t_$(basename "$f")"
  done
  magick montage $(ls "$dir"/t_shot_*.png | sort -t_ -k3 -g) -tile 4x -geometry +3+3 "$dir/sheet.jpg"
  rm -f "$dir"/t_shot_*.png
fi
grep -iE "\[error\]|fatal|unregistered|RtlUnwind|input_script|input_replay" "$dir/boot.log" | cut -c27-200 | sort | uniq -c | sort -rn | head -12
