class WorldFactRegistry:
    _ROUTES = {
        "visual_fact": "visual",
        "auditory_fact": "auditory",
        "spatial_access_fact": "spatial_access",
        "role_state_fact": "authority_role_state_fact",
        "physiology_state_fact": "authority_physiology_fact",
        "tactile_fact": "authority_tactile_fact",
        "thermal_fact": "authority_thermal_fact",
        "olfactory_fact": "authority_olfactory_fact",
        "raw_fact": "raw",
        "world_result": "world_result",
    }

    def route_for_family(self, family: str) -> str:
        return self._ROUTES.get(family, "unknown")
