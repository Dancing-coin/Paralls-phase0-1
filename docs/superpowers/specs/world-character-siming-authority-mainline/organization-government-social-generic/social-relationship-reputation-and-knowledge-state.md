# Social Relationship, Reputation And Knowledge State

Status: `implementation-authorized`

Date: `2026-09-03`

SocialFactAuthority owns relationship, reputation and knowledge state.
The state machine is `observed -> recorded -> visible -> hidden -> revoked`.
Reputation is a deterministic projection of visible facts.

Writes use `gameplay.social.relationship`. Public facts stay separate from
private character memory and from Government notice facts. No generic social
writer, reputation router or second social runtime is introduced.

