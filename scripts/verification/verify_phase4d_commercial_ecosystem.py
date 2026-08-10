from __future__ import annotations
import sys
from common import repo_root
sys.path.insert(0, str(repo_root() / "backend"))
from app.gameplay.phase4_commerce import CommercialEcosystemScenario
from verify_phase4_common import run_focused, write_report

ok, log = run_focused("backend/tests/test_phase4_commercial_ecosystem.py")
result = CommercialEcosystemScenario().run()
raise SystemExit(write_report("phase4d-commercial-ecosystem", {"overall_passed": ok and result.replay_hash == result.checkpoint_tail_hash and result.customer_demand.committed, "focused_log": log, "policy_quote_digest": {"policy": result.public_view["policy_digest"], "quote": result.public_view["quote_digest"]}, "atomic_receipts": {"competition": result.competition.receipt.transaction_id if result.competition.receipt else None, "customer_demand": result.customer_demand.receipt.transaction_id if result.customer_demand.receipt else None, "procurement": result.procurement.receipt.transaction_id if result.procurement.receipt else None, "credit": result.credit.receipt.transaction_id if result.credit.receipt else None}, "revision_vectors": {"competition": result.competition.revision_vector, "customer_demand": result.customer_demand.revision_vector, "procurement": result.procurement.revision_vector, "credit": result.credit.revision_vector}, "replay_hash": result.replay_hash, "checkpoint_tail_hash": result.checkpoint_tail_hash, "public_view": result.public_view, "no_new_owner_audit": result.no_new_owner_audit, "failure_zero_write": result.structured_reject.zero_write}))
