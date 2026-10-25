#!/bin/bash
# Hands one research task to Gemini through agy (the user's agy-dns wrapper), read-only, and saves its report.
#   tools/gemini/run_task.sh tools/gemini/tasks/<name>.md [model]
# Output: out/gemini/<name>.md (the report) and out/gemini/<name>.log (agy's stderr). Default model gemini-3.8-flash-high.
# --mode plan: the agent reads and searches but never edits the repository (Claude works in the same tree meanwhile).
# Every task carries the same rules (tools/gemini/rules.md): no game data or code generated from it leaves the PC.
# Run several at once (each in the background); GEMINI_TIMEOUT (seconds, default 2400) bounds one task.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
task=$1; model=${2:-gemini-3.8-flash-high}
[ -f "$task" ] || { sed -n 2,7p "$0"; exit 1; }
name=$(basename "$task" .md)
mkdir -p "$root/out/gemini"
prompt="$(cat "$root/tools/gemini/rules.md")

$(cat "$task")"
cd "$root"
timeout "${GEMINI_TIMEOUT:-2400}" agy-dns -p "$prompt" --model "$model" --mode plan \
  --print-timeout "${GEMINI_TIMEOUT:-2400}s" > "out/gemini/$name.md" 2> "out/gemini/$name.log" || true
echo "gemini: $name -> out/gemini/$name.md ($(wc -l < "out/gemini/$name.md") lines)"
