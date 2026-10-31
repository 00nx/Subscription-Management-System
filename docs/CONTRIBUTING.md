# Contributing

## Module ownership (four members)

| Member | Branch | Backend | Frontend |
|---|---|---|---|
| 1. Auth, users & customers | `feature/authentication` | `accounts`, `customers`: auth, JWT, roles, notifications, customer profiles | `features/auth`, `users`, `customers`, `notifications`, profile |
| 2. Products, plans & subscriptions | `feature/products-subscriptions` | `products`, `subscriptions`, `quotations`: products/variants, plans, quotations, lifecycle, renewal/cancellation | `features/products`, `plans`, `subscriptions`, `quotations` |
| 3. Billing & payments | `feature/billing-payments` | `billing`, `discounts`, `invoices`, `payments`, `tasks/billing_tasks.py` | `features/invoices`, `payments`, `discounts`, `billing`, invoice PDF |
| 4. Dashboard & integration | `feature/dashboard-analytics` | `analytics`: dashboard, reports, audit log | `features/dashboard`, `reports`, `components/shared`, integration tests |

Member 4 **coordinates** integration (keeps `develop` green, runs cross-module tests) but cross-module bugs are fixed by whoever owns the failing code. Everyone writes tests for their module and joins integration testing.

## Branching

`main` (releasable) ← `develop` (integration) ← feature branches above (and short-lived `feature/<module>-<topic>`). Never push to `main`/`develop` directly: open a pull request. Merge `develop` into your branch regularly.

## Commits and PRs

Conventional commits: `feat(billing): …`, `fix(auth): …`, `docs`, `test`, `chore`; scope = module. PRs target `develop`, stay focused, describe what/why, and need: a clean `npm run typecheck`; an Alembic migration you actually ran (`alembic upgrade head` on a fresh DB) when tables change; an updated `docs/API.md` section when endpoints change; one review (from another module's owner when you touch shared code).

## Shared contracts

- **Money is `Decimal`/`NUMERIC(12,2)`, never float.** API money values are strings. Round with `app.core.money.q` (half-up).
- Dates are UTC `DATE`/timestamptz. Status enums live in `app/core/enums.py`: don't redefine them.
- Response envelope, pagination and error format: see `docs/API.md`. Use `ApiResponse`, `Page`, `PageParams`, `paginate`.
- Authorisation: `Depends(require_roles(...))` / `get_current_user`. Customer-visible data must filter through `scope_customer_id`/`assert_owns`. Never trust a client-provided role, user id, customer id or payment status.
- Financial writes: one transaction, row locks where concurrent (`with_for_update`), idempotent where retried. Write an audit row (`record_audit`) for important changes; never log secrets.
- Shared files you will all touch (`api/v1/router.py`, `models/registry.py`, `routes/AppRoutes.tsx`, `routes/nav.ts`): add only your lines to limit conflicts. Changes to `core/`, `schemas/common.py`, `services/api.ts`, `components/ui` or `components/shared` need agreement from the others.

## Resolving merge conflicts

1. `git fetch origin && git checkout feature/yours && git merge origin/develop` (merge; don't rebase shared branches).
2. Keep **both** sides' intent in shared routers/registries. Never discard someone's change without talking to them.
3. Alembic: two heads is a conflict. `alembic heads`; if two, `alembic merge -m "merge heads" <rev1> <rev2>` and commit. Never edit an already-merged migration.
4. `package-lock.json`: take `develop`'s, run `npm install`, commit.
5. Re-run backend and frontend tests before pushing the merge.

## Running the checks

```bash
cd frontend && npm test && npm run typecheck
```
