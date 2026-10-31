# Contributing

## Four-member split

| Member | Branch | Backend | Frontend |
|---|---|---|---|
| 1. Auth & users | `feature/authentication` | `modules/accounts`: registration, login, JWT, role permissions, user management | `features/auth`, `features/users`, profile |
| 2. Products & subscriptions | `feature/products-subscriptions` | `modules/products`, `subscriptions`, `quotations` (products, variants, plans, subscriptions, quotations) | `features/products`, `plans`, `subscriptions`, `quotations` |
| 3. Billing & payments | `feature/billing-payments` | `modules/billing`, `invoices`, `payments`, `discounts` (taxes live in billing) | `features/invoices`, `payments`, `discounts`, billing UI |
| 4. Dashboard & integration | `feature/dashboard-analytics` | `modules/analytics`: reports, dashboard endpoints | `features/dashboard`, `reports`, charts, shared components, integration tests |

Member 4 **coordinates** integration (keeps `develop` green, runs the cross-module tests, chairs contract discussions) but integration problems are fixed by the member who owns the failing code, not by Member 4 alone.

## Branching

`main` (releasable) ← `develop` (integration) ← feature branches above (and short-lived `feature/<module>-<topic>` branches off them).
Never push directly to `main` or `develop`; open a pull request. Feature branches should merge `develop` in regularly.

## Commits

Conventional style: `feat(products): add variant model`, `fix(auth): reject expired refresh token`, `docs: ...`, `test: ...`, `chore: ...`. Scope = module. One logical change per commit.

## Pull requests

- Target `develop`; small and focused; describe what and why; link the issue.
- Must have passing backend (`pytest`) and frontend (`npm test`, `npm run typecheck`) checks, plus tests for new behaviour.
- At least one review, from a member of a different module when you touch shared code.
- New tables need an Alembic migration you have actually run (`alembic upgrade head` on a fresh DB).

## Shared contracts and boundaries

- Follow `docs/API.md` (envelope, pagination, auth). API shape changes are announced in the PR and update `docs/API.md`.
- Stay inside your module. Changes to `core/`, `schemas/common.py`, `services/api.ts`, `components/ui` or `components/shared` need agreement from the others (shared-component changes go through Member 4).
- Shared files you'll all touch (`api/v1/router.py`, `models/registry.py`, `routes/AppRoutes.tsx`, `routes/nav.ts`): add your lines only, keep them alphabetical or grouped by module to limit conflicts.
- Money is `Decimal`/`NUMERIC`, never float.

## Resolving merge conflicts

1. `git fetch origin && git checkout feature/yours && git merge origin/develop` (merge, don't rebase a shared branch).
2. Open each conflicted file; keep **both** sides' intent (typically both added lines in a shared router/registry). Never resolve by discarding the other person's change without talking to them.
3. Alembic: two heads is a conflict too. Run `alembic heads`; if there are two, `alembic merge -m "merge heads" <rev1> <rev2>` and commit the result. Never edit an already-merged migration.
4. `package-lock.json`: take `develop`'s version, then re-run `npm install` and commit.
5. Run the backend and frontend tests before pushing the merge. If the conflict is in someone else's module, ask them to confirm.
