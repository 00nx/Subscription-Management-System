Developer 2 - Products, plans, quotations and subscriptions

This is a module ownership package from the Brightloop repository.

STARTING POINT
- This package contains the shared project baseline plus the assigned module folders.
- It is not a separate microservice or independently deployable application.
- Keep the existing FastAPI modular-monolith and React SPA architecture.

OWNERSHIP
backend/app/modules/products
backend/app/modules/subscriptions
backend/app/modules/quotations
frontend/src/features/products
frontend/src/features/plans
frontend/src/features/quotations
frontend/src/features/subscriptions
frontend/src/services/catalog.service.ts
frontend/src/services/product.service.ts
frontend/src/services/sales.service.ts
frontend/src/services/subscription.service.ts

SHARED FILES
Shared backend API router, model registry, core settings, schemas, migrations, frontend routes, shared components, API clients and types are included as a common baseline.
Do not replace shared files wholesale. Coordinate changes and add only your module's required registrations/routes.

GIT WORKFLOW
- Work on your assigned feature branch.
- Pull/merge the integration branch before starting and regularly.
- Submit a focused pull request to develop (or the team's agreed integration branch).
- Do not push directly to main.
- Run relevant tests and frontend typecheck/build before requesting review.

IMPORTANT
These ZIPs are ownership-based, not equal in byte size or file count. Shared files are duplicated in each ZIP deliberately to let each developer understand the app in context.
