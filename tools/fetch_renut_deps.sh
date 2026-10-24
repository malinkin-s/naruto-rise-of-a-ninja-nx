#!/bin/bash
# Copies the renderer's third-party trees into app/thirdparty/ (not committed: 84 MB) from sa2-nx at a pinned commit:
# plume (with banjo-nx's deko3d back end; MIT), reblue-XenosRecomp (the shader translator; MIT), uam (deko3d shader
# compiler; GPL-2.0+ / MIT parts), imgui (MIT). The source checkout is ~/Projects/sa2-nx or $SA2_NX (cloned if missing).
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
commit=adf3a4e
src=${SA2_NX:-$HOME/Projects/sa2-nx}
[ -d "$src/.git" ] || git clone https://github.com/ChanseyIsTheBest/sa2-nx.git "$src"
git -C "$src" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$src" fetch --unshallow 2>/dev/null || git -C "$src" fetch origin
mkdir -p "$root/app/thirdparty"
for d in plume reblue-XenosRecomp uam imgui; do
  rm -rf "$root/app/thirdparty/$d"
  git -C "$src" archive "$commit" "app/thirdparty/$d" | tar -x -C "$root/app/thirdparty" --strip-components=2
done
# DXC binaries (not in sa2-nx's tree): renderbag/dxc-bin at the commit naruto-rise-recomp pins.
dxc="$root/app/thirdparty/reblue-XenosRecomp/thirdparty/dxc-bin"
tmp=$(mktemp -d)
git clone -q https://github.com/renderbag/dxc-bin.git "$tmp/dxc-bin" && git -C "$tmp/dxc-bin" checkout -q 737ac9f51c3d06f0cd1ee7e14dc065bafd52310d
cp -r "$tmp/dxc-bin/bin" "$tmp/dxc-bin/lib" "$dxc/" 2>/dev/null || cp -r "$tmp/dxc-bin/bin" "$dxc/"
rm -rf "$tmp"
du -sh "$root"/app/thirdparty/*
