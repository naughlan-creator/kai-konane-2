"""Talking to a language model, as a dependency rather than a feature.

not training models but to running the plaform models sit on.
  : provisioning endpoints, holding keys, enforcing quotas, watching
    the bill, keeping latency survivable, making failure graceful, and
    stopping the model being an exfiltration route.

All of which is ordinary dependency management applied to something unusually 
expensive, unusually slow and non-deterministic. The novelty is in those three
adjectives and this file is where each on is handled.
"""
import hashlib
import logging
import os
import random
import time

logger = logging.getLogger(__name__)

# --- limits, all overridable from the environment ---

# Generation takes SECONDS. web's global API_TIMEOUT_S is 10, so an AI route
# behind that timeout is a guaranteed 504 -- the AI call needs its own budget,
# and web needs a longer one for this route only.
TIMEOUT_S = float(os.getenv('AI_TIMEOUT_S', '30'))

MAX_ATTEMPTS = int(os.getenv('AI_MAX_ATTEMPTS', '3'))

# Cost scales with input length, and input length is controlled by the user.
# Rejected rather than truncated: silent truncation produces confidently wrong
# output from half a question, which is worse than a clear refusal.
MAX_PROMPT_CHARS = int(os.getenv('AI_MAX_PROMPT_CHARS', '4000'))

MAX_OUTPUT_TOKENS = int(os.getenv('AI_MAX_OUTPUT_TOKENS', '600'))

# Circuit breaker. If the endpoint is failing, calling it 200 more times helps
# nobody and costs money.
BREAKER_THRESHOLD = int(os.getenv('AI_BREAKER_THRESHOLD', '5'))
BREAKER_COOLDOWN_S = float(os.getenv('AI_BREAKER_COOLDOWN_S', '60'))


class AiUnavailable(Exception):
    """The model could not be reached or refused to answer. 
    
    Deliberately NOT a ServiceError subclass. A ServiceError maps to an HTTP 
    status and means the request was wrong; this means our dependency is down, 
    and the caller's job is to degrade rather than to report a 4xx.
    """


class AiRejected(Exception):
    """The request was refused before any call was made -- too long, empty, 
    or otherwise ours to reject. This one IS the caller's fault."""


class Completion:
    """What a provider returns. A small class rather than a dict so the fields 
    that cost money are named and cannot be silently forgotten."""

    def __init__(self, text, prompt_tokens=0, completion_tokens=0,
                 model='unknown', cached=False):
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model = model
        self.cached = cached

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens


# --- circuit breaker ---

class _Breaker:
    """Three variables and a timestamp. 
    
    No library: writing it means being able to explain it and the whole 
    behaviour is 'after N consecutve failures, stop calling for a while, then 
    let exactly one request through to test'.
    
    Per-process, which is a real limitation worth naming: with 2 gunicorn 
    workers each keeps its own count, so the effective threshold is 2xN across 
    the pod. Correct sharing needs Redis, and is not worth it at this size.
    """

    def __init__(self):
        self.failures = 0
        self.opened_at = None

    def is_open(self):
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= BREAKER_COOLDOWN_S:
            # Half-open: let one through. If it fails, record() re-opens.
            self.opened_at = None
            self.failures = BREAKER_THRESHOLD - 1
            return False
        return True

    def record(self, ok):
        if ok:
            self.failures = 0
            self.opened_at = None
            return
        self.failures += 1
        if self.failures >= BREAKER_THRESHOLD:
            self.opened_at = time.monotonic()
            logger.warning('ai circuit breaker opened', extra={'context': {
                'failures': self.failures, 'cooldown_s': BREAKER_COOLDOWN_S}})


_breaker = _Breaker()


# --- providers ---

class Provider:
    """The seam. Everything above this line is policy; below it is transport."""

    name = 'base'

    def complete(self, system, user, max_tokens):
        raise NotImplementedError


class StubProvider(Provider):
    """A deterministic provider, used when AI_PROVIDER is unset. 
    
    This is the default on purpose, and it is not a placeholder. It makes the 
    timeout, retry, budget, breaker and injection paths testable with no cloud 
    account and no per-token bill -- and those paths are the part that actually 
    breaks. Model output is non-deterministic; the plumbing around it is notm 
    and should be tested as the deterministic thing it is.
    """

    name = 'stub'

    def complete(self, system, user, max_tokens):
        # Deterministic from the input, so a test can assert on it and the 
        # cache has something meaningful to key.
        seed = hashlib.sha256(user.encode()).hexdigest()[:8]
        text = (
            f"Once upon a time there was a small brave explorer who lived "
            f"beside a wide blue river. One morning they found a puzzle box "
            f"washed up on the bank, tied with string and covered in sand. "
            f"They tried to open it once, and then twice, and then a third "
            f"time, but the lid would not move. So they asked a friend to "
            f"help, and together the two of them lifted the lid and found a "
            f"tiny paper boat inside. They set it on the water and watched "
            f"it sail away. Some things are easier when you ask. "
            f"[stub:{seed}]"
        )
        return Completion(
            text=text,
            # Rough: 4 chars per token. Enough to exercise the accounting.
            prompt_tokens=len(system + user) // 4,
            completion_tokens=len(text) // 4,
            model='stub-v1',
        )


class AzureOpenAIProvider(Provider):
    """Azure AI Foundry over plain HTTP. 
    
    'requests' rather than the openai SDK: one POST, and the SDK would add a 
    dependency plus its own retry logic competing with the one above.
    """

    name = 'azure'

    def __init__(self):
        self.endpoint = os.environ['AI_ENDPOINT'].rstrip('/')
        self.deployment = os.getenv('AI_CHAT_DEPLOYMENT', 'chat')
        self.api_version = os.getenv('AI_API_VERSION', '2024-10-21')
        self.api_key = os.environ['AI_API_KEY']

    def complete(self, system, user, max_tokens):
        import requests

        url = (f'{self.endpoint}/openai/deployments/{self.deployment}'
               f'/chat/completions?api-version={self.api_version}')
        response = requests.post(
            url,
            headers={'api-key': self.api_key},
            json={
                'messages': [
                    # The separation that matters: instructions are a SYSTEM
                    # message, user content is a USER message. Never
                    # concatenated. See prompts.py.
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
                'max_tokens': max_tokens,
                'temperature': 0.8,
            },
            timeout=TIMEOUT_S,
        )

        # 429 is the QUOTA WORKING, not an error. Raised so the retry logic
        # above can back off; capacity is measured in tokens per minute and
        # exceeding it is expected behaviour, not a fault.
        response.raise_for_status()

        body = response.json()
        usage = body.get('usage', {})
        return Completion(
            text=body['choices'][0]['message']['content'],
            prompt_tokens=usage.get('prompt_tokens', 0),
            completion_tokens=usage.get('completion_tokens', 0),
            model=body.get('model', self.deployment),
        )


def get_provider():
    """Chosen by environment. Stub unless told otherwise -- so a missing
    AI_ENDPOINT degrades to a working stub rather than a crash at import."""
    kind = os.getenv('AI_PROVIDER', 'stub').lower()
    if kind == 'azure':
        return AzureOpenAIProvider()
    return StubProvider()


# --- the policy layer ---

def _retryable(exc):
    """429 and 5xx are worth retrying. A 400 is not -- the request is wrong and 
    will be wrong again, so retryinh just spends money three times."""
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status is None:
        # timeout, DNS, refused connection
        return True
    return status == 429 or status >= 500


def _retry_after(exc, attempt):
    """Honour Retry-After when the service sends one; otherwise exponential
    backoff WITH JITTER.

    The jitter is not decoration. Without it, every client that failed at the
    same moment retries at the same moment, and one throttle becomes a
    stampede that keeps the endpoint throttled.
    """
    header = getattr(getattr(exc, 'response', None), 'headers', {}) or {}
    try:
        return float(header['Retry-After'])
    except (KeyError, TypeError, ValueError):
        return (2 ** attempt) * 0.5 + random.uniform(0, 0.5)


def complete(system, user, max_tokens=None):
    """Call the model with every guard applied.

    Raises AiRejected for our refusals, AiUnavailable for everything else --
    so the caller has exactly two cases to handle.
    """
    if not user or not user.strip():
        raise AiRejected('Nothing to generate from.')

    if len(user) > MAX_PROMPT_CHARS:
        raise AiRejected(
            f'That request is too long ({len(user)} characters, limit '
            f'{MAX_PROMPT_CHARS}). Please shorten it.')

    if _breaker.is_open():
        raise AiUnavailable('The story service is resting. Try again shortly.')

    provider = get_provider()
    max_tokens = max_tokens or MAX_OUTPUT_TOKENS
    last = None

    for attempt in range(MAX_ATTEMPTS):
        started = time.perf_counter()
        try:
            result = provider.complete(system, user, max_tokens)
            _breaker.record(ok=True)

            # Everything that costs money, as queryable fields. Cost is
            # invisible unless it is measured, and it scales with input length,
            # which users control.
            logger.info('ai completion', extra={'context': {
                'provider': provider.name,
                'model': result.model,
                'prompt_tokens': result.prompt_tokens,
                'completion_tokens': result.completion_tokens,
                'duration_ms': round((time.perf_counter() - started) * 1000, 1),
                'attempt': attempt + 1,
            }})
            return result

        except Exception as exc:
            last = exc
            if not _retryable(exc) or attempt == MAX_ATTEMPTS - 1:
                _breaker.record(ok=False)
                break
            delay = _retry_after(exc, attempt)
            logger.warning('ai call failed, retrying', extra={'context': {
                'attempt': attempt + 1, 'retry_in_s': round(delay, 2),
                'error': type(exc).__name__}})
            time.sleep(delay)

    _breaker.record(ok=False)
    logger.error('ai call failed', extra={'context': {
        'attempts': MAX_ATTEMPTS, 'error': str(last)[:200]}})
    raise AiUnavailable('The story service is unavailable right now.') from last
