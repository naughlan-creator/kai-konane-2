# ADR-007: The AI provider is a seam, and the stub is the default

**Status:** Accepted
**Date:** 2026-09-07

## Context

`POST /api/ai/story` calls a language model. That dependency is slow, priced per
use, occasionally wrong, occasionally down, and reachable by text a user typed.

**Call the provider's SDK directly from the view.** Fewer files, and the code
reads like the documentation. Every guard around the call — timeout, retry,
backoff, circuit breaker, budget, output validation, fallback — is then only
exercisable against the real provider, which means it is exercised for the first
time in production, and every test run costs money.

**Put an interface in front of it.** One more indirection, and the guards become
testable against something that never leaves the process.

The second is only worth it if the stub is the **default** rather than a test
fixture. A seam whose fake implementation is opt-in is a seam nobody exercises.

## Decision

`Provider` has one method. `StubProvider` and `AzureOpenAIProvider` implement
it, and `AI_PROVIDER` selects. The default is `stub`, in the chart and in the
application.

Terraform gates the account itself:

```hcl
variable "enable_ai" {
  default = false
}
```

Every resource in `ai.tf` is `count = var.enable_ai ? 1 : 0`. Turning this into
something that costs money takes three separate deliberate acts: enable it in
Terraform, point the chart at it with a key, and have someone request a story.

The Azure deployment is named `chat`, not after a model, so changing models is a
`.tfvars` edit rather than an application change.

## Consequences

**Good.** Nineteen tests exercise timeout, retry classification, backoff,
`Retry-After`, the circuit breaker, the per-child cache, budget accounting,
injection detection, output validation and graceful degradation — with no cloud
account and no per-token bill. `test_rejection_costs_nothing` asserts that a
rejected theme never reaches the provider by **counting provider calls**, because
the response looks identical either way.

Data minimisation is testable for the same reason:
`test_child_name_is_not_sent_to_the_model` inspects the outgoing payload. The
model receives age band, level and interests — no name, no id, no parent — which
under POPIA matters because the provider is a third party in another
jurisdiction and this is a cross-border transfer of children's personal
information.

**Costly.** The stub has to be a plausible response, not a placeholder. It was
first written at 27 words and failed `validate_story`'s 40-word minimum — the
component rejecting its own default. A stub that does not satisfy the system's
own contract tests nothing.

**The trap it sets.** Layered guards can be layered in the wrong order. The
4000-character prompt limit sat downstream of `clean_theme()`, which truncates
to 200 characters, so the "reject rather than truncate" rule could never fire.
Three failing tests found it. The limit now runs against the raw theme in the
endpoint: **a guard placed after the thing it guards against is decoration.**

**Also learned:** graceful degradation is invisible to every HTTP metric. When
the provider is unreachable the endpoint returns a fallback story with status
200 — no request failed, no 5xx appeared, and nothing in the request metrics
moved. Silent fallback is a feature; silent fallback nobody knows about is an
outage that never gets reported, which is why `ai_requests_total{outcome}` and
`KaiAiDegraded` exist.

## Alternative left open

**Streaming** is the better experience and changes the failure model entirely: a
response already being displayed cannot be validated before the user sees it, so
`validate_story()` would have nothing to guard. **Keyless authentication** is one
step away — the managed identity already holds `Cognitive Services OpenAI User`
alongside the key it does not use, so moving off the key is a client change
only. **A prompt registry** and **evaluation** are both absent; the second is the
largest real gap, since shape is validated and quality is not.
