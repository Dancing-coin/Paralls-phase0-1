# Government Notice, Acknowledgment And Resolution State

Status: `implementation-authorized`

Date: `2026-09-03`

Government owns notice, acknowledgment and resolution state. The state
machine is `drafted -> issued -> acknowledged -> disputed -> resolved ->
archived`. Public notices remain distinct from social facts.

Writes use `gameplay.government.notice` and are replayed through exact
owner-scoped streams. No public social writer, broadcast coordinator or
government-wide message router is admitted.

