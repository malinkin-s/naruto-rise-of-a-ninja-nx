# Task: a plan to adapt the controls to the Nintendo Switch

The game is an Xbox 360 title; the port maps Switch input to an Xbox 360 pad in the SDK (sdk/src/input/, the
Switch input driver; sa2-nx has its own options: input_xbox_layout, input_joycon_sideways, per-player button
remapping in sa2.toml [input_p1] etc. - read ~/Projects/cloned/sa2-nx/app/sa2_switch.toml, README "Controls", and
the code behind those keys). Write a plan for this port: (1) what the SDK fork already offers and how to expose it in
app/naruto_switch.toml (the player's settings file); (2) A/B and X/Y by position vs by label (the game shows Xbox
button icons: options to swap or to keep positions), the triggers (ZL/ZR analog vs digital: does Naruto need analog
triggers?), the right stick, Joy-Con single / handheld / Pro Controller; (3) whether the game's button prompts can be
shown as Switch buttons (texture replacement of the button icons: how sa2-nx or other ports did it, if any); (4)
touchscreen or gyro: anything worth it. Keep it concrete: files, cvars, effort.
