from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphScope,
)
from app.models.siming_heavenly_memory import (
    ActorCognitionMemoryEntry,
    CausalTimelineMemoryEntry,
    ConvergenceStrategyMemoryEntry,
    InterventionOutcomeMemoryEntry,
    SimingContextRequest,
    SimingHeavenlyMemoryEntry,
    StorylineObligationMemoryEntry,
    WorldFactMemoryEntry,
)
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_projection import SimingStoryProjection
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from common import (
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


TEST_FILES = [
    "backend/tests/test_siming_heavenly_memory_models.py",
    "backend/tests/test_siming_six_domain_memory.py",
    "backend/tests/test_siming_context_compiler.py",
    "backend/tests/test_siming_story_projection.py",
]


def _result(
    result_id: str,
    title: str,
    proved: bool,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        room_id="room_demo",
        scene_id="scene_demo",
    )


def _provenance(ref: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=ref,
        causation_id=ref,
        correlation_id="corr:siming-six-domain-proof",
        producer_system="system_l6",
    )


def _entries() -> list[SimingHeavenlyMemoryEntry]:
    return [
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref="authority:letter:removed",
            evidence_refs=["visual:letter:removed"],
        ),
        CausalTimelineMemoryEntry(
            entry_id="cause:letter:removed",
            cause_ref="fact:letter:removed",
            effect_ref="story:N3",
            relation_type="CAUSED_BY",
        ),
        ActorCognitionMemoryEntry(
            entry_id="cognition:char_b:letter",
            actor_id="char_b",
            revision_vector={"event": "1", "observation": "1"},
            completeness="complete",
            supporting_memory_refs=["actor_memory_surface:char_b:observation:1"],
        ),
        StorylineObligationMemoryEntry(
            entry_id="obligation:O6",
            record_type="obligation",
            lifecycle="open",
            supporting_fact_refs=["fact:letter:removed"],
        ),
        InterventionOutcomeMemoryEntry(
            entry_id="outcome:letter:proposal",
            stage="proposal",
            correlation_id="corr:letter",
        ),
        ConvergenceStrategyMemoryEntry(
            entry_id="strategy:letter",
            reachable_attractor_refs=["attractor:aftermath"],
            open_obligation_refs=["obligation:O6"],
        ),
    ]


def _write(
    service: SimingHeavenlyMemoryService,
    scope: HeavenlyGraphScope,
    entry: SimingHeavenlyMemoryEntry,
    index: int,
) -> None:
    service.write_entry(
        scope=scope,
        entry=entry,
        validity=GraphValidity(valid_from=10),
        recorded_at=10,
        revision=1,
        supersedes_revision=None,
        provenance=_provenance(f"authority:{entry.entry_id}"),
        transaction_id=f"tx:siming:memory:{index}",
        idempotency_key=f"memory:siming:{entry.entry_id}:1",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "siming-six-domain-memory-pytest.log"
    pytest_result = run_command(
        [resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )
    scope = _scope()
    entries = _entries()

    with tempfile.TemporaryDirectory(dir=log_dir) as temporary_directory:
        sqlite_path = Path(temporary_directory) / "siming-heavenly.sqlite3"
        graph = SQLiteHeavenlyGraphAdapter(sqlite_path)
        service = SimingHeavenlyMemoryService(graph)
        for index, entry in enumerate(entries):
            _write(service, scope, entry, index)
        for index, state in enumerate(("heard", "not_heard"), start=len(entries)):
            _write(
                service,
                scope,
                WorldFactMemoryEntry(
                    entry_id=f"claim:bell:{state}",
                    world_anchor_id="obj_bell",
                    state_key="heard",
                    state_value=state,
                    authority_result_ref=f"authority:bell:{state}",
                ),
                index,
            )
        graph.close()

        reopened = SQLiteHeavenlyGraphAdapter(sqlite_path)
        restored = SimingHeavenlyMemoryService(reopened)
        domain_counts = {
            entry.domain: len(restored.list_domain(scope, entry.domain, valid_at=20))
            for entry in entries
        }
        request = SimingContextRequest(
            scope=scope,
            valid_at=20,
            recorded_at=20,
            seed_node_ids=[entry.entry_id for entry in entries],
            relevant_actor_ids=["char_b"],
        )
        first = SimingContextCompiler(reopened).compile(request)
        second = SimingContextCompiler(reopened).compile(request)
        projection = SimingStoryProjection().project(second)
        claims = {
            entry.entry_id
            for entry in restored.list_domain(scope, "world_fact", valid_at=20)
            if entry.entry_id.startswith("claim:bell:")
        }
        trace = {
            "domain_counts": domain_counts,
            "first_context_hash": first.context_hash,
            "second_context_hash": second.context_hash,
            "context_equal": first == second,
            "claim_ids": sorted(claims),
            "projection": {
                "read_model_basis": projection.read_model.derived_from_snapshot_ref,
                "environment_authority": projection.state_tree.environment.authority,
                "character_authority": projection.state_tree.character.authority,
                "storyline_owner": projection.state_tree.storyline.owner_system,
                "storyline_authority": projection.state_tree.storyline.authority,
            },
        }
        reopened.close()

    trace_path = log_dir / "siming-six-domain-memory-trace.json"
    write_json(trace_path, trace)
    six_domains_present = all(count >= 1 for count in domain_counts.values())
    restart_recall = domain_counts == {
        "world_fact": 3,
        "causal_timeline": 1,
        "actor_cognition": 1,
        "storyline_obligation": 1,
        "intervention_outcome": 1,
        "convergence_strategy": 1,
    }
    summary_free_rebuild = first == second and first.context_hash == second.context_hash
    conflicts_preserved = claims == {"claim:bell:heard", "claim:bell:not_heard"}
    projection_not_truth = (
        projection.read_model.derived_from_snapshot_ref == second.context_hash
        and projection.state_tree.environment.authority == "mirror"
        and projection.state_tree.character.authority == "mirror"
        and projection.state_tree.storyline.owner_system == "siming"
        and projection.state_tree.storyline.authority == "editable"
        and not hasattr(SimingStoryProjection(), "_graph")
    )
    results = [
        _result(
            "focused_pytest_pass",
            "Six-domain focused pytest suites pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "six_domains_present",
            "Every Siming heavenly memory domain is present",
            six_domains_present,
            [str(trace_path)],
        ),
        _result(
            "restart_recall",
            "SQLite restart restores every persisted memory domain",
            restart_recall,
            [str(trace_path)],
        ),
        _result(
            "summary_free_rebuild",
            "Fresh compilers rebuild the same graph context without summaries",
            summary_free_rebuild,
            [str(trace_path)],
        ),
        _result(
            "conflicts_preserved",
            "Conflicting world claims remain distinct graph entries",
            conflicts_preserved,
            [str(trace_path)],
        ),
        _result(
            "projection_not_truth",
            "Compatibility projection remains graph-derived and non-authoritative",
            projection_not_truth,
            [str(trace_path)],
        ),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_siming_six_domain_memory_passed": overall,
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)},
    }
    json_path = log_dir / "siming-six-domain-memory-report.json"
    markdown_path = log_dir / "siming-six-domain-memory-report.md"
    write_json(json_path, report)
    write_markdown(
        markdown_path,
        "Siming Six-Domain Memory Verification Report",
        report,
        "overall_siming_six_domain_memory_passed",
    )
    print(f"siming_six_domain_memory_report_json={json_path}")
    print(f"siming_six_domain_memory_report_md={markdown_path}")
    print(f"overall_siming_six_domain_memory_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
