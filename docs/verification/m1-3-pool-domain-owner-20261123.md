# Pool domain Owner principal

## Change

`PoolAuthorityService` now accepts an optional `principal_ref` alongside its Owner fragment principal. The default remains `owner:pool`. A domain caller can use the same principal in the idempotency transaction and Owner fragment so persisted transaction ownership can be verified. This enables the Production/Facility integrity writer and later Morale Pool writer to retain their domain Owner identity while reusing the Pool primitive.

The commit is listed in the thread A history alongside this evidence file.

## Verification

| Check | Result |
|---|---|
| TDD red | Facility integrity test showed the Pool transaction was not owned by `actor_gameplay.construction_production_domain` |
| Pool and facility targeted tests | 22 passed, 2 warnings |
| Permanent selection | `docs/verification/selection/m1-3-pool-domain-owner.json` |
| Full suite | Not run |

Python 3.12.2; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. Raw test output is under `F:\paralls-verification\thread-a\m6-5-facility-integrity-red-20261123\`.
