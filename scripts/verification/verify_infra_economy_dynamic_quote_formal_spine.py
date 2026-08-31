from __future__ import annotations
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json

def main() -> int:
    root=repo_root(); python=resolve_python_exe(None); tests=root/"backend"/"tests"/"test_infra_economy_dynamic_quote_formal_spine.py"
    cases={"formal_owner_outbox":"test_dynamic_quote_uses_the_formal_economy_owner_spine_and_redacted_project_outbox","idempotency_zero_write":"test_dynamic_quote_idempotency_revision_and_invalid_payload_are_zero_write","revision_conflict_zero_write":"test_dynamic_quote_stale_revision_is_zero_write","private_payload_zero_write":"test_dynamic_quote_rejects_account_truth_in_project_quote_payload","full_checkpoint_tail_replay":"test_dynamic_quote_replays_full_and_checkpoint_tail"}
    checks={}; evidence=[]
    for key, selector in cases.items():
        log=verification_dir(root)/f"infra-economy-dynamic-quote-formal-spine-{key}.log"; result=run_command([python,"-m","pytest","-q",f"{tests}::{selector}"],root,log); checks[key]=result.returncode==0; evidence.append(str(log.relative_to(root)).replace("\\","/"))
    write_json(verification_dir(root)/"infra-economy-dynamic-quote-formal-spine-report.json",{"profile":"infra-economy-dynamic-quote-formal-spine","overall_passed":all(checks.values()),"checks":checks,"focused_test_files":[str(tests.relative_to(root)).replace("\\","/")],"evidence":evidence,"limitations":["This package creates no consumer admission. INF-3J separately binds one fixed Ecology source to this already formalized quote owner."]})
    return 0 if all(checks.values()) else 1
if __name__=="__main__": raise SystemExit(main())
