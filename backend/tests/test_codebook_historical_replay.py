from test_codebook_authorized_expansion import codebook_case


def test_expired_normal_grant_does_not_block_separate_authorized_history(codebook_case):
    case = codebook_case
    denied, receipt = case.service.read(case.request(at_tick=101), entry=case.entry)
    assert denied == {} and receipt.status == "expired"
    case.append_schedule("second")
    case.audit_grant = True
    content, receipt = case.service.read(case.request(at_tick=101, purpose="history_audit", requested_level="L2"),
        entry=case.entry)
    assert receipt.status == "granted" and receipt.source_revision == "4"
    assert receipt.policy_revision == "audit:2"
    assert len(content["work_orders"]) == 1 and content["work_orders"][0]["work_order_ref"] == "work:first"


def test_history_missing_does_not_return_current_source(codebook_case):
    case = codebook_case
    case.append_schedule("second")
    case.audit_grant = True
    case.history = None
    before = case.store.export_snapshot()
    content, receipt = case.service.read(case.request(at_tick=101, purpose="history_audit"), entry=case.entry)
    assert content == {} and receipt.status == "replay_input_unavailable"
    assert case.store.export_snapshot() == before


def test_history_requires_current_audit_authorization(codebook_case):
    case = codebook_case
    content, receipt = case.service.read(case.request(purpose="history_audit"), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and case.source_calls == 0
    case.audit_grant = True
    case.revoked = True
    content, receipt = case.service.read(case.request(purpose="history_audit"), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied" and case.source_calls == 0


def test_audit_grant_cannot_revive_normal_runtime_read(codebook_case):
    case = codebook_case
    case.audit_grant = True
    content, receipt = case.service.read(case.request(at_tick=101), entry=case.entry)
    assert content == {} and receipt.status == "permission_denied"


def test_expired_or_not_yet_valid_audit_grant_is_denied(codebook_case):
    case = codebook_case
    case.audit_grant = True
    case.policy["issued_at"] = 20
    for tick in (10, 200):
        content, receipt = case.service.read(case.request(at_tick=tick, purpose="history_audit"), entry=case.entry)
        assert content == {} and receipt.status == "expired"
