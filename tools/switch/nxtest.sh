#!/bin/bash
# Automated console run over the network: sends out/nx/naruto.nro with nxlink, receives the game's log live.
#   NX_IP=<console IP> tools/switch/nxtest.sh NAME SECONDS ['input script'] [extra --cvar=value ...]
#   e.g. NX_IP=192.168.1.50 tools/switch/nxtest.sh boot 120
#        NX_IP=192.168.1.50 tools/switch/nxtest.sh title 90 '10:START,14:START,18:START,22:START,26:START'
# NX_IP may also be set in tools/switch/nx.env (NX_IP=..., not committed).
#
# On the console: hbmenu started with title override (hold R while starting a game: full memory), then Y (netloader).
# The script waits for the netloader by itself (tools/switch/nx_wait.py, up to NX_WAIT seconds, default 900): after a
# run, just open the netloader again. hbmenu does not go back to it when the game exits.
# The game files must already be on the SD (tools/switch/package.sh, sdmc:/switch/naruto-nx/game).
# The NRO is written to sdmc:/switch/naruto-nx/naruto.nro (nxlink -p naruto-nx/naruto.nro: hbmenu's netloader puts
# /switch/ in front itself) and started with:
#   --log_network=<this PC>:28780   every log line and stdout/stderr over TCP (sdk/src/core/logging.cpp)
#   --test_exit_after_s=SECONDS     the run quits by itself (app/src/naruto_test_exit.cpp) and returns to hbmenu
#   --input_script=...              when given (sdk input_script: 'seconds:button[:hold],...')
# Output: out/runs/NAME/nx.log; a summary of errors at the end. The PC must accept TCP 28780 from the console.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
[ -f "$root/tools/switch/nx.env" ] && . "$root/tools/switch/nx.env"
name=$1; secs=$2; script=$3; shift 3 2>/dev/null || shift $#
[ -n "$NX_IP" ] && [ -n "$name" ] && [ -n "$secs" ] || { sed -n 2,6p "$0"; exit 1; }
port=${NX_LOG_PORT:-28780}
host=$(ip -4 route get "$NX_IP" | grep -oP 'src \K\S+')
dir="$root/out/runs/$name"; rm -rf "$dir"; mkdir -p "$dir"
args=(--log_network="$host:$port" --test_exit_after_s="$secs")
[ -n "$script" ] && args+=(--input_script="$script")
args+=("$@")
echo "console $NX_IP, log to $host:$port, args: ${args[*]}"

# The log listener: one connection, written as it arrives; ends when the game closes it or after SECONDS + 120.
python3 -I - "$port" "$dir/nx.log" $((secs + 120)) <<'PY' &
import socket, sys, time
port, out, limit = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port)); s.listen(1); s.settimeout(limit)
deadline = time.monotonic() + limit
try:
    c, addr = s.accept()
except socket.timeout:
    print("log listener: the game never connected"); sys.exit(1)
print(f"log listener: connected from {addr[0]}")
c.settimeout(5)
with open(out, "wb") as f:
    while time.monotonic() < deadline:
        try:
            d = c.recv(65536)
        except socket.timeout:
            continue
        except OSError:
            break
        if not d:
            break
        f.write(d); f.flush()
print("log listener: done")
PY
listener=$!
sleep 1

# Wait for hbmenu's netloader (UDP ping, does not use it up): the user just opens it after each run.
python3 -I "$root/tools/switch/nx_wait.py" "$NX_IP" "${NX_WAIT:-900}" || { kill $listener 2>/dev/null; exit 1; }

docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:$root" -w "$root" naruto-nx/devkita64 \
  /opt/devkitpro/tools/bin/nxlink -a "$NX_IP" -p naruto-nx/naruto.nro out/nx/naruto.nro -- "${args[@]}" \
  || { kill $listener 2>/dev/null; echo "nxlink failed: is hbmenu in netloader mode (Y)?"; exit 1; }

wait $listener || true
echo "== $dir/nx.log: $(wc -l < "$dir/nx.log" 2>/dev/null || echo 0) lines"
grep -iE "\[error\]|\[critical\]|fatal|unregistered|RtlUnwind|abort|exception|C0000017|registered [0-9]+ functions|test_exit" \
  "$dir/nx.log" 2>/dev/null | sed -E 's/\[t[0-9]+\] //' | cut -c27-220 | sort | uniq -c | sort -rn | head -25
