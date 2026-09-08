# ADR-005: Postgres runs in the cluster locally and is managed in production

**Status:** Accepted
**Date:** 2026-09-01
**Depends on:** [ADR-002](0002-the-api-owns-the-database.md)

## Context

The Helm chart has to work in two places that want different things from a
database.

On a laptop, the point is that `helm install` produces a working system with no
external dependency. In production, the point is that somebody else owns
backups, failover, patching and major-version upgrades.

**Run Postgres in the cluster everywhere.** One code path, one chart, no
external prerequisite. It also means owning storage durability, backup
scheduling, restore rehearsal and the upgrade path for a stateful workload —
none of which Kubernetes helps with, and all of which are someone's full-time
job at a real organisation.

**Use a managed database everywhere.** Correct in production and hostile
locally: a chart that cannot start without a cloud account is a chart nobody
runs before deploying it.

## Decision

Both, selected by a value.

```yaml
# values.yaml
postgres:
  enabled: true

# values-prod.yaml
postgres:
  enabled: false
externalDatabase:
  host: ""            # supplied at install time
```

In-cluster Postgres is a **StatefulSet**, not a Deployment: it needs a stable
identity, an ordered lifecycle and a `volumeClaimTemplate` per replica. A
Deployment with a PVC works right up until the second replica, which then
mounts the same volume as the first.

A helper resolves the host, and `required` makes the production path fail
loudly rather than silently connecting to nothing:

```
{{- required "externalDatabase.host is required when postgres.enabled is false" .Values.externalDatabase.host -}}
```

## Consequences

**Good.** `helm install` on kind gives a complete working stack with no cloud
account. The production values decline to render at all until someone supplies
a real host, so a half-configured release fails at template time rather than at
runtime.

**Costly.** Two code paths through the chart, and a helper that exists purely to
paper over the difference. Every change touching the database has to be
considered twice, and only one of the two gets exercised on a laptop.

**The trap it sets.** This is the decision that hid three defects at once. The
in-cluster database was always created by `create_all()` via `flask seed`, so
the Alembic migration chain had **never actually run against Postgres**. When it
finally did, it failed on `sa.Text(length=255)`, on a migration that was a
MySQL-era rename doing nothing on Postgres, and on an initContainer race with
two replicas. Three real bugs, invisible because the path that would have found
them was never taken.

The general shape: a convenience that bypasses a production code path will hide
whatever is wrong in it, and the bill arrives at the worst moment.

**Also learned:** the same asymmetry applies to the test suite. It runs against
SQLite by default so a fresh clone needs no server, and CI points it at a
Postgres service container because SQLite is forgiving about type coercion,
enum handling and transactional DDL. A green SQLite run is evidence, not proof.

## Alternative left open

A Postgres operator — CloudNativePG or Zalando — would give in-cluster Postgres
with backups, failover and rehearsed restores, closing most of the gap that
makes the production path different in the first place. Deliberately not done:
it replaces one thing to understand with an operator to understand, and the
managed service is the right answer for this system's scale regardless.
