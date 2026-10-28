#!/usr/bin/env python3
"""Fetches a run's logs from the console's FTP server (anonymous, read only; e.g. ftpd on port 5000) into
out/runs/NAME/, for runs started from a HOME Menu forwarder: there is no netloader then, so no --log_network and no
test_shots upload. The game writes its logs next to the NRO (logs/rex/rex_profile.log, the rotating file log).

  python3 tools/switch/ftp_logs.py NAME [--dir /switch/naruto-nx] [--ip 192.168.0.165] [--port 5000]

Saves rex_profile.log, rex_crash.log (if any) and the newest file log as nx.log (the file `tools/switch/nxtest.sh`
would have captured from the network), so the same one-liners work on out/runs/NAME/. Exit 0 always.
"""
import argparse
import ftplib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def default_ip():
    env = os.path.join(ROOT, 'tools', 'switch', 'nx.env')
    try:
        for line in open(env):
            m = re.match(r'\s*(?:export\s+)?NX_IP\s*=\s*"?([^"\s]+)', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return ''


def fetch(ftp, remote, local):
    with open(local, 'wb') as f:
        ftp.retrbinary('RETR ' + remote, f.write)
    print(f'{remote} -> {local} ({os.path.getsize(local)} bytes)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--dir', default='/switch/naruto-nx')
    ap.add_argument('--ip', default=default_ip())
    ap.add_argument('--port', type=int, default=int(os.environ.get('NX_FTP_PORT', '5000')))
    a = ap.parse_args()
    out = os.path.join(ROOT, 'out', 'runs', a.name)
    os.makedirs(out, exist_ok=True)
    try:
        ftp = ftplib.FTP()
        ftp.connect(a.ip, a.port, timeout=15)
        ftp.login()
    except (OSError, ftplib.Error) as e:
        print(f'no FTP on {a.ip}:{a.port} ({e}): turn the console\'s FTP server on')
        return 0
    logs = a.dir.rstrip('/') + '/logs'
    for sub in ('rex', ''):
        d = logs + ('/' + sub if sub else '')
        try:
            ftp.cwd(d)
            names = sorted(os.path.basename(n) for n in ftp.nlst())
        except ftplib.Error as e:
            print(f'{d}: {e}')
            continue
        print(f'{d}: {len(names)} files, last: {names[-4:]}')
        for want, local in (('rex_profile.log', 'rex_profile.log'), ('rex_crash.log', 'rex_crash.log')):
            if want in names:
                fetch(ftp, d + '/' + want, os.path.join(out, local))
        file_logs = [n for n in names if n.endswith('.log') and n not in ('rex_profile.log', 'rex_crash.log', 'rex_stderr.log')]
        if file_logs and not os.path.exists(os.path.join(out, 'nx.log')):
            fetch(ftp, d + '/' + file_logs[-1], os.path.join(out, 'nx.log'))
    ftp.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
