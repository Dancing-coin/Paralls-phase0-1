from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from types import MethodType

from pydantic import TypeAdapter
from pydantic_core import SchemaSerializer

from app.population_continuity import siming_contracts
from app.population_continuity.siming_contracts import PopulationReadSet, PopulationCadenceInput
from app.models.authority_event import AuthorityEvent


_NATIVE_DUMP = siming_contracts.dump_population_projections
_NATIVE_ADAPTER = siming_contracts._POPULATION_PROJECTIONS_ADAPTER
_NATIVE_SERIALIZER = _NATIVE_ADAPTER.serializer
_NATIVE_DUMP_METHOD = TypeAdapter.dump_python
_NATIVE_JSON_DUMPS = json.dumps
_NATIVE_CADENCE_PARSER = PopulationCadenceInput.from_authority_event.__func__
_NATIVE_READ_SET_BUILDER = PopulationReadSet.from_inputs.__func__
_NATIVE_EVENT = AuthorityEvent
_NATIVE_EVENT_INIT = AuthorityEvent.__init__
_NATIVE_EVENT_NEW = AuthorityEvent.__new__
_NATIVE_EVENT_VALIDATOR = AuthorityEvent.__pydantic_validator__


def native_method(instance, name, function):
    method = getattr(instance, name, None)
    return type(method) is MethodType and method.__self__ is instance and method.__func__ is function


def native_projection_dump(dump_function):
    return (dump_function is _NATIVE_DUMP and siming_contracts.dump_population_projections is _NATIVE_DUMP
        and siming_contracts._POPULATION_PROJECTIONS_ADAPTER is _NATIVE_ADAPTER
        and TypeAdapter.dump_python is _NATIVE_DUMP_METHOD
        and native_method(_NATIVE_ADAPTER, "dump_python", _NATIVE_DUMP_METHOD)
        and _NATIVE_ADAPTER.serializer is _NATIVE_SERIALIZER
        and type(_NATIVE_SERIALIZER) is SchemaSerializer and json.dumps is _NATIVE_JSON_DUMPS)


@dataclass(frozen=True, slots=True)
class PreparedPopulationFrame:
    projections_json: bytes
    projection_refs: tuple[str, ...]

    def read_set(self, cadence, projections):
        ordered = tuple(sorted(projections, key=lambda item: item.ref))
        refs = tuple(item.ref for item in ordered)
        if refs != self.projection_refs:
            return PopulationReadSet.from_inputs(cadence, projections)
        cadence_json = json.dumps(cadence.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        encoded = b'{"cadence":' + cadence_json + b',"projections":' + self.projections_json + b'}'
        return PopulationReadSet.model_construct(cadence=cadence, projections=ordered,
            read_set_digest="sha256:" + hashlib.sha256(encoded).hexdigest())


@dataclass
class _PublicationCapture:
    event: object = None
    rows: object = None
    native_dump: bool = False
    native_constructor: bool = False


_PUBLICATION_CAPTURE = ContextVar("population_publication_capture", default=None)


@contextmanager
def capture_publication():
    capture = _PublicationCapture()
    token = _PUBLICATION_CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _PUBLICATION_CAPTURE.reset(token)


def dump_publication_projections(projections, *, dump_function):
    native_dump = native_projection_dump(dump_function)
    rows = dump_function(projections)
    capture = _PUBLICATION_CAPTURE.get()
    if capture is not None:
        capture.rows = rows
        capture.native_dump = native_dump and native_projection_dump(dump_function)
    return rows


def record_projection_origin(event):
    capture = _PUBLICATION_CAPTURE.get()
    if (capture is not None and capture.native_dump and capture.native_constructor
            and event.payload.get("population_projections") is capture.rows):
        capture.event = event


def construct_publication_event(*, event_factory, **values):
    def native_constructor():
        return (event_factory is _NATIVE_EVENT and event_factory.__init__ is _NATIVE_EVENT_INIT
            and event_factory.__new__ is _NATIVE_EVENT_NEW
            and event_factory.__pydantic_validator__ is _NATIVE_EVENT_VALIDATOR)

    # 在实际构造调用前留存资格；回调恢复原绑定也不能补签来源。
    native = native_constructor()
    event = event_factory(**values)
    capture = _PUBLICATION_CAPTURE.get()
    if capture is not None:
        capture.native_constructor = native and native_constructor()
    return event


def encode_captured_projections(event, capture):
    rows = event.payload["population_projections"]
    # 先执行原发布编码，资格不足不能改变其异常或摘要。
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if capture.event is not event or capture.rows is not rows or type(rows) is not list:
        return digest, None
    refs = []
    for row in rows:
        if (type(row) is not dict or set(row) != {"ref", "scope", "revision_vector", "payload"}
                or type(row["ref"]) is not str or not row["ref"]
                or type(row["scope"]) is not str or not row["scope"]
                or type(row["revision_vector"]) is not dict or type(row["payload"]) is not dict
                or any(type(value) is not int or value < 0 for value in row["revision_vector"].values())):
            return digest, None
        refs.append(row["ref"])
    if refs != sorted(refs) or len(set(refs)) != len(refs):
        return digest, None
    return digest, PreparedPopulationFrame(encoded, tuple(refs))


@dataclass
class _ReadSetFrame:
    event: object
    frame: PreparedPopulationFrame | None
    consumed: bool = False
    ingress_snapshot: bytes | None = None
    ingress_consumed: bool = False


_READ_SET_FRAME = ContextVar("population_read_set_frame", default=None)


@contextmanager
def population_frame_scope(event, frame, *, ingress_snapshot=None):
    current = _ReadSetFrame(event, frame, ingress_snapshot=ingress_snapshot)
    token = _READ_SET_FRAME.set(current)
    try:
        yield
    finally:
        # 复制的 context 共享此记录；退出回调就撤销借用并释放完整帧和事件。
        current.consumed = True
        current.event = None
        current.frame = None
        current.ingress_snapshot = None
        current.ingress_consumed = True
        _READ_SET_FRAME.reset(token)


def take_population_ingress_snapshot(event):
    current = _READ_SET_FRAME.get()
    if current is None or current.event is not event or current.ingress_consumed:
        return None
    current.ingress_consumed = True
    return current.ingress_snapshot


def discard_frame_for_changed_parser(event, parser):
    current = _READ_SET_FRAME.get()
    if (current is not None and current.event is event
            and getattr(parser, "__func__", None) is not _NATIVE_CADENCE_PARSER):
        current.consumed = True


def take_population_frame(event):
    current = _READ_SET_FRAME.get()
    if current is None or current.event is not event or current.consumed:
        return None
    # 只供本次 builder；后续 finish/output 回调和嵌套发布不能借用。
    current.consumed = True
    if (getattr(PopulationReadSet.from_inputs, "__func__", None) is not _NATIVE_READ_SET_BUILDER
            or not native_projection_dump(siming_contracts.dump_population_projections)):
        return None
    return current.frame


def unadjusted_population_event(event):
    if any(key in event.payload for key in ("population_owner_receipt", "population_world_plan", "world_plan")):
        return False
    rows = event.payload.get("population_projections")
    if type(rows) is not list:
        return False
    return all(type(row) is dict and not (row.get("ref") in {"world_mode", "world-mode", "world_mode_projection"}
        and any(key in row.get("payload", {}) for key in ("population_world_plan", "world_plan", "plan"))) for row in rows)
