# ADR-003: Images are published by version tag, not by merge

**Status:** Accepted
**Date:** 2026-08-23
**Depends on:** [ADR-001](0001-split-the-monolith-into-services.md)

## Context

CI builds three images. The question is when they should reach a registry where
something might deploy them.

**Publish on every merge to `main`.** The registry always holds the newest code.
Deployment is a pull away. But `latest` then means "whatever merged most
recently", and two machines pulling it an hour apart can be running different
code with no way to tell.

**Publish on a version tag.** The registry holds only what someone chose to
release. `main` is still linted, tested and image-built on every push, so
breakage is caught immediately — it simply does not produce an artefact.

## Decision

The pipeline's Publish stage is gated:

```yaml
condition: and(succeeded(),
               startsWith(variables['Build.SourceBranch'], 'refs/tags/v'))
```

A push to `main` runs lint, tests and image builds, then skips Publish. A `v*`
tag runs everything and pushes `api`, `web` and `gateway` to GHCR tagged with
both the version and `latest`.

`compose.prod.yaml` requires `IMAGE_TAG` with **no default**. A `latest`
fallback would quietly undo the point: a deployment that cannot say which commit
it is running is a guess.

## Consequences

**Good.** Every deployable artefact corresponds to a tag, which corresponds to a
commit. "What is running?" has an answer. Releasing is a deliberate act with a
version attached rather than a side effect of clicking Merge.

**Costly.** The registry lags `main` by design. Deploying an unreleased fix
means cutting a tag, even a throwaway one — `v0.9.0-rc1` through `-rc4` exist
purely because publishing had to be exercised before `v1.0.0` was earned.

**The trap it sets.** A skipped stage looks much like a passed one in the Azure
DevOps UI — a pale tile rather than a red one. A `main` build reporting "success"
with Publish skipped was initially read as "the images were pushed", and the
registry stayed empty. The stage view says `Condition was not met`; it is worth
reading rather than glancing at.

**Also learned:** tags are cheap to move until something consumes them. A tag
pointing at an unmerged branch, or one commit early, is fixed by deleting and
re-tagging. Once a deploy has pulled `api:1.0.0`, that tag is immutable in
practice and the next release takes a new number — otherwise one version string
means different code on different machines, which is precisely what versioning
exists to prevent.

## Alternative left open

Publishing an `edge` tag on every `main` build, alongside semantic versions for
releases, would give a deployable image per merge without letting `latest` drift
from a released version. Deliberately not done: for this project, a deploy should
name the version it wants.
