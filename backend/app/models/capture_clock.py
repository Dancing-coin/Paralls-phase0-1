from __future__ import annotations

import hashlib
from typing import Any


DEFAULT_CLOCK_DOMAIN = "legacy_producer_ts"


def normalize_clock_domain(clock_domain: str | None) -> str:
    return clock_domain or DEFAULT_CLOCK_DOMAIN


def derive_capture_root_id(
    *,
    clock_domain: str,
    room_id: str,
    scene_id: str,
    zone_id: str,
    monotonic_tick: int | None,
) -> str:
    tick = "unknown" if monotonic_tick is None else str(monotonic_tick)
    return f"capture_root:{normalize_clock_domain(clock_domain)}:{room_id}:{scene_id}:{zone_id}:{tick}"


def derive_capture_id(*, capture_root_id: str, consumer_scope: str, subject_id: str) -> str:
    subject = subject_id or "world"
    return f"capture:{capture_root_id}:{consumer_scope}:{subject}"


def derive_sample_ref_id(*, capture_root_id: str, source_kind: str, source_ref: str) -> str:
    digest = hashlib.sha256(f"{capture_root_id}|{source_kind}|{source_ref}".encode("utf-8")).hexdigest()[:12]
    return f"sample_ref:{source_kind}:{digest}"


def capture_clock_trace(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        getter = value.get
    else:
        getter = lambda key, default=None: getattr(value, key, default)
    return {
        "capture_root_id": getter("capture_root_id", ""),
        "capture_id": getter("capture_id", ""),
        "clock_domain": getter("clock_domain", ""),
        "monotonic_tick": getter("monotonic_tick", None),
        "source_frame_index": getter("source_frame_index", None),
        "wall_clock_ts": getter("wall_clock_ts", None),
        "sample_ref_id": getter("sample_ref_id", ""),
    }


def same_capture_tick(left: Any, right: Any, *, tick_tolerance: int = 0) -> bool:
    left_clock = capture_clock_trace(left)
    right_clock = capture_clock_trace(right)
    if left_clock["capture_root_id"] == "" or right_clock["capture_root_id"] == "":
        return False
    if left_clock["capture_root_id"] != right_clock["capture_root_id"]:
        return False
    if left_clock["clock_domain"] != right_clock["clock_domain"]:
        return False
    left_tick = left_clock["monotonic_tick"]
    right_tick = right_clock["monotonic_tick"]
    if left_tick is None or right_tick is None:
        return False
    return abs(int(left_tick) - int(right_tick)) <= tick_tolerance
