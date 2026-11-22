"""Compile L5 play patterns against trusted composition catalogs."""

import re
from collections.abc import Mapping, Set
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayPattern:
    play_pattern_id: str
    reactions: tuple[str, ...]
    pipelines: tuple[str, ...]
    workflows: tuple[str, ...]
    content_refs: tuple[str, ...]


class PlayPatternRejected(ValueError):
    def __init__(self, code: str, field: str):
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


def compile_play_pattern(
    declaration: Mapping[str, object],
    *,
    reaction_ids: Set[str],
    pipeline_ids: Set[str],
    workflow_ids: Set[str],
    pack_pins: Set[str],
) -> PlayPattern:
    if not isinstance(declaration, Mapping):
        raise PlayPatternRejected("pattern_schema_invalid", "play_pattern")
    if "writes" in declaration:
        raise PlayPatternRejected("pattern_declares_writes", "writes")

    catalogs = {
        "reactions": reaction_ids,
        "pipelines": pipeline_ids,
        "workflows": workflow_ids,
        "content_refs": pack_pins,
    }
    for field in declaration:
        if field != "play_pattern_id" and field not in catalogs:
            raise PlayPatternRejected("pattern_schema_invalid", str(field))

    pattern_id = declaration.get("play_pattern_id")
    if not isinstance(pattern_id, str) or not re.fullmatch(r"\S+", pattern_id):
        raise PlayPatternRejected("pattern_schema_invalid", "play_pattern_id")

    references = {}
    for field, registered in catalogs.items():
        entries = declaration.get(field, [])
        if not isinstance(entries, list):
            raise PlayPatternRejected("pattern_schema_invalid", field)
        ordered_refs: dict[str, None] = {}
        for entry in entries:
            if field == "content_refs" and isinstance(entry, Mapping) and entry.keys() == {"pack"}:
                entry = entry["pack"]
            if not isinstance(entry, str) or not entry:
                raise PlayPatternRejected("pattern_schema_invalid", field)
            if field == "content_refs" and not re.fullmatch(r"[^\s@]+@[^\s@]+", entry):
                raise PlayPatternRejected("pattern_schema_invalid", field)
            if entry not in registered:
                raise PlayPatternRejected("pattern_reference_unknown", field)
            if entry in ordered_refs:
                raise PlayPatternRejected("pattern_reference_duplicate", field)
            ordered_refs[entry] = None
        references[field] = tuple(ordered_refs)

    return PlayPattern(
        play_pattern_id=pattern_id,
        reactions=references["reactions"],
        pipelines=references["pipelines"],
        workflows=references["workflows"],
        content_refs=references["content_refs"],
    )
