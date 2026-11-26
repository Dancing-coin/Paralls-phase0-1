from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.gameplay.event_schema_registry import EventSchemaRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.owner_runtime_base import rejected_result, replay_duplicate
from app.gameplay.rule_pack_validator import LoadedPack, load_pack
from app.gameplay.settlement_plan import build_atomic_event_batch


class PackageMigrationError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class PackageRef:
    pack_id: str
    pack_version: str

    def __post_init__(self) -> None:
        if (type(self.pack_id) is not str or not self.pack_id
                or type(self.pack_version) is not str or not self.pack_version):
            raise PackageMigrationError("package_identity_invalid")


class PackageArchive:
    def __init__(
        self,
        packages: Sequence[LoadedPack],
        *,
        expected_content_hashes: Mapping[PackageRef, str],
    ) -> None:
        if not isinstance(packages, Sequence):
            raise PackageMigrationError("package_archive_entries_invalid")
        if not isinstance(expected_content_hashes, Mapping):
            raise PackageMigrationError("package_archive_hash_pins_invalid")
        hash_pins: dict[PackageRef, str] = {}
        for ref, content_hash in expected_content_hashes.items():
            if (not isinstance(ref, PackageRef) or type(content_hash) is not str
                    or not content_hash or ref in hash_pins):
                raise PackageMigrationError("package_archive_hash_pins_invalid")
            hash_pins[ref] = content_hash

        indexed: dict[PackageRef, LoadedPack] = {}
        for package in packages:
            if not isinstance(package, LoadedPack):
                raise PackageMigrationError("package_archive_entry_invalid")
            if type(package.content_hash) is not str or not package.content_hash:
                raise PackageMigrationError("package_archive_hash_invalid")
            ref = PackageRef(package.pack_id, package.version)
            existing = indexed.get(ref)
            if existing is not None and existing.content_hash != package.content_hash:
                raise PackageMigrationError("package_archive_hash_conflict")
            if hash_pins.get(ref) != package.content_hash:
                raise PackageMigrationError("package_archive_content_hash_mismatch")
            indexed.setdefault(ref, package)
        if set(hash_pins) != set(indexed):
            raise PackageMigrationError("package_archive_hash_pin_unmatched")
        self._packages: Mapping[PackageRef, LoadedPack] = MappingProxyType(indexed)

    def resolve(self, package_ref: PackageRef) -> LoadedPack:
        try:
            return self._packages[package_ref]
        except KeyError as exc:
            raise PackageMigrationError("package_archive_identity_unknown") from exc


def load_package_archive(
    package_directories: Mapping[PackageRef, Path],
    trusted_content_hashes: Mapping[PackageRef, str],
    *,
    handlers: Mapping[str, Callable],
    owner_domains: Mapping[str, str] | None = None,
    command_fact_outputs: Mapping[str, set[str] | frozenset[str]] | None = None,
    event_schema_registry: EventSchemaRegistry | None = None,
) -> PackageArchive:
    if not isinstance(package_directories, Mapping) or any(
        not isinstance(ref, PackageRef) or not isinstance(directory, Path)
        for ref, directory in package_directories.items()
    ):
        raise PackageMigrationError("package_archive_directories_invalid")

    parent_directories = {
        (ref.pack_id, ref.pack_version): directory
        for ref, directory in package_directories.items()
    }
    loaded_packages: list[LoadedPack] = []
    for ref, directory in package_directories.items():
        package = load_pack(
            directory,
            handlers=handlers,
            parent_packs=parent_directories,
            owner_domains=owner_domains,
            command_fact_outputs=command_fact_outputs,
            event_schema_registry=event_schema_registry,
        )
        if (package.pack_id, package.version) != (ref.pack_id, ref.pack_version):
            raise PackageMigrationError("package_archive_identity_mismatch")
        loaded_packages.append(package)

    return PackageArchive(
        loaded_packages,
        expected_content_hashes=trusted_content_hashes,
    )


def load_deployment_package_archive(
    archive_directories: Mapping[str, str],
    trusted_content_hashes: Mapping[str, str],
    *,
    base_directory: Path,
    handlers: Mapping[str, Callable],
    owner_domains: Mapping[str, str] | None = None,
    command_fact_outputs: Mapping[str, set[str] | frozenset[str]] | None = None,
    event_schema_registry: EventSchemaRegistry | None = None,
) -> PackageArchive:
    """Load the package identities declared by the deployment contract."""
    if not isinstance(archive_directories, Mapping) or not isinstance(trusted_content_hashes, Mapping):
        raise PackageMigrationError("package_deployment_manifest_invalid")
    if set(archive_directories) != set(trusted_content_hashes):
        raise PackageMigrationError("package_deployment_manifest_mismatch")

    directories: dict[PackageRef, Path] = {}
    hashes: dict[PackageRef, str] = {}
    for identity, directory in archive_directories.items():
        if type(identity) is not str or identity.count("@") != 1:
            raise PackageMigrationError("package_deployment_identity_invalid")
        pack_id, pack_version = identity.split("@", 1)
        ref = PackageRef(pack_id, pack_version)
        if type(directory) is not str or not directory.strip():
            raise PackageMigrationError("package_deployment_directory_invalid")
        path = Path(directory)
        directories[ref] = path if path.is_absolute() else base_directory / path
        content_hash = trusted_content_hashes[identity]
        if type(content_hash) is not str or not content_hash.strip():
            raise PackageMigrationError("package_deployment_hash_invalid")
        hashes[ref] = content_hash
    return load_package_archive(
        directories,
        hashes,
        handlers=handlers,
        owner_domains=owner_domains,
        command_fact_outputs=command_fact_outputs,
        event_schema_registry=event_schema_registry,
    )


class PackageMigrationAuthority:
    PRINCIPAL_REF = "authority:platform:rule-pack-migration"

    def __init__(self, store: GameplayEventStore, archive: PackageArchive, world_ref: str) -> None:
        if type(world_ref) is not str or not world_ref:
            raise PackageMigrationError("package_migration_world_ref_invalid")
        self._store = store
        self._archive = archive
        self._world_ref = world_ref
        self._stream_id = f"platform:rule-packs:{world_ref}"

    def migrate(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        from_packages: Sequence[PackageRef],
        to_packages: Sequence[PackageRef],
        migration_ref: str,
        affected_fact_types: Sequence[str],
    ) -> AppendBatchResult:
        if not command_id or not idempotency_key or not migration_ref:
            raise PackageMigrationError("package_migration_command_identity_invalid")
        source = _normalize_refs(from_packages)
        target = _normalize_refs(to_packages)
        affected = _normalize_fact_types(affected_fact_types)
        payload = {
            "from": [_serialize_ref(ref) for ref in source],
            "to": [_serialize_ref(ref) for ref in target],
            "migration_ref": migration_ref,
            "affected_fact_types": list(affected),
        }
        if type(expected_revision) is not int or expected_revision < 0:
            return _rejected(command_id, "package_migration_revision_invalid")
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self.PRINCIPAL_REF,
            stream_id=self._stream_id,
            expected_revision=expected_revision,
            event_specs=(("pack.migrated", payload),),
            idempotency_key=idempotency_key,
            causation_id=command_id,
            correlation_id=f"world:{self._world_ref}",
            schema_version=1,
        )

        duplicate = replay_duplicate(
            self._store,
            principal=self.PRINCIPAL_REF,
            idempotency_key=idempotency_key,
            payload_digest=batch.idempotency_record.payload_digest,
            error_factory=PackageMigrationError,
            missing_result_code="package_migration_idempotency_missing_result",
        )
        if duplicate is not None:
            return duplicate

        try:
            for ref in (*source, *target):
                self._archive.resolve(ref)
        except PackageMigrationError as exc:
            return _rejected(command_id, str(exc))

        events = self._store.read_stream(self._stream_id)
        if events:
            active = resolve_package_set_at(
                events, self._archive, self._store.get_last_global_sequence()
            )
            active_refs = tuple(PackageRef(pack.pack_id, pack.version) for pack in active)
            if active_refs != source:
                return _rejected(command_id, "package_migration_source_set_stale")

        batch = batch.model_copy(
            update={
                "events": [batch.events[0].model_copy(update={"visibility_policy": "authority_only"})],
            },
            deep=True,
        )
        return self._store.append_batch(batch)


def resolve_package_set_at(
    events: Iterable[GameplayEvent],
    archive: PackageArchive,
    global_sequence: int,
    initial_packages: Sequence[PackageRef] | None = None,
) -> tuple[LoadedPack, ...]:
    if type(global_sequence) is not int or global_sequence < 0:
        raise PackageMigrationError("package_migration_sequence_invalid")

    state = _normalize_refs(initial_packages) if initial_packages is not None else None
    if state is not None:
        for ref in state:
            archive.resolve(ref)

    ordered = sorted(events, key=lambda event: event.global_sequence)
    if not ordered and initial_packages is None:
        raise PackageMigrationError("package_migration_initial_set_required")
    seen_sequences: set[int] = set()
    selected = state
    stream_id: str | None = None
    for revision, event in enumerate(ordered, start=1):
        if (event.event_type != "pack.migrated" or event.schema_version != 1
                or event.global_sequence < 1 or not event.stream_id.startswith("platform:rule-packs:")):
            raise PackageMigrationError("package_migration_event_invalid")
        if event.global_sequence in seen_sequences:
            raise PackageMigrationError("package_migration_sequence_ambiguous")
        seen_sequences.add(event.global_sequence)
        if event.stream_revision != revision:
            raise PackageMigrationError("package_migration_event_invalid")
        if stream_id is None:
            stream_id = event.stream_id
        elif stream_id != event.stream_id:
            raise PackageMigrationError("package_migration_event_invalid")
        source = _parse_event_refs(event.payload, "from")
        target = _parse_event_refs(event.payload, "to")
        migration_ref = event.payload.get("migration_ref")
        affected = event.payload.get("affected_fact_types")
        if not isinstance(migration_ref, str) or not migration_ref:
            raise PackageMigrationError("package_migration_payload_invalid")
        if not isinstance(affected, list):
            raise PackageMigrationError("package_migration_payload_invalid")
        try:
            _normalize_fact_types(affected)
        except PackageMigrationError as exc:
            raise PackageMigrationError("package_migration_payload_invalid") from exc
        for ref in (*source, *target):
            archive.resolve(ref)
        if state is not None and state != source:
            raise PackageMigrationError("package_migration_from_chain_invalid")
        state = target
        if selected is None:
            selected = source
        if event.global_sequence <= global_sequence:
            selected = target

    if selected is None:
        selected = ()
    return tuple(archive.resolve(ref) for ref in selected)


def _normalize_refs(refs: Sequence[PackageRef] | None) -> tuple[PackageRef, ...]:
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
        raise PackageMigrationError("package_identity_list_invalid")
    if any(not isinstance(ref, PackageRef) for ref in refs):
        raise PackageMigrationError("package_identity_list_invalid")
    normalized = tuple(sorted(refs))
    if len(set(normalized)) != len(normalized):
        raise PackageMigrationError("package_identity_duplicate")
    return normalized


def _normalize_fact_types(fact_types: Sequence[str]) -> tuple[str, ...]:
    if (
        not isinstance(fact_types, Sequence)
        or isinstance(fact_types, (str, bytes))
        or any(not isinstance(fact_type, str) or not fact_type for fact_type in fact_types)
    ):
        raise PackageMigrationError("package_migration_fact_type_invalid")
    normalized = tuple(sorted(fact_types))
    if len(set(normalized)) != len(normalized):
        raise PackageMigrationError("package_migration_fact_type_duplicate")
    return normalized


def _parse_event_refs(payload: Mapping[str, object], field: str) -> tuple[PackageRef, ...]:
    if set(payload) != {"from", "to", "migration_ref", "affected_fact_types"}:
        raise PackageMigrationError("package_migration_payload_invalid")
    value = payload[field]
    if not isinstance(value, list):
        raise PackageMigrationError("package_migration_payload_invalid")
    refs: list[PackageRef] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"pack", "version"}:
            raise PackageMigrationError("package_migration_payload_invalid")
        try:
            refs.append(PackageRef(item["pack"], item["version"]))
        except (TypeError, PackageMigrationError) as exc:
            raise PackageMigrationError("package_migration_payload_invalid") from exc
    try:
        return _normalize_refs(refs)
    except PackageMigrationError as exc:
        raise PackageMigrationError("package_migration_payload_invalid") from exc


def _serialize_ref(ref: PackageRef) -> dict[str, str]:
    return {"pack": ref.pack_id, "version": ref.pack_version}


def _rejected(command_id: str, error_code: str) -> AppendBatchResult:
    return rejected_result(
        command_id=command_id,
        error_code=error_code,
        stage="package_migration_validation",
        transaction_prefix="transaction:package-migration",
    )
