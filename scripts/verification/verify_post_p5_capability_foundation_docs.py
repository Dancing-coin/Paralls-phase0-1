from __future__ import annotations

from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


ROOT = "docs/superpowers"
FOUNDATION = "world-character-siming-authority-mainline/post-p5-capability-foundation"


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _missing(project_root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if not (project_root / path).exists()]


def evaluate_post_p5_capability_foundation_docs(project_root: Path) -> dict[str, object]:
    august_base = "docs/8月分析/P5后能力基础推进"
    spec_base = f"{ROOT}/specs/{FOUNDATION}"
    plan_base = f"{ROOT}/plans/{FOUNDATION}"
    required_documents = [
        *(f"{august_base}/{name}" for name in [
            "README.md", "01-F0实现证据与缺口基线.md", "02-F1A语义规则因果与调度门.md",
            "03-F1B社会知识隐私投影门.md", "04-F1C玩法包版本激活与闭源边界.md",
            "05-F2回放隐私零写入与审计门禁.md", "06-P6P7命名与顺序决策门.md",
            "07-F0八月分析逐文件覆盖台账.md", "f0-owner-map.md", "f0-gap-register.md",
            "f0-claim-ledger.md", "f0-evidence-manifest.md",
        ]),
        *(f"{spec_base}/{name}" for name in [
            "README.md", "2026-08-12-f0-implementation-evidence-and-gap-baseline-design.md",
            "2026-08-12-f1a-semantic-rule-and-causal-extension-gate-design.md",
            "2026-08-12-f1b-social-knowledge-and-privacy-projection-extension-gate-design.md",
            "2026-08-12-f1c-governed-package-revision-and-activation-contract-design.md",
            "2026-08-12-f2-harness-replay-privacy-and-zero-write-gates-design.md",
            "2026-08-12-dg-p6-p7-naming-and-order-decision-record.md",
        ]),
        *(f"{plan_base}/{name}" for name in [
            "README.md", "2026-08-12-f0-implementation-evidence-and-gap-baseline-implementation-plan.md",
            "2026-08-12-f1a-semantic-rule-and-causal-extension-gate-implementation-plan.md",
            "2026-08-12-f1b-social-knowledge-and-privacy-projection-extension-gate-implementation-plan.md",
            "2026-08-12-f1c-governed-package-revision-and-activation-contract-implementation-plan.md",
            "2026-08-12-f2-harness-replay-privacy-and-zero-write-gates-implementation-plan.md",
            "2026-08-12-dg-p6-p7-naming-and-order-review-plan.md",
            "2026-08-12-post-p5-capability-foundation-execution-prompt.md",
        ]),
    ]
    ledger_path = project_root / august_base / "07-F0八月分析逐文件覆盖台账.md"
    ledger_text = read_text(ledger_path)
    ledger_markers = [
        "世界基础设施增量指导/00-标签体系与元规则引擎.md",
        "玩法系统/01-玩法系统总纲.md",
        "角色与社会投影增量指导/09-社交关系声望与身份系统.md",
        "创作与运营/15-玩法包契约垂直样板与验证.md",
        "04-VLA世界模型与机器人沙盒方向.md",
        "07-算力成本记忆复用与运行经济.md",
        "owner、写入路径、schema/revision、投影/隐私规则、Harness 断言、迁移或回滚",
    ]
    dg_path = project_root / spec_base / "2026-08-12-dg-p6-p7-naming-and-order-decision-record.md"
    dg_text = read_text(dg_path)
    dg_markers = [
        "phase5a-quest-objective-evidence-report.json",
        "post-p5-f1a-semantic-causal-gate-report.json",
        "p6a-creator-scope-authority",
        "p7d-robotics-safety",
        "Harness `run_id`",
        "contract/schema revision",
        "invalidates every\nsuccessor row",
    ]
    cross_link_paths = [
        project_root / august_base / "README.md",
        project_root / spec_base / "README.md",
        project_root / plan_base / "README.md",
        project_root / plan_base / "2026-08-12-post-p5-capability-foundation-execution-prompt.md",
    ]
    cross_link_markers = [
        "07-F0八月分析逐文件覆盖台账.md",
        "post-p5-capability-foundation",
        "post-p5-capability-foundation-execution-prompt.md",
        "post-p5-capability-foundation-docs",
    ]
    combined_cross_links = "\n".join(read_text(path) for path in cross_link_paths)
    results = [
        _result(
            "post_p5_documents_exist",
            "Post-P5 August guidance, formal specs, matching plans, and execution prompt exist",
            not _missing(project_root, required_documents),
            required_documents,
            "\n".join(_missing(project_root, required_documents)),
        ),
        _result(
            "f0_august_coverage_ledger_complete",
            "F0 ledger maps all non-phase-progression August analysis families",
            all(marker in ledger_text for marker in ledger_markers),
            [str(ledger_path.relative_to(project_root)).replace("\\", "/")],
            "\n".join(marker for marker in ledger_markers if marker not in ledger_text),
        ),
        _result(
            "dg_opening_matrix_is_evidence_aware",
            "P6/P7 opening matrix names report paths, freshness invalidation, and future profiles",
            all(marker in dg_text for marker in dg_markers),
            [str(dg_path.relative_to(project_root)).replace("\\", "/")],
            "\n".join(marker for marker in dg_markers if marker not in dg_text),
        ),
        _result(
            "post_p5_cross_links_present",
            "August guidance, formal specs, plans, and execution prompt cross-link",
            all(marker in combined_cross_links for marker in cross_link_markers),
            [str(path.relative_to(project_root)).replace("\\", "/") for path in cross_link_paths],
            "\n".join(marker for marker in cross_link_markers if marker not in combined_cross_links),
        ),
    ]
    return {
        "scope": "documentation-gate-only; does not prove F0-F2, P6, or P7 runtime completion",
        "results": results,
        "overall_post_p5_capability_foundation_docs_passed": all(
            str(entry["status"]) == "proved" for entry in results
        ),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_post_p5_capability_foundation_docs(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "post-p5-capability-foundation-docs-report.json"
    md_path = log_dir / "post-p5-capability-foundation-docs-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Post-P5 Capability Foundation Documentation Gate Report",
        report,
        "overall_post_p5_capability_foundation_docs_passed",
    )
    print(f"post_p5_capability_foundation_docs_report_json={json_path}")
    print(f"post_p5_capability_foundation_docs_report_md={md_path}")
    print(f"overall_post_p5_capability_foundation_docs_passed={report['overall_post_p5_capability_foundation_docs_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_post_p5_capability_foundation_docs_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
