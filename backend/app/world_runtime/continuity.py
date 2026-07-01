from pydantic import BaseModel, ConfigDict


class RuntimeContinuityState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    ongoing_contact_target: str = ""
    interrupted_action: str = ""
    last_transition_kind: str = ""
