#!/usr/bin/env python3
"""Waits until hbmenu's netloader is open on the console, without using up its one TCP connection.

  python3 -I tools/switch/nx_wait.py CONSOLE_IP [TIMEOUT_SECONDS]

nxlink finds a console by UDP: "nxboot" to port 28280, an open netloader answers "bootnx". This sends that ping every
2 s until the answer comes (exit 0) or the timeout passes (exit 1). A TCP probe of port 28280 would be taken as an
upload and close the netloader.
"""
import socket, sys, time

ip = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else 600
deadline = time.monotonic() + limit
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# The netloader answers to port 28771 (nxlink's), not to the sender's port: send from it, so the answer is also the
# reply a stateful firewall (ufw) lets in.
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 28771))
s.settimeout(2)
said = False
while time.monotonic() < deadline:
    s.sendto(b"nxboot", (ip, 28280))
    try:
        data, addr = s.recvfrom(64)
        if data.startswith(b"bootnx"):
            print(f"netloader open on {addr[0]}")
            sys.exit(0)
    except socket.timeout:
        pass
    if not said:
        print(f"waiting for the netloader on {ip} (hbmenu with title override, Y)...", flush=True)
        said = True
print("netloader did not open in time"); sys.exit(1)
