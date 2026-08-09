from __future__ import annotations

import pytest


def test_frost_farm_records_are_strict_and_owner_scoped() -> None:
    from app.gameplay.frost_farm_runtime import CropState, FarmPlot, FrostEffectInput, ResistanceProfile

    plot = FarmPlot(plot_ref="plot:frost:1", jurisdiction_ref="jurisdiction:north", owner_ref="owner:farm")
    crop = CropState(crop_ref="crop:wheat:1", plot_ref=plot.plot_ref, state="growing", health=100)
    profile = ResistanceProfile(profile_ref="resistance:wheat:v1", resistance=0.25)
    effect = FrostEffectInput(plot=plot, crop=crop, resistance=profile, frost_intensity=0.8, permission_scope="owner:farm")
    assert effect.crop.plot_ref == effect.plot.plot_ref
    with pytest.raises(ValueError, match="extra|forbid"):
        FarmPlot(plot_ref="plot:1", jurisdiction_ref="jurisdiction:1", owner_ref="owner:1", unexpected=True)
