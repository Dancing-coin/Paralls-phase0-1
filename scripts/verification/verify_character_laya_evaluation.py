"""Fail-closed preflight and offline scoring for the four-role Laya evaluation.

This module deliberately does not call Laya.  It verifies source pins and the
evaluation contract, and reports missing runtime inputs instead of turning an
empty split or denominator into a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.character_agent.profile import CharacterDossierLoader
from app.character_agent.profile.models import CharacterProfile
from app.character_agent.profile.dossier_models import CharacterDossier
from pydantic import ValidationError


PROVIDER_REVISION = "laya:68804629e8ccd9d616d48a40e87de9fabbeae069:1720e3e3357cfe1e281542e223f8273b0890ca34"
WEIGHT_SHA256 = "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
SOURCE_PINS = (
    ("assets/characters/profiles/char_a.yaml", "8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463"),
    ("assets/characters/profiles/char_b.yaml", "98b4386dbcdb90d466c698426f14fc951e22cf244021ec5f1b7c6d7e488065bc"),
    ("assets/characters/profiles/char_c.yaml", "e30497f952b6c2c3fa780271cbf4c8f07030bceb289ed5790d7e9166ae168ce7"),
    ("assets/characters/dossiers/char_a.yaml", "55e76f6ffcd698d4fe427181c115d90ae99abf9ce897df5a2de38ad9644a5db2"),
    ("assets/characters/dossiers/char_b.yaml", "8e96be37e92f562175a4c113e55fe7b6c6c31bf4add38414e287fa073b1739a2"),
    ("backend/app/character_agent/profile/dossier_loader.py", "618eee434fcbc32be07fd3c0d90a46758dd474e13abf8f2ab034f8318d79a17f"),
    ("backend/app/character_agent/profile/loader.py", "06e6a608bbe7aafc5c2b1eda2b7d1bec23f00c85f49377c51b1ec658ed045e99"),
    ("backend/app/character_agent/gateway/laya_provider.py", "34e11611c20f4794d16044ca7ec9ae9e5b5f950338e876c2dd126be33897bde7"),
    ("backend/tests/fixtures/character_evaluation/char_d_authored/profile.yaml", "b2306f2fcfac63398cfd2196790cd506dfef6cf8fb107218ed1415bd8a4aff1e"),
    ("backend/tests/fixtures/character_evaluation/char_d_authored/dossier.yaml", "57c387a1dcd84f71fc6388a0985f5efb07e31f44fe71f31a5635e93e3a03545c"),
    ("backend/tests/fixtures/character_evaluation/char_d_authored/sources.yaml", "6aa449b653a5ccf89f97cb8bfd1cfdcb3a1d6a3b817e01823071e8f3839be0da"),
    ("docs/10月分析/角色/13-角色能力图谱、认知包络与动态算力设计.md", "85da495a16e46ef1f1e5b750f555b1b7233f92eb18abbf5123902ba23fa44c54"),
    ("backend/tests/fixtures/character_evaluation/four_role_lock_event/development_inputs.yaml", "7c43f597b2262649bee02396dbc022f31b6a0adab4d81dc8a766e4b3e6451baa"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source_pins(root: Path, pins: list[dict[str, str]] | tuple[tuple[str, str], ...]) -> list[str]:
    changed: list[str] = []
    for item in pins:
        path, expected = (item["path"], item["sha256"]) if isinstance(item, dict) else item
        candidate = root / path
        if not candidate.is_file() or _sha(candidate) != expected:
            changed.append(f"source_changed:{path}")
    return changed


def check_split_isolation(splits: dict[str, list[str]]) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for split, trajectories in splits.items():
        for trajectory in trajectories:
            previous = seen.get(str(trajectory))
            if previous and previous != split:
                errors.append(f"trajectory_leakage:{trajectory}")
            seen[str(trajectory)] = split
    return sorted(set(errors))


def score_records(records: list[dict[str, Any]], track: str) -> dict[str, Any]:
    rows = [r for r in records if r.get("track") == track]
    valid_inputs = [r for r in rows if r.get("input_valid") is True and r.get("question_valid") is True]
    legal = [r for r in valid_inputs if r.get("legal_target") is True]
    conditional = [r for r in legal if r.get("input_valid") and r.get("candidates_valid") and r.get("acceptable_presented")]
    hits = sum(
        bool(r.get("raw_choice_acceptable"))
        and not bool(r.get("fallback"))
        and not bool(r.get("slow_model"))
        and not bool(r.get("timeout"))
        for r in conditional
    )
    accuracy = hits / len(legal) if legal else None
    return {
        "status": "measured" if legal else "not_run",
        "denominator": len(legal),
        "conditional_denominator": len(conditional),
        "hits": hits,
        "accuracy": accuracy,
        "conditional_accuracy": hits / len(conditional) if conditional else None,
        "excluded_no_legal_target": sum(r.get("legal_target") is not True for r in rows),
        "excluded_input_or_question_error": len(rows) - len(valid_inputs),
        "fallback_count": sum(bool(r.get("fallback")) for r in rows),
        "slow_model_count": sum(bool(r.get("slow_model")) for r in rows),
        "timeout_count": sum(bool(r.get("timeout")) for r in rows),
        "latency_ms": [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))],
    }


def audit_fixture(repo: Path, fixture: Path) -> dict[str, Any]:
    blockers = check_source_pins(repo, SOURCE_PINS)
    manifest_path = fixture / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    actions = yaml.safe_load((fixture / "acceptable_actions.yaml").read_text(encoding="utf-8")) if (fixture / "acceptable_actions.yaml").is_file() else {}
    split_payload = yaml.safe_load((fixture / "splits.yaml").read_text(encoding="utf-8")) if (fixture / "splits.yaml").is_file() else {}
    declared_pins = manifest.get("source_pins", [])
    required = {(path, sha) for path, sha in SOURCE_PINS}
    declared = {(p.get("path"), p.get("sha256")) for p in declared_pins if isinstance(p, dict)}
    if not required <= declared:
        blockers.append("source_pins_incomplete")
    blockers.extend(check_source_pins(repo, [p for p in declared_pins if isinstance(p, dict) and "path" in p and "sha256" in p]))
    d_root = repo / "backend/tests/fixtures/character_evaluation/char_d_authored"
    for name, model in (("profile", CharacterProfile), ("dossier", CharacterDossier)):
        path = d_root / f"{name}.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
        try:
            model.model_validate(raw)
        except ValidationError:
            blockers.append(f"char_d_{name}_schema_unresolved")
    actors_loaded = []
    for actor in ("char_a", "char_b", "char_c"):
        root = repo / "assets/characters" / ("profiles" if actor == "char_c" else "dossiers")
        try:
            CharacterDossierLoader(root).load(actor)
        except (OSError, ValueError):
            blockers.append(f"actor_source_unloadable:{actor}")
        else:
            actors_loaded.append(actor)
    if actions.get("status") != "approved":
        blockers.append("acceptable_actions_unreviewed")
    if manifest.get("provider_revision") != PROVIDER_REVISION or manifest.get("checkpoint_weight_sha256") != WEIGHT_SHA256:
        blockers.append("checkpoint_unverified")
    if manifest.get("policy_revision") in {None, "", "policy:unfrozen"}:
        blockers.append("policy_unfrozen")
    for gate in ("policy", "questions", "candidates", "thresholds", "calibration_method"):
        if manifest.get("freeze", {}).get(gate) is not True:
            blockers.append(f"unfrozen:{gate}")
    if not isinstance(manifest.get("quality_thresholds"), dict) or not manifest["quality_thresholds"]:
        blockers.append("quality_thresholds_missing")
    if not manifest.get("calibration_method"):
        blockers.append("calibration_method_missing")
    tracks = manifest.get("tracks", {})
    if tracks.get("base_selection", {}).get("controlled_error") is not False:
        blockers.append("base_selection_controlled_error_not_disabled")
    performance = tracks.get("character_performance", {})
    if performance.get("controlled_error") is not True or not isinstance(performance.get("seed"), int):
        blockers.append("performance_seed_or_error_policy_missing")
    development_path = fixture / "development_inputs.yaml"
    development = yaml.safe_load(development_path.read_text(encoding="utf-8")) if development_path.is_file() else {}
    for field in ("frozen_mind_frame", "private_projection", "dynamic_state", "complete_u", "controlled_p", "acceptable_action_set"):
        if not development.get(field):
            blockers.append(f"development_missing:{field}")
    if development.get("target_state", {}).get("legality") != "legal":
        blockers.append("development_no_legal_target")
    splits = split_payload.get("splits", {}) if isinstance(split_payload, dict) else {}
    if not isinstance(splits, dict):
        splits = {}
    leakage = check_split_isolation({str(k): list(v or []) for k, v in splits.items() if isinstance(v, list)})
    blockers.extend(leakage)
    for required in ("calibration", "final", "independent_holdout"):
        if not splits.get(required):
            blockers.append(f"split_empty:{required}")
    # This is a preflight, never a quality run. Passing source checks cannot
    # supply the development/calibration/final observations that do not exist.
    blockers.append("official_baseline_not_run")
    return {
        "status": "evaluation_blocked" if blockers else "evaluation_ready",
        "preflight": {
            # Development is an input-contract gate. It does not require a
            # final threshold revision; thresholds are outputs of development.
            # Schema parsing and input freezing are the development gate.  A
            # missing authored field is recorded as unavailable; it is not a
            # reason to demand a final threshold before development starts.
            "development_ready": not any(item in blockers for item in (
                "source_pins_incomplete", "source_changed:docs/10月分析/角色/13-角色能力图谱、认知包络与动态算力设计.md",
            )),
            "calibration_ready": False,
            "final_ready": False,
            "thresholds": "not_frozen",
            "calibration_blockers": ["development_not_run", "candidate_policy_not_frozen", "calibration_split_empty"],
            "final_blockers": ["calibration_not_run", "independent_holdout_split_empty", "final_labels_sealed"],
        },
        "source_status": "source_frozen" if not [b for b in blockers if b.startswith("source_changed:") or b == "source_pins_incomplete"] else "source_changed_or_incomplete",
        "loaded_actor_sources": actors_loaded,
        "char_d_runtime_admitted": False,
        "provider_revision": PROVIDER_REVISION,
        "checkpoint_weight_sha256": WEIGHT_SHA256,
        "provider_calls": 0,
        "final_labels_read": False,
        "fine_tuning": "not_assessable",
        "candidate_coverage": None,
        "role_differences": "not_measured",
        "calibration": {"status": "not_run", "sample_count": 0, "brier": None, "ece": None},
        "blockers": sorted(set(blockers)),
        "splits": {"development": "not_run", "calibration": "not_run", "final": "not_run", "independent_holdout": "not_run"},
        "tracks": {"base_selection": score_records([], "base_selection"), "character_performance": score_records([], "character_performance")},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("backend/tests/fixtures/character_evaluation/four_role_lock_event"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--export-evidence", type=Path)
    args = parser.parse_args()
    from run_context import output_root, run_scope
    repo = Path(__file__).resolve().parents[2]
    with run_scope(repo, export_to=args.export_evidence):
        report = audit_fixture(repo, args.fixture)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        output = args.output or output_root(repo) / "character-laya-evaluation-preflight.json"
        if not output.resolve().is_relative_to(output_root(repo).resolve()):
            parser.error("--output must be in the current Harness run scope; use --export-evidence for retention")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        raw_inputs = output_root(repo) / "inputs"
        raw_inputs.mkdir(parents=True, exist_ok=True)
        for name in ("manifest.yaml", "splits.yaml", "development_inputs.yaml", "acceptable_actions.yaml"):
            source = args.fixture / name
            if source.is_file():
                (raw_inputs / name).write_bytes(source.read_bytes())
        print(payload, end="")
    return 0 if report["status"] == "evaluation_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())

