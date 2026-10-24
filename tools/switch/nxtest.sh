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
# Output: out/runs/NAME/nx.log, shot_<s>.png (NX_SHOTS), rex_profile.log; a summary of errors at the end. The PC must accept TCP 28780 from the console.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
[ -f "$root/tools/switch/nx.env" ] && . "$root/tools/switch/nx.env"
name=$1; secs=$2; script=$3; shift 3 2>/dev/null || shift $#
[ -n "$NX_IP" ] && [ -n "$name" ] && [ -n "$secs" ] || { sed -n 2,6p "$0"; exit 1; }
port=${NX_LOG_PORT:-28780}
host=$(ip -4 route get "$NX_IP" | grep -oP 'src \K\S+')
dir="$root/out/runs/$name"; rm -rf "$dir"; mkdir -p "$dir"
args=(--log_network="$host:$port" --test_exit_after_s="$secs")
# NX_SHOTS="20 40 60": frames of the renderer at those seconds, sent with the log (default: every 20 s).
shots=${NX_SHOTS:-$(seq -s ' ' 20 20 $((secs - 5)))}
[ -n "$shots" ] && args+=(--test_shots="${shots// /,}")
# NX_PROFILE=1: the SDK's profiler samples each busy thread's stack at 1 kHz (sdk/src/ui/switch_perf.cpp); its report
# (logs/rex/rex_profile.log, always written) comes back at the end of the run as rex_profile.log.
# Only the threads named in NX_PROFILE_THREADS (name prefixes, comma separated, no spaces; default the game's main
# thread): pausing every thread cut the network log.
[ "$NX_PROFILE" = 1 ] && args+=(--switch_profile_stacks=true --switch_profile_threads="${NX_PROFILE_THREADS:-Main}")
[ -n "$script" ] && args+=(--input_script="$script")
args+=("$@")
echo "console $NX_IP, log to $host:$port, args: ${args[*]}"

# A listener left by an earlier run (a crashed game never closes its log connection) still holds the port.
pkill -f "python3 -I - $port " 2>/dev/null && sleep 1
# The listener: the game's log (one connection, written as it arrives) and its frames (test_shots: one connection
# each, "NXSHOT <s> <w> <h> <bytes>" then RGBX rows -> shot_<s>.png). Ends when the log connection closes or after
# SECONDS + 120.
python3 -I - "$port" "$dir" $((secs + 120)) <<'PY' &
import socket, subprocess, sys, threading, time
port, out, limit = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port)); s.listen(4); s.settimeout(1)
deadline = time.monotonic() + limit
log_done = threading.Event()
log_seen = threading.Event()

def recv_exact(c, n):
    buf = bytearray()
    while len(buf) < n:
        d = c.recv(min(1 << 20, n - len(buf)))
        if not d:
            break
        buf += d
    return bytes(buf)

def handle(c, addr):
    c.settimeout(10)
    try:
        first = c.recv(6, socket.MSG_PEEK | socket.MSG_WAITALL)
    except OSError:
        c.close(); return
    if first == b"NXFILE":
        header = b""
        while not header.endswith(b"\n"):
            ch = c.recv(1)
            if not ch: break
            header += ch
        _, fname, n = header.split()
        data = recv_exact(c, int(n))
        c.close()
        fname = fname.decode().replace("/", "_")
        with open(f"{out}/{fname}", "wb") as f:
            f.write(data)
        print(f"listener: file {fname} ({len(data)} of {int(n)} bytes)", flush=True)
        return
    if first == b"NXSHOT":
        header = b""
        while not header.endswith(b"\n"):
            ch = c.recv(1)
            if not ch: break
            header += ch
        _, sec, w, h, n = header.split()
        data = recv_exact(c, int(n))
        c.close()
        if len(data) == int(n):
            png = f"{out}/shot_{int(sec):03d}.png"
            subprocess.run(["magick", "-size", f"{int(w)}x{int(h)}", "-depth", "8", "rgba:-", "-alpha", "off", png],
                           input=data, check=False)
            print(f"listener: frame at {int(sec)} s -> {png}", flush=True)
        return
    log_seen.set()
    print(f"listener: log connected from {addr[0]}", flush=True)
    c.settimeout(5)
    with open(f"{out}/nx.log", "ab") as f:
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
    c.close()
    log_done.set()

while time.monotonic() < deadline and not log_done.is_set():
    try:
        c, addr = s.accept()
    except socket.timeout:
        continue
    threading.Thread(target=handle, args=(c, addr), daemon=True).start()
time.sleep(2)  # a frame still arriving
print("listener: done" if log_seen.is_set() else "listener: the game never connected", flush=True)
PY
listener=$!
sleep 1

# Wait for hbmenu's netloader (UDP ping, does not use it up): the user just opens it after each run.
python3 -I "$root/tools/switch/nx_wait.py" "$NX_IP" "${NX_WAIT:-900}" || { kill $listener 2>/dev/null; exit 1; }

docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:$root" -w "$root" naruto-nx/devkita64 \
  /opt/devkitpro/tools/bin/nxlink -a "$NX_IP" -p naruto-nx/naruto.nro out/nx/naruto.nro -- "${args[@]}" \
  || { kill $listener 2>/dev/null; echo "nxlink failed: is hbmenu in netloader mode (Y)?"; exit 1; }

wait $listener || true
if ls "$dir"/shot_*.png >/dev/null 2>&1; then
  magick montage "$dir"/shot_*.png -tile 4x -geometry 400x+3+3 "$dir/sheet.jpg" && echo "== frames: $dir/sheet.jpg"
fi
echo "== $dir/nx.log: $(wc -l < "$dir/nx.log" 2>/dev/null || echo 0) lines"
grep -iE "\[error\]|\[critical\]|fatal|unregistered|RtlUnwind|abort|exception|C0000017|registered [0-9]+ functions|test_exit" \
  "$dir/nx.log" 2>/dev/null | sed -E 's/\[t[0-9]+\] //' | cut -c27-220 | sort | uniq -c | sort -rn | head -25
