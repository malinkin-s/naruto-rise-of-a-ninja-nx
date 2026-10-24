#!/bin/bash
# A PC run whose frames come from the renderer itself (sa2_capture.cpp's recorder), not from the screen: nothing touches
# the compositor (grim once took the desktop, and a run with screen shots coincided with a Hyprland crash), works with
# the window hidden or on another workspace.
#   tools/pc/frames.sh NAME SECONDS START_S EVERY COUNT ['input script'] [extra flags...]
#   e.g. tools/pc/frames.sh renut1 60 10 300 8 '' --sa2_renderer=renut     (8 frames, one every 5 s from 10 s)
# REPLAY=<file.nxinput> and SAVE=<dir> as in scripted.sh. Output: out/runs/NAME/{boot.log,frame_<n>.png,sheet.jpg}.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
[ -n "$REPLAY" ] && REPLAY=$(realpath "$REPLAY")
[ -n "$SAVE" ] && SAVE=$(realpath "$SAVE")
name=$1; secs=$2; start=$3; every=$4; count=$5; script=$6; shift 6 || shift $#
dir="$root/out/runs/$name"; rm -rf "$dir"; mkdir -p "$dir/user"
[ -n "$SAVE" ] && cp -r "$SAVE"/. "$dir/user/"
gpu="--gpu_plugin=xenos"; case "$*" in *sa2_renderer=renut*) gpu="";; esac
input=(); [ -n "$REPLAY" ] && input=(--input_replay="$REPLAY"); [ -z "$REPLAY" ] && [ -n "$script" ] && input=(--input_script="$script")
cd "$root/out/pc"
rm -rf captures
export LD_LIBRARY_PATH="$root/sdk/out/linux-amd64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
timeout "$secs" ./naruto --game_data_root="$root/game" $gpu --log_file="$dir/boot.log" --user_data_root="$dir/user" \
  --sa2_video_s="$start" --sa2_video_every="$every" --sa2_video_frames="$count" --sa2_video_lockstep=false \
  "${input[@]}" "$@" > "$dir/stdout.txt" 2>&1 || true
raw=$(ls captures/*.rgba 2>/dev/null | head -1)
if [ -z "$raw" ]; then echo "no frames recorded"; else
  w=640; h=360  # half of the 1280x720 render; the .txt beside the video (written when it ends) wins
  [ -f "${raw%.rgba}.txt" ] && read -r w h _ < <(grep -oE "[0-9]+" "${raw%.rgba}.txt" | head -2 | tr '\n' ' ') || true
  bytes=$((w * h * 4)); n=$(( $(stat -c%s "$raw") / bytes ))
  for i in $(seq 0 $((n - 1))); do
    dd if="$raw" bs="$bytes" skip="$i" count=1 status=none | magick -size "${w}x${h}" -depth 8 rgba:- -alpha off "$dir/frame_$i.png"
  done
  magick montage "$dir"/frame_*.png -tile 4x -geometry 400x+3+3 "$dir/sheet.jpg"
  echo "$n frames ${w}x${h} -> $dir/sheet.jpg"
fi
grep -iE "\[error\]|fatal|unregistered|RtlUnwind|game frames" "$dir/boot.log" | cut -c27-220 | sort | uniq -c | sort -rn | head -8
