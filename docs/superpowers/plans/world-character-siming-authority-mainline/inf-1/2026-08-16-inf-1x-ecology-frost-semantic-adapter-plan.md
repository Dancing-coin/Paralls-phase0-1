# INF-1X Ecology Frost Semantic Adapter Plan

Status: `implemented and verified closed Ecology owner row; generic adapter remains incomplete`

1. Completed: add focused source-relation and zero-write tests.
2. Completed: add only the closed command model and semantic-to-Ecology envelope mapper.
3. Completed: keep all canonical validation and append in `EcologyHazardAuthority`.
4. Completed: independent Harness selectors prove success,
   relation/privacy/revision/idempotency rejection and replay. The docs gate,
   `git diff --check`, and repository-root `python -m pytest -q` also pass.
