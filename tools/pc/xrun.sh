#!/bin/bash
# Runs the PC build inside a private Xvfb server: the game's window never reaches the desktop's compositor (two
# Hyprland crashes coincided with test runs: an NVIDIA EGL SIGBUS while the game's Vulkan window was on screen, and
# one right after a game crash). Core dumps are off, so a game crash does not set off the desktop's crash handling.
#   tools/pc/xrun.sh <command...>     (e.g. tools/pc/xrun.sh tools/pc/frames.sh NAME ...)
set -e
display=:97
if ! pgrep -f "Xvfb $display" >/dev/null; then
  Xvfb $display -screen 0 1280x720x24 -nolisten tcp >/dev/null 2>&1 &
  sleep 1
fi
ulimit -c 0
exec env -u WAYLAND_DISPLAY -u HYPRLAND_INSTANCE_SIGNATURE DISPLAY=$display SDL_VIDEODRIVER=x11 "$@"
