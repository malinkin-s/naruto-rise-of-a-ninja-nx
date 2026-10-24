#!/bin/bash
# Removes the guest memory files the runtime leaves in /dev/shm (sdk/src/system/xmemory.cpp names them
# xenia_memory_<tick>; a run that is killed or crashes never unlinks them). They fill /dev/shm, and a full tmpfs gives
# SIGBUS to the game and to the desktop's compositor (Hyprland crashed this way; the user's diagnosis, 2026-10-24).
# Only when no instance of the game is running, so a live run keeps its memory.
if pgrep -x naruto >/dev/null; then
  echo "shm_clean: a game instance is running, nothing removed" >&2
  exit 0
fi
shopt -s nullglob
files=(/dev/shm/xenia_memory_*)
[ ${#files[@]} -gt 0 ] && { rm -f -- "${files[@]}"; echo "shm_clean: removed ${#files[@]} stale guest memory file(s)" >&2; }
exit 0
