# PGO profile

Branch counts of one console session (about 15 minutes: Konoha, a fight, menus) of the instrumented NRO, one `.gcda` file per
object. Only function numbers, checksums and 64-bit counters: no code, no assets, no text. Made by `tools/pgo_merge.sh` from the
streams the instrumented NRO writes (`NARUTO_PGO=generate`, `app/src/naruto_pgo.cpp`), read by `-DNARUTO_PGO=use`.

Files are named by the object's path in the build tree (`#` for each `/`), so they match from any build tree with the same
layout; the few objects compiled from absolute source paths (the SDK's `rex_app.cpp` and similar, names with `home#...`) only
match a checkout at the same path, and compile without a profile elsewhere. Change no source and no generated code between the
instrumented build and the build that uses this profile: a changed function loses its counts. See `docs/HANDOFF.md` §6.
