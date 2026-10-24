#!/bin/bash
# The SD card folder: out/nx/sdcard/switch/naruto-nx/{naruto.nro, game/}.
#   tools/switch/package.sh [-nogame]
# game/ is your own extracted disc (hard links to game/, no copy). Copy out/nx/sdcard/ to the root of the SD card.
# On the console: hbmenu -> Naruto: Rise of a Ninja (launch it with title override, holding R on a game, for the full
# memory). Logs: sdmc:/switch/naruto-nx/logs/.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
dst="$root/out/nx/sdcard/switch/naruto-nx"
mkdir -p "$dst"
cp "$root/out/nx/naruto.nro" "$dst/naruto.nro"
if [ "$1" != "-nogame" ]; then
  rm -rf "$dst/game"
  cp -al "$root/game" "$dst/game" 2>/dev/null || cp -r "$root/game" "$dst/game"
fi
du -shL "$dst"/* | sed "s|$root/||"
