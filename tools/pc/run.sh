#!/bin/bash
# Runs the PC build (out/pc) with the SDK's emulated GPU.
#   tools/pc/run.sh [SECONDS] [extra rexglue flags...]    SECONDS: stop after that many (0 = until closed)
# Log: out/boot.log. The game files are expected in game/ (your own extracted disc).
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
secs=${1:-0}; shift || true
"$root/tools/pc/shm_clean.sh"  # stale /dev/shm guest memory (xenia_memory_*) before the run
trap '"$root/tools/pc/shm_clean.sh"' EXIT  # and after it
cd "$root/out/pc"
cmd=(./naruto --game_data_root="$root/game" --gpu_plugin=xenos --log_file="$root/out/boot.log" "$@")
export LD_LIBRARY_PATH="$root/sdk/out/linux-amd64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [ "$secs" -gt 0 ]; then timeout "$secs" "${cmd[@]}" || [ $? -eq 124 ]; else "${cmd[@]}"; fi
