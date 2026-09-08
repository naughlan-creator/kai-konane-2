# ADR-006: Alerts describe symptoms, not causes

**Status:** Accepted
**Date:** 2026-09-02

## Context

Prometheus will happily alert on anything it scrapes. The question is which of
those things should wake someone.

**Alert on causes.** CPU above 80%, memory above a threshold, replica count
below expected, disk filling. These are easy to write and easy to justify one at
a time. They also fire when nothing is wrong — a batch job using the CPU it was
given — and they miss outages that involve no resource pressure at all. A
service returning 500 to every request uses very little CPU.

**Alert on symptoms.** Error rate, latency, and the specific failures a user
would notice. Harder to write, and each one has to name something a person
experiences.

The failure mode of the first approach is not false alarms as such. It is that
people learn to ignore the alerts, and then ignore the real one.

## Decision

Every rule in `deploy/k8s/monitoring/11-prometheus-config.yaml` describes
something a user would notice. Nothing alerts on CPU, memory or replica count —
those are dashboard panels.

Rules are **ratios with duration**, not counts:

```yaml
            expr: |
              sum by (component) (rate(http_requests_total{status="5xx"}[5m]))
                /
              sum by (component) (rate(http_requests_total[5m]))
                > 0.05
            for: 5m
```

Ten errors in a million requests is healthy; ten in twenty is an outage. A
count-based rule pages for the first and misses the second. Without `for`, a
single bad scrape pages someone.

Severity is `page` or `ticket`, and the distinction is whether it is worth
waking a person: sustained 5xx pages, a p95 above one second gets a ticket.

## Consequences

**Good.** The alerts that exist are ones worth reading. `KaiApiUnreachableFromWeb`
catches the failures with no HTTP status at all — timeouts, refused connections,
DNS — which a status-code metric structurally cannot see, and which are exactly
the ones that mean the api is gone rather than erroring.

**Costly.** A cause that has not yet become a symptom goes unalerted. A disk at
95% is invisible here until it fills and requests start failing. That is the
accepted trade, and it is only defensible because the dashboards exist.

**The trap it sets.** `KaiNoTraffic` — `rate(http_requests_total) == 0` — looks
obviously useful and is deliberately absent. It would fire every night on a demo
cluster nobody is using, and an alert that fires nightly trains people to close
it without reading. The rules **not** written are part of this decision, and
`11-prometheus-config.yaml` carries a section saying which and why.

**The exception that sharpens the rule.** `KaiModelPredictsOneClass` alerts on
the distribution of a model's outputs, which no user can perceive. It is here
because a model returning `BEGINNER` for every child raises nothing, logs
nothing, fails no test and returns a valid answer — the only observable
difference between a working model and a dead one is the distribution. Uptime,
latency and error rate say a model is *serving*; they cannot say it is *right*.
It has a volume floor so it stays quiet on a fresh cluster.

**Also learned:** a rule file Prometheus rejects does not crash it. Prometheus
logs the failure, **keeps the previously loaded rules**, and carries on serving
— so a bad expression and an unapplied ConfigMap look identical from the UI. CI
now runs `promtool check rules` on every pull request for exactly this reason.

## Alternative left open

Alertmanager is not deployed. Prometheus evaluates the rules and shows them
firing, and nothing routes, groups, silences or delivers them. Adding it is
routing configuration, not observability, and there is nobody to page — but the
rules are written as though there were, so the day someone is on call the rules
do not need rewriting.
