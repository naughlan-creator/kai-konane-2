# ADR-004: Container Apps scale to zero, and the cold start is accepted

**Status:** Accepted
**Date:** 2026-08-28
**Depends on:** [ADR-001](0001-split-the-monolith-into-services.md)

## Context

Azure Container Apps includes a monthly free grant of 180,000 vCPU-seconds. A
replica that is always running consumes 2,592,000 vCPU-seconds a month at 1
vCPU, or 648,000 at the 0.25 vCPU this project uses.

**Keep one replica of each app warm.** Every request is fast. `api` and
`gateway` alone come to 1,944,000 vCPU-seconds — about eleven times the free
grant — for a system nobody is browsing at 3am.

**Scale to zero.** Nothing runs when nothing is asked for, and the bill for an
idle month is nothing. The first request after an idle period pays for a
container to start.

The second option is only tolerable if the cold start is understood, and for
this architecture it is worse than it first appears: the gateway must start
before it can proxy to `web`, which must start before it calls `api`. The starts
are **serial**, not parallel.

## Decision

Every app scales to zero. `min_replicas` is a variable with no floor:

```hcl
  # No floor. A replica pinned at 1 bills for every second of the month whether
  # or not anyone visits.
  min_replicas = var.min_replicas
  max_replicas = var.max_replicas
```

An earlier version wrote `max(var.min_replicas, 1)`, which silently prevented
the thing the variable existed to allow.

Sizing is the smallest pair Container Apps accepts:

```hcl
  cpu    = 0.25
  memory = "0.5Gi"
```

Not a style choice — the service only accepts specific cpu/memory combinations,
and 0.5/1Gi is the point at which the free grant stops covering the workload.

## Consequences

**Good.** An idle month costs nothing, so the environment can exist between
demos instead of being destroyed and rebuilt. The whole deployment fits inside
the free tier, which is what made it possible to apply, inspect and destroy it
for real rather than describe it.

**Costly.** The first request after idle waits for three containers in sequence.
For a demo this is the difference between "here is the app" and thirty seconds
of explaining what the browser is doing.

**The trap it sets.** A cold start is indistinguishable from a broken deployment
if you do not know to expect it. The mitigation is knowing the flag exists:
`min_replicas = 1` in `terraform.tfvars` before a demo, and back to 0 after. A
setting you have to remember is a weak control, and it is the honest description
of this one.

**Also learned:** the 0.25 vCPU ceiling is what makes the level-prediction model
a sizing question rather than an implementation detail. It loads a joblib
artefact and sits just under a second, which is why
`http_request_duration_seconds` carries an explicit 0.75s bucket boundary — a
default bucket set would put that endpoint and a healthy one in the same bucket.

## Alternative left open

Container Apps supports "always ready" replicas as a distinct concept from
minimum replicas, and a scheduled scale-up before a known demo window would give
warm starts without paying for a warm month. Both were left undone because the
variable already expresses the trade, and a schedule is another thing that can
be wrong at the moment it matters.
