# Female JK External Candidate

This is a non-destructive runtime export from:

`E:\下载\建模3  金色卷发jk女 T字版  多动作版.blend`

The source `.blend` is not modified. The source contains a 344-bone authoring
rig, 68 weighted deform-boundary bones, and controller/constraint animation.
The GLB was exported from a working copy with controller evaluation baked onto
the weighted deform boundary.

Observed source actions:

- `idle`
- `walking`
- `running`
- `left turn`
- `right turn`
- `boxing`
- `sword attack`
- `drinking`
- `waveing`
- `walking2`

The copied jump clip comes from the reviewed black-haired female source.
Contact windows for boxing and sword attack remain evidence candidates, not
automatic hit results. The working export contains three explicit right-hand sockets (`weapon_hand`,
`weapon_slot:sword`, and `weapon_hit_volume:sword`), but those sockets do not
turn the sword clip into a qualified melee action without timing evidence. The
action names are not treated as qualification evidence. No action is promoted
merely because its clip is named `boxing` or `sword attack`.
