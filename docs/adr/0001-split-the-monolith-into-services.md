# ADR-001: Split the monolith into four services

**Status:** Accepted
**Date:** 2026-08-20
**Supersedes:** —

## Context

Kai Konane began as a single Flask application: routes, templates, models and
domain logic in one package, one process, one deployable. It worked, and for a
codebase this size it would have kept working.

Three things pushed against keeping it:

- The presentation layer and the domain had already separated *logically*.
  Routes called service classes and never touched the ORM directly, so the seam
  existed in the code before it existed in the deployment.
- The api's dependency list is dominated by scikit-learn, scipy, numpy and
  pandas — about 440 MB — needed only to unpickle one saved model. The UI needs
  none of it, but a single deployable makes every replica pay for it.
- A portfolio project that claims service-oriented design should be able to show
  the boundary being enforced, not asserted.

The alternative considered seriously was **leaving it as a monolith and
documenting the internal seam**. That is the right answer for many projects this
size, and it was rejected on the third point rather than the first two.

## Decision

Four services behind an nginx gateway:

| Service | Owns |
|---|---|
| `gateway` | Routing. `/api/*` to api, everything else to web |
| `web` | Templates, sessions, forms. No ORM, no database connection |
| `api` | The domain, the schema, the migrations |
| `db` | PostgreSQL |

`web` reaches `api` only over HTTP, through a single module (`app/api_client.py`).
The boundary is enforced by a test in each service rather than by convention:
`test_the_api_serves_no_html` asserts the api's only non-`/api` routes are the
health endpoints, and `web`'s suite runs with the api stubbed out entirely —
which it could not do if it reached into a database.

## Consequences

**Good.** `web` ships four dependencies and a 116 MB image against the api's 799
MB. The split is what makes that possible; no Docker technique comes close to
the same saving. Each service can be tested, and fails, independently.

**Costly.** One internal HTTP hop per request to rehydrate the session user.
Two test suites, two dependency sets, two images to build. A change spanning
presentation and domain is now two commits in two directories.

**Surprising.** The split introduced a class of bug that does not exist in a
monolith: things that are correct in every service and wrong between them. Four
of them appeared only in Azure and passed every local check — startup DNS
resolution, Host-based dispatch, HTTP-to-HTTPS redirects on internal ingress,
and an nginx entrypoint script silently opting out. Each was invisible under
compose because Docker's networking is more forgiving than a managed ingress.

The lesson worth carrying: **"it runs in compose" tells you the application is
correct, not that the deployment is.**

**Reversible?** Partly. The services could be recombined by importing `api`'s
package into `web` again, but the JSON contract, the token auth and the
per-object authorisation would all become redundant machinery. In practice this
is a one-way door.
