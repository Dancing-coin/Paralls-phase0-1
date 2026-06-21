from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_llm_provider_is_only_invoked_from_siming_runtime() -> None:
    offenders: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        references_siming_llm = (
            "siming_llm_provider" in text
            or "SimingLlm" in text
            or "_llm_provider" in text
        )
        if not references_siming_llm or "generate_candidates(" not in text:
            continue
        if rel not in {"app/services/siming_runtime.py", "app/services/siming_llm_provider.py"}:
            offenders.append(rel)

    assert offenders == []


def test_consumer_producer_and_bus_do_not_import_llm_provider() -> None:
    for rel in [
        "app/services/siming_event_consumer.py",
        "app/services/siming_event_producer.py",
        "app/services/authority_event_bus.py",
    ]:
        assert "siming_llm_provider" not in read(rel)


def test_no_formal_dispatch_requested_event_family_exists() -> None:
    for rel in ["app/services/siming_runtime.py", "app/services/siming_event_producer.py"]:
        text = read(rel)
        assert 'return "siming.dispatch_requested"' not in text
        assert "event_type = \"siming.dispatch_requested\"" not in text
        assert 'event_type="siming.dispatch_requested"' not in text
