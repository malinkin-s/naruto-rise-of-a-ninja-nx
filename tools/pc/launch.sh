#!/bin/bash
# Starts the PC build for a test run and waits for it.
#   tools/pc/launch.sh SECONDS STDOUT_FILE ./naruto args...      (run from out/pc)
# NARUTO_DISPLAY selects where the window goes:
#   ws2 (default): a window on Hyprland workspace 2, opened there silently (a runtime window rule by class/title,
#                  hyprctl eval with hl.window_rule; the user asked for runs out of the way of the desktop they work on)
#   xvfb:          a private Xvfb server (tools/pc/xrun.sh): no window on the desktop at all.
#   direct:        a child of this shell on the current workspace.
# The game quits by itself (--test_exit_after_s=SECONDS is added); after SECONDS + 30 it is killed. Core dumps are
# off (a crash must not set off the desktop's crash handling). Frames are never grabbed from the screen.
set -u
secs=$1; out=$2; shift 2
mode=${NARUTO_DISPLAY:-ws2}
export LD_LIBRARY_PATH="$(cd ../../sdk/out/linux-amd64 && pwd)${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
args=("$@" --test_exit_after_s="$secs")
case "$mode" in
  direct)
    ( ulimit -c 0; timeout $((secs + 30)) "${args[@]}" ) > "$out" 2>&1; exit $? ;;
  xvfb)
    ( timeout $((secs + 30)) "$(dirname "$0")/xrun.sh" "${args[@]}" ) > "$out" 2>&1; exit $? ;;
esac
# ws2: a runtime window rule (until Hyprland's config is reloaded; the user's config is not changed) sends the game's
# window to workspace 2 without switching to it; the game stays a child of this shell.
for match in 'class = "^([Nn]aruto)$"' 'title = "^([Nn]aruto.*)$"'; do
  hyprctl eval "hl.window_rule({ match = { $match }, workspace = \"2 silent\" })" >/dev/null 2>&1
done
( ulimit -c 0; timeout $((secs + 30)) "${args[@]}" ) > "$out" 2>&1
