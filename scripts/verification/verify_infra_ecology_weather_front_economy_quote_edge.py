from common import repo_root,resolve_python_exe,run_command,verification_dir,write_json
def main():
 root=repo_root(); py=resolve_python_exe(None); test=root/"backend/tests/test_infra_ecology_weather_front_economy_quote_edge.py"; cases=["test_weather_front_updates_only_existing_economy_quote_through_owner_spine","test_weather_front_quote_forged_admission_is_zero_write","test_weather_front_quote_stale_ecology_head_is_zero_write","test_weather_quote_admission_cannot_be_reused_for_another_quote","test_weather_quote_duplicate_is_idempotent_and_replayable","test_weather_quote_duplicate_key_cannot_replay_a_different_admitted_source","test_authority_only_weather_front_cannot_admit_a_project_quote_update"]; checks={}
 for case in cases:
  result=run_command([py,"-m","pytest","-q",f"{test}::{case}"],root,verification_dir(root)/f"infra-ecology-weather-front-economy-quote-{case}.log"); checks[case]=result.returncode==0
 write_json(verification_dir(root)/"infra-ecology-weather-front-economy-quote-edge-report.json",{"profile":"infra-ecology-weather-front-economy-quote-edge","overall_passed":all(checks.values()),"checks":checks}); return 0 if all(checks.values()) else 1
if __name__=="__main__": raise SystemExit(main())
