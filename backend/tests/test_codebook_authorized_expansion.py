from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.models.codebook import CodebookEntry, CodebookReadRequest
from app.services.codebook import CodebookReadService, codebook_digest, expand_codebook


class CodebookCase:
    """真实领域Owner来源；读取授权由服务装配端持有。"""

    def __init__(self, directory):
        self.store = DurableGameplayEventStore(directory / "codebook-source.sqlite3")
        self.owner = OrganizationAuthority(store=self.store)
        self.source_calls = 0
        self.history = None
        self.audit_grant = False
        self.revoked = False
        self.append_schedule("first")
        self.history = self.store.export_snapshot()
        projection = self.projection(self.store)
        self.entry = CodebookEntry(code_ref="code:schedule:char_a", source_ref="gameplay:organization:org:bakery",
            source_type="organization_schedule", source_revision="4", content_digest=codebook_digest(projection),
            scope="actor:self", visibility="actor_private", reader_roles=("subject",),
            purpose_policy_ref="policy:schedule-read", codec_version="codebook:v1",
            safe_summary={"task": "日常班表"}, expansion_levels=("L0", "L1", "L2"), expiry=100)
        self.policy = dict(policy_ref="policy:schedule-read", policy_revision="1", code_ref=self.entry.code_ref,
            summary_digest=codebook_digest(self.entry.safe_summary), reader_ref="character:char_a",
            reader_roles=("subject",), purposes=("simulation",), scopes=("actor:self",),
            level_fields={"L0": ("task",), "L1": ("organization_ref",), "L2": ("organization_ref", "work_orders")},
            issued_at=0, expiry=100, historical=False, source_ref=self.entry.source_ref,
            source_type=self.entry.source_type, source_revision="4", source_digest=self.entry.content_digest)
        self.service = CodebookReadService(policy_reader=self.read_policy, source_reader=self.read_source)

    def append_schedule(self, suffix):
        result = self.owner.record_schedule(command_id="schedule:" + suffix, organization_ref="org:bakery",
            recipient_ref="character:char_a", membership_ref="membership:" + suffix,
            assignment_ref="assignment:" + suffix, role="worker", shift_ref="shift:" + suffix,
            operating_window_ref="window:" + suffix, work_order_ref="work:" + suffix,
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope="organization:summary")
        assert result.committed

    @staticmethod
    def projection(store):
        return OrganizationAuthority(store=store).schedule_view_for(organization_ref="org:bakery",
            recipient_ref="character:char_a", observed_at="1970-01-01T00:00:00Z").model_dump(mode="json")

    def read_policy(self, request, entry):
        policy = deepcopy(self.policy)
        if self.revoked:
            policy["reader_roles"] = ()
        if self.audit_grant:
            policy.update(purposes=("history_audit",), historical=True, expiry=200, policy_revision="audit:2")
        else:
            projection = self.projection(self.store)
            policy.update(source_revision=str(self.store.get_stream_head(entry.source_ref)),
                source_digest=codebook_digest(projection))
        return policy

    def read_source(self, request, entry):
        self.source_calls += 1
        if request.purpose == "history_audit":
            return self.projection(GameplayEventStore.from_snapshot(self.history)) if self.history is not None else None
        return self.projection(self.store)

    def request(self, **updates):
        values = dict(reader_ref="character:char_a", code_ref=self.entry.code_ref, requested_level="L1",
            purpose="simulation", scope="actor:self", expected_revision=self.entry.source_revision,
            expected_digest=self.entry.content_digest, at_tick=10)
        values.update(updates)
        return CodebookReadRequest(**values)


@pytest.fixture
def codebook_case(tmp_path):
    case = CodebookCase(tmp_path)
    yield case
    case.store.close()


@pytest.mark.parametrize("level,fields", [("L0", {"task"}), ("L1", {"organization_ref"}),
    ("L2", {"organization_ref", "work_orders"})])
def test_granted_levels_only_return_declared_fields(codebook_case, level, fields):
    case = codebook_case
    before = case.store.export_snapshot()
    content, receipt = case.service.read(case.request(requested_level=level), entry=case.entry)
    assert receipt.status == "granted"
    assert set(content) == fields and set(receipt.granted_fields) == fields
    assert "work_orders" not in receipt.model_dump()
    assert case.store.export_snapshot() == before


@pytest.mark.parametrize("changes,status", [({"reader_ref": "character:char_b"}, "permission_denied"),
    ({"code_ref": "code:other"}, "permission_denied"), ({"purpose": "unapproved"}, "permission_denied"),
    ({"scope": "public"}, "permission_denied"), ({"at_tick": 100}, "expired"),
    ({"expected_revision": "3"}, "stale_input"), ({"expected_digest": "sha256:" + "0" * 64}, "digest_mismatch")])
def test_denied_reads_return_empty_content_without_reading_source(codebook_case, changes, status):
    case = codebook_case
    before = case.store.export_snapshot()
    content, receipt = case.service.read(case.request(**changes), entry=case.entry)
    assert content == {} and receipt.status == status and receipt.granted_fields == ()
    assert case.source_calls == 0 and case.store.export_snapshot() == before
    assert "work_orders" not in json.dumps(receipt.model_dump())


def test_current_authorization_revocation_applies_to_existing_entry(codebook_case):
    case = codebook_case
    case.revoked = True
    content, receipt = case.service.read(case.request(), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and case.source_calls == 0


def test_owner_source_revision_change_rejects_old_entry(codebook_case):
    case = codebook_case
    case.append_schedule("second")
    before = case.store.export_snapshot()
    content, receipt = case.service.read(case.request(), entry=case.entry)
    assert content == {} and receipt.status == "stale_input"
    assert case.source_calls == 0 and case.store.export_snapshot() == before


def test_output_nested_mutation_does_not_change_owner_or_entry(codebook_case):
    case = codebook_case
    content, receipt = case.service.read(case.request(requested_level="L2"), entry=case.entry)
    before = case.store.export_snapshot()
    content["work_orders"][0]["role"] = "changed"
    repeated, again = case.service.read(case.request(requested_level="L2"), entry=case.entry)
    assert repeated["work_orders"][0]["role"] == "worker" and again == receipt
    assert case.store.export_snapshot() == before
    with pytest.raises(TypeError):
        case.entry.safe_summary["task"] = "changed"


def test_projection_content_change_cannot_keep_old_digest(codebook_case):
    case = codebook_case
    projection = case.projection(case.store)
    projection["work_orders"][0]["role"] = "forged"
    content, receipt = expand_codebook(case.request(), entry=case.entry, source_projection=projection,
        current_policy=case.read_policy(case.request(), case.entry))
    assert content == {} and receipt.status == "digest_mismatch"


def test_public_reader_cannot_accept_a_caller_signed_policy(codebook_case):
    case = codebook_case
    with pytest.raises(TypeError):
        case.service.read(case.request(), entry=case.entry, current_policy=case.policy)


@pytest.mark.parametrize("changes", [{"extra": "untrusted"}, {"at_tick": True}, {"at_tick": -1},
    {"requested_level": "L3"}, {"expected_digest": "bad"}])
def test_request_rejects_undeclared_or_invalid_fields(codebook_case, changes):
    with pytest.raises(ValidationError):
        codebook_case.request(**changes)


def test_invalid_owner_policy_is_denied_without_content(codebook_case):
    case = codebook_case
    case.policy["extra"] = "untrusted"
    content, receipt = case.service.read(case.request(), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and case.source_calls == 0


def test_bypassed_frozen_request_is_revalidated(codebook_case):
    case = codebook_case
    request = case.request().model_copy(update={"at_tick": True})
    with pytest.raises(ValidationError):
        case.service.read(request, entry=case.entry)


def test_digest_and_delivered_content_use_one_source_snapshot(codebook_case):
    case = codebook_case
    original = case.projection(case.store)

    class ChangingProjection(dict):
        def items(self):
            values = deepcopy(original)
            if getattr(self, "read_once", False):
                values["work_orders"][0]["role"] = "forged"
            self.read_once = True
            return values.items()

    content, receipt = expand_codebook(case.request(requested_level="L2"), entry=case.entry,
        source_projection=ChangingProjection(original), current_policy=case.policy)
    assert receipt.status == "granted"
    assert content["work_orders"][0]["role"] == "worker"


def test_grant_revoked_during_source_read_does_not_return_content(codebook_case):
    case = codebook_case

    def read_then_revoke(request, entry):
        content = case.read_source(request, entry)
        case.revoked = True
        return content

    reader = CodebookReadService(policy_reader=case.read_policy, source_reader=read_then_revoke)
    content, receipt = reader.read(case.request(requested_level="L2"), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and receipt.granted_fields == ()


def test_safe_summary_mutation_cannot_keep_old_owner_pin(codebook_case):
    case = codebook_case
    entry = case.entry.model_copy(update={"safe_summary": {"task": "forged"}})
    content, receipt = case.service.read(case.request(requested_level="L0"), entry=entry)
    assert content == {} and receipt.status == "digest_mismatch" and case.source_calls == 0


def test_same_policy_revision_cannot_hide_changed_field_grant(codebook_case):
    case = codebook_case

    def read_then_restrict(request, entry):
        content = case.read_source(request, entry)
        case.policy["level_fields"]["L2"] = ("organization_ref",)
        return content

    reader = CodebookReadService(policy_reader=case.read_policy, source_reader=read_then_restrict)
    content, receipt = reader.read(case.request(requested_level="L2"), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and receipt.granted_fields == ()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_safe_summary_cannot_contain_non_finite_numbers(codebook_case, value):
    with pytest.raises(ValidationError):
        CodebookEntry.model_validate({**codebook_case.entry.model_dump(), "safe_summary": {"risk": value}})


def test_entry_json_roundtrip_keeps_frozen_summary(codebook_case):
    entry = codebook_case.entry
    restored = CodebookEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    with pytest.raises(TypeError):
        restored.safe_summary["task"] = "changed"


def test_revocation_during_snapshot_creation_is_checked_before_delivery(codebook_case):
    case = codebook_case
    original = case.projection(case.store)

    class RevokingProjection(dict):
        def items(self):
            case.revoked = True
            return original.items()

    reader = CodebookReadService(policy_reader=case.read_policy,
        source_reader=lambda request, entry: RevokingProjection(original))
    content, receipt = reader.read(case.request(requested_level="L2"), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and receipt.granted_fields == ()
