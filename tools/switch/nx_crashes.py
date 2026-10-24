#!/usr/bin/env python3
"""Fetches the console's crash reports written since a test run started, and names the game's addresses in them.

Atmosphere writes atmosphere/crash_reports/<POSIX time>_<program id>.log when a process dies ("The software was
closed because an error occurred"); our NRO runs as hbloader (0100915020400000), its addresses read
"naruto + 0x<offset>". Read over the console's FTP server (anonymous, read only; e.g. ftpd on port 5000). Every report
of that time window is copied (other processes too: an overlay's crash shows up there as well), and for ours each
"naruto + 0x..." gets the function and source line from the run's ELF (llvm-addr2line; the ELF is linked at 0).

  python3 tools/switch/nx_crashes.py <console IP> <since: POSIX seconds> <out dir> <ELF> [--port 5000]
Exit 0 always (a console without an FTP server just has no reports to give).
"""
import ftplib
import os
import re
import subprocess
import sys

OURS = '0100915020400000'  # hbloader: the process an NRO runs in


def symbolize(text, elf):
    offsets = sorted(set(re.findall(r'naruto \+ (0x[0-9a-f]+)', text)))
    if not offsets or not os.path.isfile(elf):
        return text
    names = {}
    for off in offsets:
        r = subprocess.run(['llvm-addr2line', '-f', '-C', '-e', elf, off], capture_output=True, text=True).stdout
        lines = r.strip().split('\n')
        func = lines[0] if lines else '?'
        where = os.path.basename(lines[1]) if len(lines) > 1 else ''
        names[off] = f'{func[:110]} ({where})'
    return re.sub(r'naruto \+ (0x[0-9a-f]+)\)', lambda m: f'naruto + {m.group(1)}) {names.get(m.group(1), "")}', text)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 4:
        sys.exit(__doc__)
    ip, since, out, elf = args[0], int(args[1]), args[2], args[3]
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 5000
    try:
        ftp = ftplib.FTP()
        ftp.connect(ip, port, timeout=10)
        ftp.login()
        ftp.cwd('/atmosphere/crash_reports')
        names = [os.path.basename(n) for n in ftp.nlst()]
    except (OSError, ftplib.Error) as e:
        print(f'crash reports: no FTP on {ip}:{port} ({e})')
        return
    new = [n for n in names if n.endswith('.log') and re.match(r'\d+_', n) and int(n.split('_')[0]) >= since]
    if not new:
        print('crash reports: none since the run started')
    for name in sorted(new):
        chunks = []
        ftp.retrbinary('RETR ' + name, chunks.append)
        text = b''.join(chunks).decode('utf-8', 'replace')
        program = name.split('_')[1].split('.')[0]
        if program == OURS:
            text = symbolize(text, elf)
        path = os.path.join(out, 'crash_' + name)
        open(path, 'w', encoding='utf-8').write(text)
        head = re.search(r'Process Name:\s+(\S+)', text)
        print(f'crash report: {path} ({head.group(1) if head else program})')
        if program == OURS:
            for line in text.split('\n'):
                if re.search(r'^\s+(Type|Address|PC|LR|ReturnAddress\[0[0-7]\]):', line):
                    print('   ' + line.strip()[:200])
    ftp.quit()


if __name__ == '__main__':
    main()
