"""Export the validated Astra room source scene to Godot's native glTF format."""

from pathlib import Path

import bpy


ASSET_ROOT = Path(__file__).resolve().parent
SOURCE_BLEND = ASSET_ROOT / "source" / "runs" / "high" / "room-high.blend"
OUTPUT_GLB = ASSET_ROOT / "room-high.glb"


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT_GLB),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_materials="EXPORT",
        export_normals=True,
        export_tangents=True,
        export_lights=True,
        export_cameras=False,
        export_yup=True,
    )


if __name__ == "__main__":
    main()
