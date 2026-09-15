# Astra Room

Source: `https://github.com/SushaanthSrinivasan/astra-room-test.git` at commit
`4ee2621011778da8702bff79585a5c97654ce232`.

`source/` is a shallow checkout of the upstream repository. Its only local
metadata file is `.gdignore`, which prevents Godot from importing upstream
preview images and does not change the room source. The selected asset is
`source/runs/high/room-high.blend`, the upstream project's highest-effort scene
with a recorded geometry validation pass.

`room-high.glb` is generated from that Blender source by:

```powershell
& 'D:\Programs\Blender\blender.exe' --background --python .\assets\environment\astra_room\export_to_godot.py
```

Godot imports the generated `.glb` directly. The upstream repository did not
include a license file at the pinned commit; confirm rights before shipping the
asset outside this local project.

For a ready-to-instance Godot entry point, open
`res://scenes/phase0/AstraRoom.tscn`. It wraps the imported GLB without changing
the existing `MainDemo.tscn`.

The Godot wrapper uses a soft cool window-light approximation, neutral blue-gray
environment fill, Reinhard tonemapping, and caps the imported floor-lamp light
to a low local accent. This is intentionally a realtime approximation; exact
pixel parity remains available from the original Blender render.

The latest verified preview is `godot-lighting-preview.png`.
