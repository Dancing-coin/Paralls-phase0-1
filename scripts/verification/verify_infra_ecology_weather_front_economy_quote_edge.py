from datetime import datetime, timezone
from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown
def main():
 root=repo_root(); py=resolve_python_exe(None); test=root/"backend/tests/test_infra_ecology_weather_front_economy_quote_edge.py"; cases={"existing_quote_owner_spine":"test_weather_front_updates_only_existing_economy_quote_through_owner_spine","forged_admission_zero_write":"test_weather_front_quote_forged_admission_is_zero_write","stale_ecology_head_zero_write":"test_weather_front_quote_stale_ecology_head_is_zero_write","admission_not_reusable":"test_weather_quote_admission_cannot_be_reused_for_another_quote","duplicate_replay":"test_weather_quote_duplicate_is_idempotent_and_replayable","changed_duplicate_zero_write":"test_weather_quote_duplicate_key_cannot_replay_a_different_admitted_source","authority_only_source_zero_write":"test_authority_only_weather_front_cannot_admit_a_project_quote_update"}; checks={}; evidence=[]
 for name, case in cases.items():
  log=verification_dir(root)/f"infra-ecology-weather-front-economy-quote-edge-{name}.log"; result=run_command([py,"-m","pytest","-q",str(test),"-k",case],root,log); checks[name]=result.returncode==0; evidence.append(artifact_ref(root,log).replace("\\","/"))
 report={"profile":"infra-ecology-weather-front-economy-quote-edge","overall_passed":all(checks.values()),"checks":checks,"focused_test_files":[artifact_ref(root,test).replace("\\","/")],"evidence":evidence,"run_id":f"infra-ecology-weather-front-economy-quote-edge-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}","commit":evidence_revision(root),"write_path":"Ecology weather-front source -> existing Economy quote owner -> GameplayEventStore.append_batch -> scoped outbox/replay","limitations":["Only pre-existing Economy quote refs are admitted; no generic quote registry or pricing formula is created.","This path changes quote projection only; it does not mutate accounts, settle payment, or create a scheduler."]}
 path=verification_dir(root)/"infra-ecology-weather-front-economy-quote-edge-report.json"; write_json(path,report); write_markdown(path.with_suffix(".md"),"Weather-Front Economy Quote Edge Report",{"results":[{"id":k,"status":"proved" if v else "missing","title":k} for k,v in checks.items()]},"overall_passed"); print(f"infra_ecology_weather_front_economy_quote_edge_report_json={path}"); print(f"overall_infra_ecology_weather_front_economy_quote_edge_passed={report['overall_passed']}"); return 0 if report["overall_passed"] else 1
if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
