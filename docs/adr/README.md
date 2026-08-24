# Architecture decision records

One file per decision that would be expensive to reverse or hard to explain
later. Each records what was decided, what it cost, and what it did not solve --
the last of those being the part usually missing.

| # | Decision | Status |
|---|---|---|
| [0001](0001-split-the-monolith-into-services.md) | Split the monolith into four services | Accepted |
| [0002](0002-the-api-owns-the-database.md) | The api owns the database, exclusively | Accepted |
| [0003](0003-tag-driven-image-publishing.md) | Images are published by version tag, not by merge | Accepted |

Decisions recorded elsewhere rather than as an ADR, because they are narrower
and live next to the code they affect -- see [../architecture.md](../architecture.md):

- Why the `/api` prefix is not stripped by the gateway
- Why the media endpoint is unauthenticated
- Why rewards stay write-only
- Why alpine is right for `web` and wrong for `api`
