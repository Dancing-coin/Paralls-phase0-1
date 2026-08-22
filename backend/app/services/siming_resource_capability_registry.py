from app.models.siming_resource_capability import (
    ResourceCapabilityPackage,
    ResourceMatch,
    ResourceRealizationRequest,
)


class ResourceCapabilityRegistry:
    FATIGUE_WINDOW = 5

    def __init__(self) -> None:
        self._packages: dict[str, ResourceCapabilityPackage] = {}
        self._recent_signatures: list[str] = []
        self.register(
            ResourceCapabilityPackage(
                capability_id="main_demo_throne_room",
                asset_bundle="main_demo_throne_room",
                scene_refs=["scenes/phase0/MainDemo.tscn"],
                actor_ids=["char_b", "char_c"],
                object_ids=["obj_letter"],
                environment_ids=["env_lamp"],
                realization_keys=["look_at_target", "focus_attention"],
                semantic_purposes=["evidence_reveal", "private_confrontation"],
                load_cost=0.0,
                loaded=True,
                cooldown_until=0,
            )
        )

    def register(self, package: ResourceCapabilityPackage) -> None:
        if package.capability_id in self._packages:
            raise ValueError(f"resource capability {package.capability_id!r} already registered")
        self._packages[package.capability_id] = package

    def set_cooldown(self, capability_id: str, *, until: int) -> None:
        package = self._packages.get(capability_id)
        if package is None:
            raise ValueError(f"unknown resource capability {capability_id!r}")
        self._packages[capability_id] = package.model_copy(
            update={"cooldown_until": until}
        )

    def match(
        self,
        request: ResourceRealizationRequest,
        *,
        world_ts: int,
    ) -> ResourceMatch:
        covered = [
            package
            for package in self._packages.values()
            if self._covers(package, request, world_ts)
        ]
        ranked = sorted(
            covered,
            key=lambda package: (
                self._fatigue(package, request),
                package.load_cost,
                0 if package.loaded else 1,
                package.capability_id,
            ),
        )
        if not ranked:
            return ResourceMatch(accepted=False, reason="resource_unavailable")
        selected = ranked[0]
        return ResourceMatch(
            accepted=True,
            capability=selected,
            realization_signature=request.signature(selected.asset_bundle),
            fatigue_penalty=self._fatigue(selected, request),
        )

    def record_realization(
        self,
        request: ResourceRealizationRequest,
        asset_bundle: str,
        *,
        world_ts: int,
    ) -> None:
        del world_ts
        if asset_bundle not in {
            package.asset_bundle for package in self._packages.values()
        }:
            raise ValueError(f"unknown resource asset bundle {asset_bundle!r}")
        self._recent_signatures.append(request.signature(asset_bundle))
        self._recent_signatures = self._recent_signatures[-self.FATIGUE_WINDOW :]

    @staticmethod
    def _covers(
        package: ResourceCapabilityPackage,
        request: ResourceRealizationRequest,
        world_ts: int,
    ) -> bool:
        return (
            world_ts >= package.cooldown_until
            and set(request.actor_bindings.values()).issubset(package.actor_ids)
            and (
                request.target_object_id is None
                or request.target_object_id in package.object_ids
            )
            and (
                request.target_environment_id is None
                or request.target_environment_id in package.environment_ids
            )
            and set(request.required_realization_keys).issubset(package.realization_keys)
            and request.semantic_purpose in package.semantic_purposes
        )

    def _fatigue(
        self,
        package: ResourceCapabilityPackage,
        request: ResourceRealizationRequest,
    ) -> float:
        return float(
            self._recent_signatures.count(request.signature(package.asset_bundle))
        )
