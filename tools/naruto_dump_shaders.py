#!/usr/bin/env python3
"""Dumps every Xbox 360 shader container of Naruto: Rise of a Ninja for Renut's translator (sa2_renderer = "renut").

Naruto's shaders are in two places: game/xeshader.sdb (the game's; containers stored without alignment, so the scan is
bytewise, as the PC base's tools/native-renderer/extract-sdb-containers.py does) and the loaded default.xex image
(Direct3D's own; out/default_image.bin, written by the codegen with REXGLUE_DUMP_IMAGE).

Output: <out>/{vs,ps}_<xxh3_64 of the container>.bin, each a complete container (virtual part, then physical part: the
layout XenosRecomp reads), and <out>/manifest.csv: the format of sa2-nx's tools/sa2_dump_shaders.py and reNut's
tools/dump_shaders.py (masterspike52), whose container check this copies. XXH3-64 comes from the system's libxxhash.

  python3 -I tools/naruto_dump_shaders.py [--sdb game/xeshader.sdb] [--image out/default_image.bin] [--out DIR]
"""
import argparse, csv, ctypes, ctypes.util, os, re, struct, sys

_lib = ctypes.CDLL(ctypes.util.find_library("xxhash") or "libxxhash.so.0")
_lib.XXH3_64bits.restype = ctypes.c_uint64
_lib.XXH3_64bits.argtypes = [ctypes.c_char_p, ctypes.c_size_t]


def xxh3_64_hex(blob):
    return "%016x" % _lib.XXH3_64bits(blob, len(blob))


SHADER_MAGIC = re.compile(rb"\x10\x2a\x11[\x00\x01]")


def find_shader_headers(data, aligned):
    """reNut's check: a container's sizes, tables and its physical part's (offset, size) agree."""
    found = []
    for m in SHADER_MAGIC.finditer(data):
        o = m.start()
        if (aligned and o % 4) or o + 0x24 > len(data):
            continue
        virt, phys = struct.unpack_from(">II", data, o + 4)
        ct, dt, so = struct.unpack_from(">III", data, o + 0x10)
        if not (0x24 <= virt < 0x10000 and 0 < phys < 0x100000 and o + virt + phys <= len(data)):
            continue
        if ct >= virt or dt >= virt or not (0x24 <= so < virt - 8):
            continue
        poff, psize = struct.unpack_from(">II", data, o + so)
        if poff + psize != phys:
            continue
        found.append(o)
    return found


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sdb", default=os.path.join(root, "game", "xeshader.sdb"))
    ap.add_argument("--image", default=os.path.join(root, "out", "default_image.bin"))
    ap.add_argument("--image-base", type=lambda s: int(s, 0), default=0x82000000)
    ap.add_argument("--out", default=os.path.join(root, "out", "renut_shader_dump"))
    args = ap.parse_args()
    sources = []
    for path, base, aligned in ((args.image, args.image_base, True), (args.sdb, 0, False)):
        if os.path.isfile(path):
            sources.append((path, base, aligned))
        else:
            print("warning: no %s" % path)
    if not sources:
        sys.exit("no inputs")
    os.makedirs(args.out, exist_ok=True)
    seen, manifest = set(), []
    for path, base, aligned in sources:
        data = open(path, "rb").read()
        count = 0
        for h in find_shader_headers(data, aligned):
            flags, virt, phys = struct.unpack_from(">III", data, h)
            blob = data[h:h + virt + phys]
            kind = "vs" if flags & 1 else "ps"
            name = "%s_%s" % (kind, xxh3_64_hex(blob))
            manifest.append((name, kind, virt, phys, os.path.basename(path), "0x%08x" % (base + h)))
            count += 1
            if name in seen:
                continue
            seen.add(name)
            with open(os.path.join(args.out, name + ".bin"), "wb") as fh:
                fh.write(blob)
        print("%-20s %5d shaders" % (os.path.basename(path), count))
    manifest.sort()
    with open(os.path.join(args.out, "manifest.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "type", "virtual_size", "physical_size", "source", "asset"])
        w.writerows(manifest)
    ps = sum(1 for n in seen if n.startswith("ps_"))
    print("%d unique shaders (%d ps, %d vs) -> %s" % (len(seen), ps, len(seen) - ps, args.out))


if __name__ == "__main__":
    main()
