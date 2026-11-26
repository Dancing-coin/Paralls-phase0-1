from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.fact_type_registry import FactTypeRegistry
from app.gameplay.package_migration_runtime import (
    PackageArchive,
    PackageMigrationAuthority,
    PackageMigrationError,
    PackageRef,
    load_package_archive,
    load_deployment_package_archive,
    resolve_package_set_at,
)
from app.gameplay.rule_pack_validator import LoadedPack, load_pack


FACILITY_PACK = Path(__file__).resolve().parents[2] / "packs/county_siege_facility"


def _pack(pack_id: str, version: str, content_hash: str | None = None) -> LoadedPack:
    return LoadedPack(
        pack_id=pack_id,
        version=version,
        content_hash=content_hash or f"sha256:{pack_id}:{version}",
        registry=FactTypeRegistry({}, {}, {}),
        legacy_rule={},
    )


def _archive(packages: list[LoadedPack]) -> PackageArchive:
    return PackageArchive(
        packages,
        expected_content_hashes={
            PackageRef(package.pack_id, package.version): package.content_hash
            for package in packages
        },
    )


def _authority(archive: PackageArchive) -> tuple[GameplayEventStore, PackageMigrationAuthority]:
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    return store, PackageMigrationAuthority(store, archive, "world:test")


def test_package_archive_resolves_immutable_package_identity() -> None:
    pack = _pack("rules", "1")
    archive = _archive([pack])

    assert archive.resolve(PackageRef("rules", "1")) is pack


def test_package_archive_rejects_conflicting_hash_for_same_identity() -> None:
    with pytest.raises(PackageMigrationError, match="package_archive_hash_conflict"):
        PackageArchive(
            [_pack("rules", "1", "sha256:first"), _pack("rules", "1", "sha256:second")],
            expected_content_hashes={PackageRef("rules", "1"): "sha256:first"},
        )


def test_package_archive_rejects_content_hash_changed_from_archive_pin() -> None:
    ref = PackageRef("rules", "1")
    with pytest.raises(PackageMigrationError, match="package_archive_content_hash_mismatch"):
        PackageArchive(
            [_pack("rules", "1", "sha256:changed")],
            expected_content_hashes={ref: "sha256:original"},
        )


def test_package_archive_bootstrap_loads_directory_against_trusted_hash_pin() -> None:
    ref = PackageRef("county_siege_facility", "1.0.0")
    trusted_hash = load_pack(FACILITY_PACK, handlers={}).content_hash

    archive = load_package_archive(
        {ref: FACILITY_PACK}, {ref: trusted_hash}, handlers={},
    )

    assert archive.resolve(ref).content_hash == trusted_hash


def test_package_archive_bootstrap_requires_a_trusted_hash_for_every_directory() -> None:
    ref = PackageRef("county_siege_facility", "1.0.0")

    with pytest.raises(PackageMigrationError, match="package_archive_content_hash_mismatch"):
        load_package_archive({ref: FACILITY_PACK}, {}, handlers={})


def test_deployment_manifest_bootstrap_resolves_canonical_identity_keys() -> None:
    identity = "county_siege_facility@1.0.0"
    trusted_hash = load_pack(FACILITY_PACK, handlers={}).content_hash

    archive = load_deployment_package_archive(
        {identity: "packs/county_siege_facility"},
        {identity: trusted_hash},
        base_directory=FACILITY_PACK.parents[1],
        handlers={},
    )

    assert archive.resolve(PackageRef("county_siege_facility", "1.0.0")).content_hash == trusted_hash


def test_deployment_manifest_rejects_partial_identity_sets() -> None:
    with pytest.raises(PackageMigrationError, match="package_deployment_manifest_mismatch"):
        load_deployment_package_archive(
            {"county_siege_facility@1.0.0": "packs/county_siege_facility"},
            {},
            base_directory=FACILITY_PACK.parents[1],
            handlers={},
        )


def test_package_archive_bootstrap_rejects_directory_content_changed_after_pin(tmp_path) -> None:
    ref = PackageRef("county_siege_facility", "1.0.0")
    trusted_hash = load_pack(FACILITY_PACK, handlers={}).content_hash
    changed_pack = tmp_path / "facility"
    shutil.copytree(FACILITY_PACK, changed_pack)
    content = changed_pack / "pool_defs/gate_integrity.yaml"
    content.write_text(
        content.read_text(encoding="utf-8").replace('initial: "100"', 'initial: "99"'),
        encoding="utf-8",
    )

    with pytest.raises(PackageMigrationError, match="package_archive_content_hash_mismatch"):
        load_package_archive({ref: changed_pack}, {ref: trusted_hash}, handlers={})


def test_package_archive_bootstrap_resolves_and_pins_parent_overlay(tmp_path) -> None:
    parent_ref = PackageRef("county_siege_facility", "1.0.0")
    child_ref = PackageRef("facility_overlay", "2.0.0")
    child = tmp_path / "overlay"
    child.mkdir()
    (child / "pack.yaml").write_text(
        'pack_id: "facility_overlay"\n'
        'pack_version: "2.0.0"\n'
        'schema_version: 1\n'
        'parent_pack: {pack_id: "county_siege_facility", pack_version: "1.0.0"}\n',
        encoding="utf-8",
    )
    expected_hashes = {
        parent_ref: load_pack(FACILITY_PACK, handlers={}).content_hash,
        child_ref: load_pack(
            child,
            handlers={},
            parent_packs={(parent_ref.pack_id, parent_ref.pack_version): FACILITY_PACK},
        ).content_hash,
    }

    archive = load_package_archive(
        {parent_ref: FACILITY_PACK, child_ref: child}, expected_hashes, handlers={},
    )

    loaded_child = archive.resolve(child_ref)
    assert [pin.pack_id for pin in loaded_child.resolved_packs] == [
        "county_siege_facility", "facility_overlay",
    ]
    assert archive.resolve(parent_ref).content_hash == expected_hashes[parent_ref]


def test_replay_without_migrations_uses_initial_package_set() -> None:
    initial = _pack("rules", "1")
    archive = _archive([initial])

    assert resolve_package_set_at([], archive, 0, initial_packages=[PackageRef("rules", "1")]) == (initial,)


def test_replay_without_migrations_requires_an_initial_package_set() -> None:
    with pytest.raises(PackageMigrationError, match="package_migration_initial_set_required"):
        resolve_package_set_at([], _archive([]), 0)


def test_replay_uses_from_before_and_to_at_or_after_migration_sequence() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    archive = _archive([old, new])
    store, authority = _authority(archive)
    result = authority.migrate(
        command_id="migrate-1",
        idempotency_key="idem:migrate-1",
        expected_revision=0,
        from_packages=[PackageRef("rules", "1")],
        to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:rules-2",
        affected_fact_types=["Ownership.Right"],
    )
    assert result.committed
    assert result.global_sequence_range is not None
    sequence = result.global_sequence_range[1]
    events = store.read_stream("platform:rule-packs:world:test")

    assert resolve_package_set_at(events, archive, sequence - 1) == (old,)
    assert resolve_package_set_at(events, archive, sequence) == (new,)
    assert resolve_package_set_at(events, archive, sequence + 1) == (new,)


def test_replay_resolves_history_before_multiple_committed_migrations() -> None:
    packs = tuple(_pack("rules", version) for version in ("1", "2", "3"))
    archive = _archive(packs)
    store, authority = _authority(archive)
    sequences = []
    for revision in range(2):
        result = authority.migrate(
            command_id=f"migrate-{revision}", idempotency_key=f"idem:migrate-{revision}",
            expected_revision=revision,
            from_packages=[PackageRef("rules", packs[revision].version)],
            to_packages=[PackageRef("rules", packs[revision + 1].version)],
            migration_ref=f"migration:rules-{revision + 2}", affected_fact_types=[],
        )
        assert result.committed and result.global_sequence_range is not None
        sequences.append(result.global_sequence_range[1])
    events = store.read_stream("platform:rule-packs:world:test")

    assert resolve_package_set_at(events, archive, sequences[0] - 1) == packs[:1]
    assert resolve_package_set_at(events, archive, sequences[0]) == packs[1:2]
    assert resolve_package_set_at(events, archive, sequences[1]) == packs[2:]


def test_replay_rejects_broken_from_chain() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    third = _pack("rules", "3")
    archive = _archive([old, new, third])
    store, authority = _authority(archive)
    first = authority.migrate(
        command_id="migrate-1", idempotency_key="idem:migrate-1", expected_revision=0,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:rules-2", affected_fact_types=[],
    )
    assert first.committed
    second = authority.migrate(
        command_id="migrate-2", idempotency_key="idem:migrate-2", expected_revision=1,
        from_packages=[PackageRef("rules", "3")], to_packages=[PackageRef("rules", "1")],
        migration_ref="migration:rules-1", affected_fact_types=[],
    )
    assert not second.committed
    with pytest.raises(PackageMigrationError, match="package_migration_from_chain_invalid"):
        resolve_package_set_at(
            [*store.read_stream("platform:rule-packs:world:test"),
             _migration_event(3, PackageRef("rules", "3"), PackageRef("rules", "1"), revision=2)],
            archive,
            3,
        )


def test_replay_rejects_ambiguous_global_sequence() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    archive = _archive([old, new])
    event = _migration_event(1, PackageRef("rules", "1"), PackageRef("rules", "2"))

    with pytest.raises(PackageMigrationError, match="package_migration_sequence_ambiguous"):
        resolve_package_set_at([event, event.model_copy(update={"event_id": "event:duplicate"})], archive, 1)


def test_replay_rejects_malformed_package_identity_in_event_payload() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    archive = _archive([old, new])
    event = _migration_event(1, PackageRef("rules", "1"), PackageRef("rules", "2"))
    event.payload["from"] = [{"pack": 123, "version": "1"}]

    with pytest.raises(PackageMigrationError, match="package_migration_payload_invalid"):
        resolve_package_set_at([event], archive, 1)


def _migration_event(sequence: int, source: PackageRef, target: PackageRef, *, revision: int | None = None):
    from app.gameplay.models import GameplayEvent

    return GameplayEvent(
        event_id=f"event:fixture:{sequence}", event_type="pack.migrated", schema_version=1,
        stream_id="platform:rule-packs:world:test", stream_revision=sequence if revision is None else revision,
        global_sequence=sequence, transaction_id=f"transaction:fixture:{sequence}",
        command_id=f"fixture:{sequence}", causation_id=f"fixture:{sequence}",
        correlation_id=f"fixture:{sequence}", visibility_policy="project",
        payload={
            "from": [{"pack": source.pack_id, "version": source.pack_version}],
            "to": [{"pack": target.pack_id, "version": target.pack_version}],
            "migration_ref": "migration:fixture", "affected_fact_types": [],
        },
    )


def test_migration_commits_formal_payload_and_duplicate_replays_before_pin_check() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    store, authority = _authority(_archive([old, new]))
    args = dict(
        command_id="migrate-1", idempotency_key="idem:migrate-1", expected_revision=0,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:rules-2", affected_fact_types=["Ownership.Right"],
    )
    result = authority.migrate(**args)
    retry = authority.migrate(**args)

    assert result.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert len(store.read_stream("platform:rule-packs:world:test")) == 1
    assert store.read_stream("platform:rule-packs:world:test")[0].payload == {
        "from": [{"pack": "rules", "version": "1"}],
        "to": [{"pack": "rules", "version": "2"}],
        "migration_ref": "migration:rules-2",
        "affected_fact_types": ["Ownership.Right"],
    }


def test_durable_migration_reopens_and_replays_at_historical_sequence(tmp_path) -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    archive = _archive([old, new])
    path = tmp_path / "package-migration.db"
    args = dict(
        command_id="migrate-durable", idempotency_key="idem:migrate-durable", expected_revision=0,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:rules-2", affected_fact_types=[],
    )
    store = DurableGameplayEventStore(
        path, event_schema_registry=create_stormnight_event_schema_registry()
    )
    result = PackageMigrationAuthority(store, archive, "world:test").migrate(**args)
    assert result.committed and result.global_sequence_range is not None
    sequence = result.global_sequence_range[1]
    store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        events = reopened.read_stream("platform:rule-packs:world:test")
        assert resolve_package_set_at(events, archive, sequence - 1) == (old,)
        assert resolve_package_set_at(events, archive, sequence) == (new,)
        retry = PackageMigrationAuthority(reopened, archive, "world:test").migrate(**args)
        assert retry.idempotency_status == "duplicate_replayed"
        assert len(reopened.read_stream("platform:rule-packs:world:test")) == 1
    finally:
        reopened.close()


def test_changed_duplicate_payload_is_rejected_without_writing() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    third = _pack("rules", "3")
    store, authority = _authority(_archive([old, new, third]))
    args = dict(
        command_id="migrate-1", idempotency_key="idem:migrate-1", expected_revision=0,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:rules-2", affected_fact_types=[],
    )
    authority.migrate(**args)
    with pytest.raises(PackageMigrationError, match="idempotency_key_reused"):
        authority.migrate(**{**args, "to_packages": [PackageRef("rules", "3")]})
    assert len(store.read_stream("platform:rule-packs:world:test")) == 1


def test_stale_source_package_set_is_rejected_without_writing() -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    store, authority = _authority(_archive([old, new]))
    committed = authority.migrate(
        command_id="migrate-first", idempotency_key="idem:migrate-first", expected_revision=0,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:first", affected_fact_types=[],
    )
    assert committed.committed

    result = authority.migrate(
        command_id="migrate-stale", idempotency_key="idem:migrate-stale", expected_revision=1,
        from_packages=[PackageRef("rules", "1")], to_packages=[PackageRef("rules", "2")],
        migration_ref="migration:stale", affected_fact_types=[],
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "package_migration_source_set_stale"
    assert len(store.read_stream("platform:rule-packs:world:test")) == 1


@pytest.mark.parametrize(
    ("expected_revision", "from_packages", "to_packages", "error_code"),
    [
        (9, [PackageRef("rules", "1")], [PackageRef("rules", "2")], "revision_conflict"),
        (0, [PackageRef("rules", "1")], [PackageRef("missing", "1")], "package_archive_identity_unknown"),
    ],
)
def test_rejected_migration_writes_nothing(expected_revision, from_packages, to_packages, error_code) -> None:
    old = _pack("rules", "1")
    new = _pack("rules", "2")
    store, authority = _authority(_archive([old, new]))
    result = authority.migrate(
        command_id="migrate-rejected", idempotency_key="idem:migrate-rejected",
        expected_revision=expected_revision, from_packages=from_packages, to_packages=to_packages,
        migration_ref="migration:attempt", affected_fact_types=[],
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error_code
    assert store.read_stream("platform:rule-packs:world:test") == []
