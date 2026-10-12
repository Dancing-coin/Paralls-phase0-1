from collections.abc import Mapping
import hashlib
import json
from typing import Callable

from pydantic import ValidationError

from app.models.codebook import CodebookEntry, CodebookReadPolicy, CodebookReadReceipt, CodebookReadRequest, _plain_json


def codebook_digest(value: Mapping[str, object]) -> str:
    body = json.dumps(_plain_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _authorize(request, entry, current_policy):
    # 接纳处重验，不能信model_copy/model_construct绕过的frozen对象。
    request = CodebookReadRequest.model_validate(request)
    entry = CodebookEntry.model_validate(entry)
    receipt = CodebookReadReceipt(reader_ref=request.reader_ref, code_ref=request.code_ref,
        source_revision=entry.source_revision, requested_level=request.requested_level, purpose=request.purpose,
        policy_revision="unavailable", issued_at=request.at_tick, expiry=entry.expiry, status="permission_denied")
    try:
        policy = CodebookReadPolicy.model_validate(current_policy)
    except ValidationError:
        return request, entry, None, receipt
    receipt = receipt.model_copy(update={"policy_revision": policy.policy_revision,
        "expiry": policy.expiry if policy.historical else min(entry.expiry, policy.expiry)})
    if (request.reader_ref != policy.reader_ref or request.code_ref != entry.code_ref
        or request.code_ref != policy.code_ref or request.purpose not in policy.purposes
        or request.scope != entry.scope or request.scope not in policy.scopes
        or entry.purpose_policy_ref != policy.policy_ref
        or not set(entry.reader_roles).intersection(policy.reader_roles)
        or request.requested_level not in entry.expansion_levels
        or request.requested_level not in policy.level_fields
        or policy.source_ref != entry.source_ref or policy.source_type != entry.source_type
        or policy.historical != (request.purpose == "history_audit")):
        return request, entry, None, receipt
    status = "granted"
    if request.at_tick < policy.issued_at or request.at_tick >= receipt.expiry:
        status = "expired"
    elif request.expected_revision != entry.source_revision or policy.source_revision != entry.source_revision:
        status = "stale_input"
    elif (request.expected_digest != entry.content_digest or policy.source_digest != entry.content_digest
        or codebook_digest(entry.safe_summary) != policy.summary_digest):
        status = "digest_mismatch"
    return request, entry, policy, receipt.model_copy(update={"status": status})


def _expand_authorized(request, entry, policy, receipt, source_projection):
    if receipt.status != "granted":
        return {}, receipt
    unavailable = "replay_input_unavailable" if policy.historical else "source_unavailable"
    if source_projection is None:
        return {}, receipt.model_copy(update={"status": unavailable})
    try:
        # 所有层级核对同一原始版本，L0不能借用旧来源或被篡改的摘要。
        snapshot = _plain_json(source_projection)
        if codebook_digest(snapshot) != entry.content_digest:
            return {}, receipt.model_copy(update={"status": "digest_mismatch"})
        source = _plain_json(entry.safe_summary) if request.requested_level == "L0" else snapshot
        fields = tuple(sorted(policy.level_fields[request.requested_level]))
        if any(field not in source for field in fields):
            return {}, receipt.model_copy(update={"status": unavailable})
        # JSON往返给消费者独立正文，entry和原Owner内容保持隔离。
        visible = json.loads(json.dumps({field: source[field] for field in fields}, allow_nan=False))
    except (TypeError, ValueError, RecursionError):
        return {}, receipt.model_copy(update={"status": "digest_mismatch"})
    return visible, receipt.model_copy(update={"granted_fields": fields})


def expand_codebook(request: CodebookReadRequest, *, entry: CodebookEntry,
    source_projection: Mapping[str, object] | None, current_policy: Mapping[str, object]
) -> tuple[Mapping[str, object], CodebookReadReceipt]:
    """纯过滤端口；policy/source必须由原Owner在同一读边界提供。"""
    request, entry, policy, receipt = _authorize(request, entry, current_policy)
    return _expand_authorized(request, entry, policy, receipt, source_projection)


class CodebookReadService:
    """由可信Owner装配的读取服务，公开请求不能传入授权或正文。"""

    def __init__(self, *,
        policy_reader: Callable[[CodebookReadRequest, CodebookEntry], Mapping[str, object]],
        source_reader: Callable[[CodebookReadRequest, CodebookEntry], Mapping[str, object] | None]):
        self._policy_reader = policy_reader
        self._source_reader = source_reader

    def read(self, request: CodebookReadRequest, *, entry: CodebookEntry
    ) -> tuple[Mapping[str, object], CodebookReadReceipt]:
        request = CodebookReadRequest.model_validate(request)
        entry = CodebookEntry.model_validate(entry)
        request, entry, policy, receipt = _authorize(request, entry, self._policy_reader(request, entry))
        if receipt.status != "granted":
            return {}, receipt
        source = self._source_reader(request, entry)
        content, result = _expand_authorized(request, entry, policy, receipt, source)
        if result.status != "granted":
            return content, result
        # 读取期间失权或授权内容变化均拒绝，不静默重pin或先返回敏感正文。
        try:
            current = CodebookReadPolicy.model_validate(self._policy_reader(request, entry))
        except ValidationError:
            current = None
        if current != policy:
            return {}, receipt.model_copy(update={"status": "permission_denied"})
        return content, result
