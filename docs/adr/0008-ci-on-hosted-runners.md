# ADR-008: CI runs on hosted runners, and the self-hosted pipeline is kept

**Status:** Accepted
**Date:** 2026-09-08
**Depends on:** [ADR-003](0003-tag-driven-image-publishing.md)

## Context

`azure-pipelines.yml` is a complete three-stage pipeline — lint, tests against
Postgres, tag-gated publish to GHCR — and it works. It has one structural
problem:

```yaml
pool:
  name: nolan-agent-pool
```

A self-hosted agent. It runs when that machine is on, and its results live in
Azure DevOps while the pull requests live on GitHub. CI that requires a laptop
to be powered up is a build script with a scheduler attached.

The cost was concrete. `test_the_api_serves_no_html` was broken by the
observability work — `/metrics` was added to the route list — and survived a
full day, through an entire subsequent issue, because nothing ran on the pull
request that broke it.

**Move to hosted runners.** Results land on the pull request, and Linux runners
remove a category of workaround: the manual `docker run` for Postgres, the
`for /l` polling loop, and a PowerShell step written because `script:` runs
`cmd.exe`, which has no `sed`. All three exist only because the agent is Windows.

**Delete or keep the Azure pipeline.** Two definitions can drift. One of them is
also a working example of a self-hosted agent, service connections and a
different YAML dialect.

## Decision

GitHub Actions is authoritative. Nine jobs on every pull request: `ruff`, api
tests against a Postgres service container, web tests, and — new, with no
equivalent in the old pipeline — `terraform fmt`/`validate`, `helm lint` and
render, `promtool check rules`, `kubeconform`, and all three image builds.

`azure-pipelines.yml` is kept and marked as superseded.

Branch protection is a file:

```bash
gh api --method PUT repos/.../rulesets/<id> --input .github/ruleset-main.json
```

Protection configured by clicking is a setting nobody can review, diff or
restore. As a file it goes through the same pull request as the code it protects.

## Consequences

**Good.** Nine checks gate `main`, `bypass_actors` is empty — including the
repository owner — and `strict_required_status_checks_policy` requires a branch
to be current before it merges. That last setting is what closes the specific
gap that caused this: green-on-my-branch is not green-after-merge.

The infrastructure validation is the part with no predecessor. The `helm` job
includes a **negative** test that asserts a `required` guard still fails when it
should. Every other step asserts something works.

**Costly.** Two CI definitions to keep coherent, and one of them is not run.
A README-only change also runs three Docker builds, because a required check
that is skipped blocks a merge forever rather than passing it.

**The trap it sets.** The Actions cache scope defaults to the **job name**.
Renaming the image job to produce stable check names — matrix jobs are named
after every matrix value, so `images (api, services/api)` would break the moment
anyone renamed a build context — silently moved its cache. It also revealed that
the previous name had all three matrix legs writing to one shared scope
concurrently, overwriting each other.

**Also learned:** `mode=max` exports the builder stage, which is the point of it
and wrong here. Measured:

```
#22 exporting to GitHub Actions Cache
#22 writing layer sha256:60f9ff3f... 784.6s done
#22 DONE 913.0s
```

Fifteen minutes of cache export to save a 137-second build, on an 827MB image of
numpy, scipy, pandas and scikit-learn — and three images at `max` would exceed
the 10GB repository limit and evict each other into permanent misses. `mode=min`
took the same step to 35.7s. A cache is worth only what it saves, and neither
number is knowable without measuring.

## Alternative left open

`terraform validate` never talks to Azure. It would catch a reference to a
resource that does not exist; it cannot catch what broke the first `terraform
apply` — an alert rule whose query Azure rejected with a 400 at create time.
Catching that needs `terraform plan` against a real subscription, which needs
credentials in CI, which is an OIDC federation exercise this repository has not
done. Retiring `azure-pipelines.yml` is the other open question, deferred until
the GitHub workflow has run long enough to have earned it.
