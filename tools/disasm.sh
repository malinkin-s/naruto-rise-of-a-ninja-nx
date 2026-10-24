#!/bin/bash
# Prints a generated function's PPC instructions (from the codegen comments), with its labels and address of each.
#   tools/disasm.sh 8212F708 [gen dir]
fn=$1; gen=${2:-app/generated/default}
f=$(grep -l "DEFINE_REX_FUNC(sub_$fn)" "$gen"/*_recomp.*.cpp | head -1)
awk -v F="DEFINE_REX_FUNC(sub_$fn)" -v A=$((16#$fn)) 'index($0,F){p=1; a=A; next} p&&/^}/{exit}
  p&&/^loc_/{sub(":","",$0); a=strtonum("0x" substr($0,5)); print "  " $0 ":"; next}
  p&&/^\t\/\/ /{sub(/^\t\/\/ /,""); printf "%08X  %s\n", a, $0; a+=4}' "$f"
