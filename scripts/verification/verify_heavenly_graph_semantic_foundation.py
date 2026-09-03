from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown

sys.path.insert(0, str(repo_root() / "backend"))

from app.models.siming_heavenly_graph import (
    GraphBranchForkRequest,
    GraphCorrectionRequest,
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    NodeLookupQuery,
)
from app.services.heavenly_graph_consistency import HeavenlyGraphConsistencyAudit
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphRevisionConflict
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


RESULT_IDS = (
    "focused_contract_tests",
    "adapter_parity",
    "semantic_metadata",
    "scope_denial",
    "bounded_results",
    "stale_write_rejection",
    "correction_chain",
    "branch_isolation",
    "replay_digest",
)

GRAPH_TEST_FILES = (
    "backend/tests/heavenly_graph_contract.py",
    "backend/tests/test_sqlite_heavenly_graph_contract.py",
    "backend/tests/test_heavenly_graph_semantics.py",
    "backend/tests/test_heavenly_graph_semantic_queries.py",
    "backend/tests/test_heavenly_graph_branch_lifecycle.py",
    "backend/tests/test_heavenly_graph_consistency.py",
    "backend/tests/test_heavenly_graph_endpoint_scopes.py",
)


def _scope(branch: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:verify",
        session_id="session:verify",
        story_branch_id=branch,
        room_id="room:verify",
        scene_id="scene:verify",
    )


def _provenance(source_ref: str = "authority:event:verify:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:verify",
        correlation_id="correlation:verify",
        producer_system="verifier",
        evidence_refs=[source_ref],
    )


def _metadata(*, policy: str = "policy:verify", source_ref: str = "authority:event:verify:1", scope_digest: str = "scope:verify", visibility: str = "public", derivation: str = "authority") -> GraphSemanticMetadata:
    return GraphSemanticMetadata(
        record_kind="fact",
        visibility_scope=visibility,  # type: ignore[arg-type]
        derivation_kind=derivation,  # type: ignore[arg-type]
        source_event_refs=(source_ref,),
        source_revision_vector=GraphRevisionVector(source_revision=1),
        policy_revision=policy,
        scope_digest=scope_digest,
    )


def _node(
    node_id: str,
    scope: HeavenlyGraphScope,
    *,
    state: str = "seed",
    revision: int = 1,
    supersedes_revision: int | None = None,
    recorded_at: int = 10,
    source_ref: str = "authority:event:verify:1",
    metadata: GraphSemanticMetadata | None = None,
    node_type: str = "world_fact",
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=scope,
        validity=GraphValidity(valid_from=0),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": state},
        provenance=_provenance(source_ref),
        semantic_metadata=metadata or _metadata(source_ref=source_ref),
    )


def _batch(scope: HeavenlyGraphScope, key: str, nodes: list[HeavenlyGraphNode]) -> HeavenlyGraphWriteBatch:
    return HeavenlyGraphWriteBatch(
        transaction_id=f"graph_tx:verify:{key}",
        idempotency_key=f"authority:event:verify:{key}",
        scope=scope,
        nodes=nodes,
    )


def _context(scope: HeavenlyGraphScope, *, principal: str = "reader:verify", scopes: tuple[str, ...] = ("public",), policy: str = "policy:verify") -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal=principal,
        allowed_visibility_scopes=scopes,  # type: ignore[arg-type]
        world_id=scope.world_id,
        session_id=scope.session_id,
        story_branch_id=scope.story_branch_id,
        valid_at=20,
        recorded_at=20,
        policy_revision=policy,
    )


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _adapter_checks(graph: Any) -> dict[str, bool]:
    scope = _scope()
    context = _context(scope)
    checks: dict[str, bool] = {}
    seed = _node("fact:verify", scope)
    seed_batch = _batch(scope, "seed", [seed])
    graph.write_batch(seed_batch)
    try:
        query = NodeLookupQuery(context=context, scope=scope, node_ids=[seed.node_id], limit=10)
        stored = graph.get_node(node_id=seed.node_id, scope=scope, valid_at=20)
        checks["semantic_metadata"] = bool(
            stored
            and stored.semantic_metadata.policy_revision == "policy:verify"
            and stored.semantic_metadata.source_event_refs == ("authority:event:verify:1",)
            and stored.semantic_metadata.scope_digest == "scope:verify"
        )

        private_scope = scope.model_copy(update={"graph_namespace": "actor_private", "owner_actor_id": "char:b"})
        private = _node(
            "memory:private",
            private_scope,
            metadata=_metadata(visibility="actor_private"),
            node_type="actor_memory_ref",
        )
        graph.write_batch(_batch(private_scope, "private", [private]))
        denied = graph.query_semantic(
            NodeLookupQuery(
                context=_context(private_scope, principal="reader:char:a", scopes=("actor_private",)),
                scope=private_scope,
                node_ids=[private.node_id],
            )
        )
        checks["scope_denial"] = denied.nodes == [] and denied.incomplete_reason == "visibility_denied"

        chain_scope = private_scope
        chain_nodes = [
            _node(
                f"fact:bound:{i}",
                chain_scope,
                metadata=_metadata(visibility="actor_private"),
                node_type="actor_memory_ref",
            )
            for i in range(4)
        ]
        graph.write_batch(_batch(chain_scope, "bounded", chain_nodes))
        bounded = graph.query_subgraph(
            scope=chain_scope,
            seed_node_ids=[chain_nodes[0].node_id],
            relation_types=[],
            direction="outgoing",
            max_depth=1,
            valid_at=20,
            recorded_at=20,
            node_limit=2,
            relation_limit=2,
        )
        # A direct node query also proves the semantic facade's hard limit.
        bounded_query = graph.query_semantic(
            NodeLookupQuery(
                context=_context(chain_scope, principal="reader:char:b", scopes=("actor_private",)),
                scope=chain_scope,
                limit=2,
            )
        )
        checks["bounded_results"] = bounded.truncated is False and len(bounded_query.nodes) <= 2 and bounded_query.truncated is True

        captured = graph.scope_revision_vector(scope)
        independent = _node("fact:independent", scope, source_ref="authority:event:verify:independent")
        graph.write_batch(_batch(scope, "independent", [independent]))
        correction = GraphCorrectionRequest(
            target_kind="node",
            target_id=seed.node_id,
            target_revision=1,
            correction_kind="corrected",
            source_refs=["authority:event:verify:correction"],
            semantic_metadata=_metadata(),
            expected_revision_vector=captured,
            scope=scope,
        )
        try:
            graph.correct(correction)
            checks["stale_write_rejection"] = False
        except HeavenlyGraphRevisionConflict:
            checks["stale_write_rejection"] = graph.get_node(node_id=seed.node_id, scope=scope, valid_at=20).revision == 1  # type: ignore[union-attr]

        fresh = graph.scope_revision_vector(scope)
        applied = graph.correct(correction.model_copy(update={"expected_revision_vector": fresh}))
        current = graph.get_node(node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=20)
        history = graph.get_node(node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=10)
        audit = HeavenlyGraphConsistencyAudit(graph).audit(scope, context)
        checks["correction_chain"] = bool(
            applied.applied
            and current
            and history
            and current.revision == 2
            and current.supersedes_revision == 1
            and current.semantic_metadata.derivation_kind == "correction"
            and history.revision == 1
            and audit.errors == []
        )

        production = _scope("branch:main")
        branch_seed = _node("fact:branch-seed", production)
        graph.write_batch(_batch(production, "branch-seed", [branch_seed]))
        fork = graph.fork_branch(
            GraphBranchForkRequest(
                source_scope=production,
                target_branch_id="branch:preview",
                fork_valid_at=20,
                fork_recorded_at=20,
                source_revision_vector=graph.scope_revision_vector(production),
            )
        )
        branch = _scope("branch:preview")
        branch_only = _node("fact:branch-only", branch)
        graph.write_batch(_batch(branch, "branch-only", [branch_only]))
        contamination_denied = False
        try:
            graph.write_batch(_batch(_scope("branch:unforked"), "unforked", [_node("fact:unforked", _scope("branch:unforked"))]))
        except ValueError:
            contamination_denied = True
        checks["branch_isolation"] = bool(
            fork.applied
            and graph.get_node(node_id=branch_only.node_id, scope=production, valid_at=20) is None
            and graph.get_node(node_id=branch_only.node_id, scope=branch, valid_at=20) is not None
            and contamination_denied
        )

        checkpoint = graph.create_checkpoint(checkpoint_id="checkpoint:verify", scope=production, valid_at=20, recorded_at=20)
        tail_node = _node(
            branch_seed.node_id,
            production,
            state="tail",
            revision=2,
            supersedes_revision=1,
            recorded_at=30,
            source_ref="authority:event:verify:tail",
            metadata=_metadata(source_ref="authority:event:verify:tail"),
        )
        tail = _batch(production, "tail", [tail_node])
        graph.write_batch(tail)
        full = graph.create_checkpoint(checkpoint_id="checkpoint:verify:full", scope=production, valid_at=20, recorded_at=30)
        replayed = graph.replay_from_checkpoint(checkpoint.checkpoint_ref, [tail])
        checks["replay_digest"] = bool(
            replayed.nodes == graph.read_checkpoint(full.checkpoint_ref).nodes
            and replayed.relations == graph.read_checkpoint(full.checkpoint_ref).relations
            and replayed.checkpoint.replay_digest == graph.read_checkpoint(full.checkpoint_ref).checkpoint.replay_digest
        )
    except Exception:
        return {check_id: False for check_id in RESULT_IDS[1:]}
    return checks


def collect_graph_evidence(output_root: Path) -> dict[str, Any]:
    """Exercise both graph adapters and return deterministic proof flags."""
    output_root.mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix="heavenly-graph-verify-", dir=output_root)
    temp_root = Path(temp.name)
    database = temp_root / "heavenly-graph.sqlite3"
    memory = InMemoryHeavenlyGraphAdapter()
    sqlite = SQLiteHeavenlyGraphAdapter(database)
    try:
        memory_checks = _adapter_checks(memory)
        sqlite_checks = _adapter_checks(sqlite)
        parity_scope = _scope()
        parity_context = _context(parity_scope)
        parity_query = NodeLookupQuery(
            context=parity_context,
            scope=parity_scope,
            node_ids=["fact:verify"],
            limit=10,
        )
        parity = (
            memory.query_semantic(parity_query) == sqlite.query_semantic(parity_query)
            and HeavenlyGraphConsistencyAudit(memory).audit(parity_scope, parity_context)
            == HeavenlyGraphConsistencyAudit(sqlite).audit(parity_scope, parity_context)
        )
        memory_checks["adapter_parity"] = parity
        sqlite_checks["adapter_parity"] = parity
    finally:
        sqlite.close()
    checks = {
        check_id: memory_checks.get(check_id, False)
        and sqlite_checks.get(check_id, False)
        for check_id in RESULT_IDS[1:]
    }
    return {
        "checks": checks,
        "adapter_checks": {"in_memory": memory_checks, "sqlite": sqlite_checks},
        "sqlite_database": str(database),
        "temporary_directory": str(temp_root),
        "_temporary_directory": temp,
    }


def evaluate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = {
        check_id: bool(evidence.get(check_id, evidence.get("checks", {}).get(check_id, False)))
        for check_id in RESULT_IDS
        if check_id != "focused_contract_tests"
    }
    return {"overall": all(checks.values()), "checks": checks}


def run_verification(output_root: Path, *, focused_exit_code: int = 0) -> dict[str, object]:
    output_root.mkdir(parents=True, exist_ok=True)
    evidence = collect_graph_evidence(output_root)
    try:
        evaluation = evaluate_evidence(evidence)
        results = [
            _result(check_id, check_id.replace("_", " ").title(), bool(evaluation["checks"].get(check_id, False)), ["verifier-owned-temporary-database"])
            for check_id in RESULT_IDS[1:]
        ]
        results.insert(0, _result("focused_contract_tests", "Focused Heavenly Graph contract suites pass", focused_exit_code == 0, ["focused-graph-contract-pytest"], f"exit_code={focused_exit_code}"))
        return {
            "overall_heavenly_graph_semantic_foundation_passed": bool(evaluation["overall"]) and focused_exit_code == 0,
            "results": results,
            "artifacts": {
                "sqlite_database": "verifier-owned-temporary-database",
                "temporary_directory": "verifier-owned-temporary-directory",
                "pytest_log": "focused-graph-contract-pytest",
            },
        }
    finally:
        evidence["_temporary_directory"].cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "heavenly-graph-semantic-foundation-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *GRAPH_TEST_FILES], project_root, pytest_log)
    report = run_verification(log_dir, focused_exit_code=pytest_result.returncode)
    json_path = log_dir / "heavenly-graph-semantic-foundation-report.json"
    md_path = log_dir / "heavenly-graph-semantic-foundation-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Heavenly Graph Semantic Foundation Verification Report", report, "overall_heavenly_graph_semantic_foundation_passed")
    overall = bool(report["overall_heavenly_graph_semantic_foundation_passed"])
    print(f"heavenly_graph_semantic_foundation_report_json={json_path}")
    print(f"heavenly_graph_semantic_foundation_report_md={md_path}")
    print(f"overall_heavenly_graph_semantic_foundation_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
