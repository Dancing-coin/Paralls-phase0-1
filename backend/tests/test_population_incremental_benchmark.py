from scripts.verification.verify_population_data_oriented_incremental import (
    measure_incremental_history,
    measure_projection_scale,
)


def test_incremental_measurement_uses_real_publisher_and_reads_only_tail() -> None:
    result = measure_incremental_history(
        history=1_000,
        population=100,
        tail=10,
        samples=2,
    )

    assert result["replay_equivalent"] is True
    assert result["overall_passed"] is True
    assert result["prefix_checkpoint_sequence"] == 1_000
    assert result["full_oracle_event_count"] == 1_020
    assert result["input_hash"].startswith("sha256:")
    assert result["output_hash"] == result["full_oracle_hash"]
    assert result["peak_rss_bytes"] > 0
    assert len(result["samples"]) == 2
    assert all(sample["published"] for sample in result["samples"])
    assert all(sample["read_events_calls"] == 1 for sample in result["samples"])
    assert all(sample["read_events_returned"] == 10 for sample in result["samples"])
    assert all(sample["read_events_encoded_bytes"] > 0 for sample in result["samples"])
    assert all(sample["read_stream_calls"] == 1 for sample in result["samples"])
    assert all(sample["read_stream_returned"] == 1 for sample in result["samples"])
    assert all(sample["read_stream_encoded_bytes"] > 0 for sample in result["samples"])
    assert result["p95_ms"] >= result["p50_ms"] > 0


def test_projection_scale_measurement_runs_real_siming_pipeline() -> None:
    result = measure_projection_scale(population=54, samples=2)

    assert result["overall_passed"] is True
    assert result["population"] == 54
    assert result["published_projection_count"] == 54
    assert result["pipeline_audit_count"] == 2
    assert result["input_encoded_bytes"] > 0
    assert result["output_encoded_bytes"] > 0
    assert result["input_hash"].startswith("sha256:")
    assert result["output_hash"].startswith("sha256:")
    assert result["p95_ms"] >= result["p50_ms"] > 0
