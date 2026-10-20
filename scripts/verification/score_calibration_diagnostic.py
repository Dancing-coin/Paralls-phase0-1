"""Score a sealed calibration envelope in a separate truth-bearing process."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / "backend"))
from app.character_agent.evaluation.calibration_contracts import canonical_records_digest, canonical_digest_excluding, score_calibration_records, _invalid, _accepted_labels

DENOMINATORS={"autonomous_decision":8,"explicit_instruction_diagnostic":6,"role_sensitive_decision":8}
HITS={"autonomous_decision":6,"explicit_instruction_diagnostic":5,"role_sensitive_decision":6}
THRESHOLD="sha256:a4bb6f41bc165ed1a645550ee54a7e1830ff5f5dbd8843bb73ecfbf6b6517ba1"


def digest(value):
    return "sha256:"+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def file_digest(data):
    return "sha256:"+hashlib.sha256(data).hexdigest()


def validate_archive(envelope, manifest):
    records=envelope.get("records")
    if not isinstance(records,list) or envelope.get("records_digest")!=canonical_records_digest(records): raise ValueError("records digest mismatch")
    if envelope.get("envelope_digest")!=canonical_digest_excluding(envelope,{"envelope_digest"}): raise ValueError("envelope digest mismatch")
    if envelope.get("run_status",{}).get("status") not in {"sealed","stopped_on_invalid_or_error"}: raise ValueError("archive is not sealed")
    meta=envelope.get("metadata",{})
    if meta.get("input_digest")!=manifest.get("new_input_digest") or meta.get("manifest_digest")!=digest(manifest): raise ValueError("archive input/manifest digest mismatch")
    ids=manifest.get("formal_question_ids"); rows=manifest.get("records")
    if not isinstance(ids,list) or len(ids)!=22 or len(set(ids))!=22 or not isinstance(rows,list) or len(rows)!=22 or len(records)!=22: raise ValueError("archive question coverage mismatch")
    if [r.get("question_id") for r in records]!=ids or [r.get("question_id") for r in rows]!=ids: raise ValueError("archive request mapping mismatch")
    for record,row in zip(records,rows):
        if record.get("track")!=row.get("track") or record.get("request_digest")!=row.get("wire_digest"): raise ValueError("archive request mapping mismatch")
        if record.get("request_digest")!=digest(record.get("request")): raise ValueError("request digest mismatch")
        expected_response_digest=digest(record["response_body"]) if record.get("response_body") is not None else None
        if record.get("response_digest")!=expected_response_digest: raise ValueError("response digest mismatch")
        body=record.get("response_body")
        choice=(((body or {}).get("answers") or {}).get("choice") or {}).get("choice") if isinstance(body,dict) else None
        expected_response={"choice":choice} if isinstance(choice,str) else None
        if record.get("response")!=expected_response: raise ValueError("response choice mapping mismatch")
        if list(record["request"]["questions"]["choice"]["criteria"])!=row.get("candidate_order"): raise ValueError("request candidate order mismatch")
    return len(records)


def validate_score_admission(envelope, manifest, approval, truth_bytes, review_bytes,
                             prepared_bytes=None, source_manifest_bytes=None):
    validate_archive(envelope,manifest)
    records=envelope["records"]; rows=manifest["records"]; ids=manifest["formal_question_ids"]; meta=envelope["metadata"]
    if not isinstance(approval,dict) or approval.get("decision")!="approved" or approval.get("purpose")!="diagnostic_only": raise ValueError("independent approval missing or rejected")
    if not approval.get("reviewer_identity") or approval.get("result_exposure") is not False or approval.get("semantic_review",{}).get("decision")!="approved" or approval.get("transport_review",{}).get("decision")!="approved": raise ValueError("independent approval scope mismatch")
    paths=approval.get("read_log",{}).get("paths")
    if not isinstance(paths,list) or not paths or any(any(term in str(path).lower() for term in ("run-envelope","score.json","response")) for path in paths):
        raise ValueError("independent approval read scope mismatch")
    if (approval.get("actual_inputs_digest")!=meta.get("input_digest") or approval.get("review_input_sha256")!=file_digest(review_bytes)
        or not isinstance(approval.get("truth_sha256"),str) or not approval["truth_sha256"].startswith("sha256:")
        or (truth_bytes is not None and approval["truth_sha256"]!=file_digest(truth_bytes))
        or approval.get("threshold_digest")!=THRESHOLD
        or manifest.get("threshold_digest")!=THRESHOLD or approval.get("formal_question_ids")!=ids
        or approval.get("formal_denominators")!=DENOMINATORS): raise ValueError("independent approval version binding mismatch")
    if prepared_bytes is None or source_manifest_bytes is None: raise ValueError("independent approval source/mapping evidence missing")
    prepared=json.loads(prepared_bytes)
    if (prepared.get("inputs_digest")!=approval["actual_inputs_digest"]
        or approval.get("source",{}).get("metadata_manifest_sha256")!=file_digest(source_manifest_bytes)):
        raise ValueError("independent approval source binding mismatch")
    prepared_rows={r["question_id"]:r for r in prepared.get("prepared_records",[]) if isinstance(r,dict)}
    approved=approval.get("requests")
    if not isinstance(approved,list) or len(approved)!=22: raise ValueError("independent approval request mapping missing")
    corrected=approval.get("transport_review",{}).get("corrected_input_only_budget",{}).get("corrected_required_tokens_by_question")
    if not isinstance(corrected,dict) or set(corrected)!=set(ids): raise ValueError("independent approval budget audit missing")
    for record,row,item in zip(records,rows,approved):
        if (item.get("question_id")!=record["question_id"] or item.get("track")!=record["track"]
            or item.get("request_digest")!=record["request_digest"] or item.get("candidate_order")!=row["candidate_order"]
            or item.get("semantic_review")!="approved" or item.get("transport_review")!="approved"):
            raise ValueError("independent approval request mapping mismatch")
        prepared_row=prepared_rows.get(record["question_id"],{})
        prepared_context=prepared_row.get("prepared_request",{}).get("context",{})
        if (prepared_row.get("wire_digest")!=record["request_digest"]
            or prepared_context.get("candidate_digest")!=item.get("candidate_mapping_digest")
            or prepared_context.get("candidate_intents")!=item.get("candidate_order")):
            raise ValueError("independent approval candidate mapping mismatch")
        usage=record.get("usage") or {}
        if (usage.get("truncated") is False and usage.get("state_tokens_dropped")==0
            and corrected[record["question_id"]]!=usage.get("input_tokens")):
            raise ValueError("independent approval budget binding mismatch")
    return len(records)

def main() -> int:
    p=argparse.ArgumentParser()
    for name in ("archive","manifest","approval","truth","review-input","prepared-inputs","source-manifest","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--purpose",choices=("diagnostic","formal"),default="diagnostic")
    a=p.parse_args()
    if a.purpose!="diagnostic": raise SystemExit("exposed calibration scorer cannot grant formal acceptance")
    envelope=json.loads(a.archive.read_text(encoding="utf-8"))
    manifest=json.loads(a.manifest.read_text(encoding="utf-8"))
    try: validate_archive(envelope,manifest)
    except ValueError as exc: raise SystemExit(str(exc)) from exc
    approval=json.loads(a.approval.read_text(encoding="utf-8"))
    review_bytes=a.review_input.read_bytes()
    prepared_bytes=a.prepared_inputs.read_bytes()
    source_bytes=a.source_manifest.read_bytes()
    try: validate_score_admission(envelope,manifest,approval,None,review_bytes,prepared_bytes,source_bytes)
    except ValueError as exc: raise SystemExit(str(exc)) from exc
    truth_bytes=a.truth.read_bytes()
    try: validate_score_admission(envelope,manifest,approval,truth_bytes,review_bytes,prepared_bytes,source_bytes)
    except ValueError as exc: raise SystemExit(str(exc)) from exc
    truth_doc=json.loads(truth_bytes)
    truth={j["question_id"]: j for j in truth_doc.get("judgments",[]) if isinstance(j,dict) and j.get("formal_denominator_computable") is True}
    if set(truth)!=set(manifest["formal_question_ids"]): raise SystemExit("approved truth question coverage mismatch")
    result=score_calibration_records(envelope["records"],truth,formal_denominators=DENOMINATORS,minimum_valid=DENOMINATORS)
    items=[]
    for record in envelope["records"]:
        invalid=_invalid(record); accepted=_accepted_labels(truth[record["question_id"]].get("acceptable_action_set"))
        if not accepted: invalid=invalid or "truth_missing"
        choice=(record.get("response") or {}).get("choice")
        items.append({"question_id":record["question_id"],"track":record["track"],"valid":invalid is None,
                      "invalid_reason":invalid,"selected":choice,"hit":invalid is None and choice in accepted})
    result["per_question"]=items
    result["policy_a"]=("pass" if all(result["tracks"][track]["hits"]>=minimum for track,minimum in HITS.items()) else "fail") if result["status"]=="scored" else "blocked"
    result.update(purpose="exposed_calibration_repair_diagnostic",formal_acceptance=False,
                  archive_digest=envelope["envelope_digest"],truth_digest=file_digest(truth_bytes),
                  approval_digest=file_digest(a.approval.read_bytes()),threshold_digest=THRESHOLD,
                  evidence_limitations=["v2 archive lacks bound execution identity/read log",
                                        "new runner contract cannot retroactively attest v2 execution",
                                        "exposed calibration is not blind final or holdout"])
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); return 0 if result["status"]=="scored" else 2
if __name__ == "__main__": raise SystemExit(main())
