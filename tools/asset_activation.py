"""Restore an archived art pack into an explicit active path.

The archive remains untouched. The copied active pack is still opt-in and must
be referenced by an adapter scene or manifest; this command never changes the
default validation scene.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Archived source remains the only restore authority: archive/ -> assets/active/.
ARCHIVE_ROOT = ROOT / "archive"
INVENTORY = ROOT / "archive" / "asset-inventory.json"


def load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def list_packs() -> int:
    for pack in load_inventory()["packs"]:
        print(
            f"{pack['id']}: {pack['category']} "
            f"{pack['path']} -> {pack['restore_target']}"
        )
    return 0


def restore(pack_id: str) -> int:
    matches = [pack for pack in load_inventory()["packs"] if pack["id"] == pack_id]
    if not matches:
        raise SystemExit(f"Unknown archived pack: {pack_id}")
    pack = matches[0]
    source = ROOT / pack["path"]
    target = ROOT / pack["restore_target"]
    if not source.is_dir():
        raise SystemExit(f"Archived pack is missing: {source}")
    if target.exists():
        raise SystemExit(f"Restore target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    if pack_id == "crusader_knight":
        wrapper_source = ROOT / "archive" / "scenes" / "legacy" / "KnightRoleSkin.tscn"
        wrapper_target = ROOT / "scenes" / "active" / pack_id / "KnightRoleSkin.tscn"
        wrapper_target.parent.mkdir(parents=True, exist_ok=True)
        wrapper_text = wrapper_source.read_text(encoding="utf-8")
        wrapper_text = wrapper_text.replace(
            "res://assets/characters/shared/crusader_knight.glb",
            "res://assets/active/crusader_knight/crusader_knight.glb",
        )
        wrapper_target.write_text(wrapper_text, encoding="utf-8")
    print(f"Restored {pack_id}: {target}")
    print("Archive preserved; activate it through an explicit adapter/manifest.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list archived packs")
    restore_parser = commands.add_parser("restore", help="copy one pack back")
    restore_parser.add_argument("pack_id")
    args = parser.parse_args()
    if args.command == "list":
        return list_packs()
    return restore(args.pack_id)


if __name__ == "__main__":
    raise SystemExit(main())
