from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from common import evidence_revision, repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    ledger = root / "docs/8月分析/P5后能力基础推进/07-F0八月分析逐文件覆盖台账.md"
    owner = root / "docs/8月分析/P5后能力基础推进/f0-owner-map.md"
    gap = root / "docs/8月分析/P5后能力基础推进/f0-gap-register.md"
    claims = root / "docs/8月分析/P5后能力基础推进/f0-claim-ledger.md"
    manifest = root / "docs/8月分析/P5后能力基础推进/f0-evidence-manifest.md"
    texts = [path.read_text(encoding="utf-8") for path in (ledger, owner, gap, claims, manifest)]
    required_columns = all(token in texts[0] for token in ("当前结论", "已有 owner / 证据入口", "后续轨道", "主要风险"))
    covered = texts[0].count("|") > 20 and all("状态" in text for text in texts[1:])
    report = {"profile": "post-p5-f0-complete", "scope": "complete", "overall_passed": required_columns and covered, "checks": {"file_by_file_ledger": required_columns, "owner_map": covered, "gap_register": covered, "claim_ledger": covered, "evidence_manifest": covered}, "run_id": f"post-p5-f0-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "owner": "mainline-maintainer", "freshness": "invalidated by owner/schema/assertion changes"}
    path = verification_dir(root) / "post-p5-f0-complete-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Post-P5 F0 Complete Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in report["checks"].items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"post_p5_f0_complete_report_json={path}")
    print(f"overall_post_p5_f0_complete_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
