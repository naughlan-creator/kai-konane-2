"""The AI endpoints.

Mounted under /api like every other feature blueprint, and separate from api_bp
because this is the one part of the service that calls something outside the
process.

Every route is authenticated and authorised. An AI endpoint is not exempt --
an unauthenticated one is a bill anyone on the internet can run up, and that is
a availability problem as much as a cost one: burn the token-per-minute quota
and the feature is down for legitimate users too.
"""
import hashlib
import logging
import time

from flask import Blueprint, jsonify, request

from app.ai import prompts
from app.ai.provider import AiRejected, AiUnavailable, complete
from app.api.auth_seam import token_required
from app.api.authz import current_user_id

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


# --- cache ---
#
# The same theme from 20 children costs 20 times. Hashing the normalised theme
# means "space rockets" and " Space Rockets " share an entry.
#
# In-process and unbounded-ish, which is a deliberate simplification with two 
# named limitations: each gunicorn worker keeps its own copy (so the hit rate
# is worse than it looks), and it does not survive a restart. Redis is the 
# correct answer at any real scale; at this size it would be more moving parts
# than the problem justifies.
_CACHE = {}
_CACHE_TTL_S = 3600
_CACHE_MAX = 500


def _cache_key(theme):
    return hashlib.sha256(prompts.clean_theme(theme).lower().encode()).hexdigest()


def _cache_get(key):
    hit = _CACHE.get(key)
    if not hit:
        return None
    text, stored_at = hit
    if time.monotonic() - stored_at > _CACHE_TTL_S:
        _CACHE.pop(key, None)
        return None
    return text


def _cache_put(key, text):
    if len(_CACHE) >= _CACHE_MAX:
        # Crude eviction: drop the oldest. An LRU would be better and needs
        # OrderedDict; this is enough to stop unbounded growth, which is the
        # only property that actually matters here.
        oldest = min(_CACHE, key=lambda k: _CACHE[k][1])
        _CACHE.pop(oldest, None)
    _CACHE[key] = (text, time.monotonic())


# --- fallback ---

FALLBACK_STORY = (
    "Today the sky was full of clouds shaped like animals. A small child "
    "watched them drift and gave each one a name. When the wind changed, the "
    "animals turned into boats, and then into mountains. The child waved "
    "goodbye to every shape and promised to look again tomorrow. Some things "
    "are best enjoyed while they last."
)


@ai_bp.post('/story')
@token_required
def generate_story():
    """Generate a short story from a theme.

    Degrades rather than fails. The model WILL be unavailable sometimes, and
    unlike the database that must not be an outage -- this is a nice-to-have
    feature on a page that has other content. web's user_loader already applies
    the same principle to an api outage.
    """
    payload = request.get_json(silent=True) or {}
    theme = payload.get('theme', '')
    
    raw = (theme or '').strip()
    if not raw:
        return jsonify(error='Please choose a theme for the story.'), 400
    if len(raw) > prompts.MAX_THEME_CHARS:
        return jsonify(
            error=f'That theme is too long ({len(raw)} characters, limit '
                  f'{prompts.MAX_THEME_CHARS}). Please shorten it.'), 400

    # Logged, not blocked -- see prompts.looks_like_injection on why. This is
    # how "someone is probing the model" becomes visible instead of invisible.
    if prompts.looks_like_injection(theme):
        logger.warning('possible prompt injection', extra={'context': {
            'user_id': current_user_id(),
            'theme_prefix': prompts.clean_theme(theme)[:80],
        }})

    key = _cache_key(theme)
    cached = _cache_get(key)
    if cached:
        return jsonify(story=cached, source='cache'), 200

    system, user = prompts.build_story_prompt(theme)

    try:
        result = complete(system, user)
    except AiRejected as exc:
        # Our refusal: too long, or empty. The caller's fault, so a 400.
        return jsonify(error=str(exc)), 400
    except AiUnavailable:
        # Their fault, or nobody's. 200 with a fallback and an honest `source`,
        # NOT a 503 -- the page should still render something a child can read.
        # The field is what lets web say "our storyteller is resting" rather
        # than passing off the fallback as generated.
        logger.info('serving fallback story', extra={'context': {
            'user_id': current_user_id()}})
        return jsonify(story=FALLBACK_STORY, source='fallback'), 200

    story = prompts.validate_story(result.text)
    if story is None:
        # The model answered, but with something the wrong shape. Counted
        # separately from an outage: this is a QUALITY failure, and conflating
        # the two would hide a degrading model behind an availability metric.
        logger.warning('model output failed validation', extra={'context': {
            'chars': len(result.text or ''), 'model': result.model}})
        return jsonify(story=FALLBACK_STORY, source='fallback'), 200

    _cache_put(key, story)
    return jsonify(story=story, source='model', model=result.model), 200


@ai_bp.get('/health')
@token_required
def ai_health():
    """Whether the feature is currently working, without generating anything.

    Deliberately NOT part of /readyz. A model outage must not take the api out
    of the Service -- everything else still works, and readiness is about
    whether this pod can serve traffic, not whether every optional dependency
    is healthy.

    Same reasoning as web having no probe that touches the api.
    """
    from app.ai.provider import _breaker, get_provider
    return jsonify(
        provider=get_provider().name,
        breaker_open=_breaker.is_open(),
        cached_stories=len(_CACHE),
    ), 200