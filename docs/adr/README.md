# Architecture decision records

One file per decision that would be expensive to reverse or hard to explain
later. Each records what was decided, what it cost, and what it did not solve --
the last of those being the part usually missing.

| # | Decision | Status |
|---|---|---|
| [0001](0001-split-the-monolith-into-services.md) | Split the monolith into four services | Accepted |
| [0002](0002-the-api-owns-the-database.md) | The api owns the database, exclusively | Accepted |
| [0003](0003-tag-driven-image-publishing.md) | Images are published by version tag, not by merge | Accepted |
| [0004](0004-container-apps-scale-to-zero.md) | Container Apps scale to zero, and the cold start is accepted | Accepted |
| [0005](0005-postgres-in-cluster-locally-managed-in-production.md) | Postgres runs in the cluster locally and is managed in production | Accepted |
| [0006](0006-alerts-describe-symptoms.md) | Alerts describe symptoms, not causes | Accepted |
| [0007](0007-the-ai-provider-is-a-seam.md) | The AI provider is a seam, and the stub is the default | Accepted |
| [0008](0008-ci-on-hosted-runners.md) | CI runs on hosted runners, and the self-hosted pipeline is kept | Accepted |

Decisions recorded elsewhere rather than as an ADR, because they are narrower
and live next to the code they affect -- see [../architecture.md](../architecture.md):

- Why the `/api` prefix is not stripped by the gateway
- Why the media endpoint is unauthenticated
- Why rewards stay write-only
- Why alpine is right for `web` and wrong for `api`
- Why OpenTelemetry was added alongside `X-Request-ID` rather than instead of it
  (in [../../deploy/README.md](../../deploy/README.md), with the rest of the observability stack)
