# Female Bandage External

This package is a fresh runtime export from:

`E:\下载\建模1 绷带血迹黑长直 T字版本 多动作版本.blend`

The source blend and its byte-for-byte working copy remain unchanged. Blender
5.1.2 exported the GLB, then the export script removed only the two non-deform
hand-FK controller nodes/tracks from the runtime boundary. The package keeps
the source's 344-bone authoring rig boundary and ships 68 weighted deform skin
joints.

The package contains Idle/Walk/Run/Jump/Turn locomotion, full-body exclusive
boxing and `SWORD ATTACK`. The three weapon anchors are real GLB nodes attached
to `hand.r`: `weapon_hand`, `weapon_slot:sword`, and
`weapon_hit_volume:sword`.

The Godot 4.6.3 headless qualification runner imported this exact GLB and
reported `qualified`; the machine-readable result is recorded under
`assets/characters/qualification_reports/female_bandage_external.json`. The
qualification claim comes from that import and audit, not from the source
filename or the user's declaration.
