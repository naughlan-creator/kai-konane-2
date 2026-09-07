"""Prometheus metrics.

Logs and metrics answer different questions. logging_setup.py answers "what
happened to this ONE request" -- you arrive with a request id and leave with a
story. Metrics answer "what is happening to ALL of them" -- you arrive with a 
suspicion and leave with a rate.

Counting log lines to get a rate is a query whose cost grows with traffic, so
it gets slower exactly as the incident gets worse. A metric is pre-aggregated:
the cost of asking is constant.
"""
import os
import time

from flask import Blueprint, Response, request

_MULTIPROC_DIR = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
if _MULTIPROC_DIR:
    os.makedirs(_MULTIPROC_DIR, exist_ok=True)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        multiprocess,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    # The service must start without the dependency. An observability library
    # that can take the application down with it has inverted the relationship:
    # monitoring exists to tell you the app is broken, not to break it.
    PROMETHEUS_AVAILABLE = False


metrics_bp = Blueprint('metrics', __name__)

# Seconds. Tuned for THIS service, not copied from a default.
#
# The library default runs to 10s, which is useless here: everything lands in
# one bucket and the p95 is a flat line. Buckets cannot be changed without
# losing history, so they are worth thinking about once, now.
#
# The 0.75 boundary exists because the level-prediction endpoint loads a joblib
# model and sits just under a second.
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)

if PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        'http_requests_total', 'Total HTTP requests.',
        ['method', 'endpoint', 'status'])

    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds', 'HTTP request latency.',
        ['method', 'endpoint'], buckets=_LATENCY_BUCKETS)

    # A Gauge, not a Counter, because it goes DOWN. rate() over a counter that
    # decreases reports a spike that never happened.
    http_requests_in_flight = Gauge(
        'http_requests_in_flight', 'Requests currently being served.',
        multiprocess_mode='livesum')

    app_info = Gauge('app_info', 'Build information. Always 1; the labels carry '
                     'the payload.', ['service', 'version'])

    # Domain metrics. The three above are true of any web service; these are
    # what would show THIS system going wrong.
    auth_attempts_total = Counter(
        'auth_attempts_total', 'Login attempts by outcome.', ['outcome'])

    # Given the privilege-escalation hole found in #9, this is the metric that
    # would have shown it being exercised.
    authz_denials_total = Counter(
        'authz_denials_total', 'Authorisation refusals, by the rule that '
        'refused.', ['rule'])

    # --- AI ---
    #
    # Every call has a price, and the price is invisible unless it is measured.
    # Cost scales with input length, which users control -- so this is the
    # metric that turns "why is the bill like that" into a query.
    ai_requests_total = Counter(
        'ai_requests_total', 'Story requests by outcome.',
        ['outcome'])          # model | cache | fallback | rejected

    ai_tokens_total = Counter(
        'ai_tokens_total', 'Tokens consumed.',
        ['kind'])             # prompt | completion

    ai_cost_usd_total = Counter(
        'ai_cost_usd_total', 'Estimated spend in USD.')

    ai_request_duration_seconds = Histogram(
        'ai_request_duration_seconds', 'Time waiting on the model.',
        # Different buckets from HTTP entirely: generation takes SECONDS.
        # Reusing the web buckets would put every call in the top bucket.
        buckets=(0.5, 1, 2, 3, 5, 8, 12, 20, 30))

    ai_injection_attempts_total = Counter(
        'ai_injection_attempts_total',
        'Themes matching a known injection shape. Logged, never blocked -- '
        'this is how "someone is probing the model" becomes visible.')

    ai_breaker_open = Gauge(
        'ai_breaker_open', 'Circuit breaker state. 1 = refusing calls.',
        multiprocess_mode='max')

    # --- the level-prediction model --------------------------------------
    #
    # THE metric that would have caught the model returning BEGINNER for every
    # child. A constant prediction is a VALID prediction: no test failed, no
    # alert fired, no error was logged. Nothing in the system could tell the
    # difference between a working model and a broken one -- because the only
    # difference was the distribution.
    model_predictions_total = Counter(
        'model_predictions_total', 'Level predictions by class.',
        ['model', 'level'])

    model_prediction_failures_total = Counter(
        'model_prediction_failures_total',
        'Predictions that raised or returned an unusable value.', ['model'])


def _endpoint_label():
    """The route pattern, never the concrete path.

    A time series exists per distinct label combination. Labelling by
    request.path makes /api/users/1 and /api/users/2 separate series, so the
    cardinality of this metric becomes the number of rows in the users table.
    request.url_rule.rule gives /api/users/<int:user_id> -- one series per
    endpoint, which is what anyone actually wants a rate for.

    The fallback matters as much as the rule. Without it, a scanner probing 
    random URLs creates a new series per request, and an unauthenticated
    attacker can exhaust the monitoring server's memory just by making
    requests -- denial of service delivered through the observability stack    
    """
    if request.url_rule is not None:
        return request.url_rule.rule
    return '<unmatched>'


# --- AI and model recording -----------------------------------------------
#
# Plain module-level functions rather than methods on anything: provider.py
# and level_predictor.py import them directly, and neither should need a Flask
# app context to record a number.

# Rough per-1k-token prices, overridable. Deliberately approximate -- the point
# is a cost SIGNAL that moves with usage, not an invoice. If this is ever
# treated as billing truth it will be wrong.
_COST_PROMPT = float(os.getenv('AI_COST_PER_1K_PROMPT', '0.00015'))
_COST_COMPLETION = float(os.getenv('AI_COST_PER_1K_COMPLETION', '0.0006'))


def observe_ai_call(outcome, duration=None, prompt_tokens=0,
                    completion_tokens=0):
    if not PROMETHEUS_AVAILABLE:
        return
    ai_requests_total.labels(outcome=outcome).inc()
    if duration is not None:
        ai_request_duration_seconds.observe(duration)
    if prompt_tokens:
        ai_tokens_total.labels(kind='prompt').inc(prompt_tokens)
    if completion_tokens:
        ai_tokens_total.labels(kind='completion').inc(completion_tokens)
    cost = (prompt_tokens / 1000 * _COST_PROMPT
            + completion_tokens / 1000 * _COST_COMPLETION)
    if cost:
        ai_cost_usd_total.inc(cost)


def observe_ai_injection():
    if PROMETHEUS_AVAILABLE:
        ai_injection_attempts_total.inc()


def observe_breaker(is_open):
    if PROMETHEUS_AVAILABLE:
        ai_breaker_open.set(1 if is_open else 0)


def observe_prediction(model, level):
    """Record a prediction by class.

    Alert on any single class exceeding ~95% over a day. That is the whole fix
    for a failure mode where a degenerate model is indistinguishable from a
    working one.
    """
    if PROMETHEUS_AVAILABLE:
        model_predictions_total.labels(model=model, level=str(level)).inc()


def observe_prediction_failure(model):
    if PROMETHEUS_AVAILABLE:
        model_prediction_failures_total.labels(model=model).inc()


def configure_metrics(app, service):
    """Install the middleware and the /metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        app.logger.warning('prometheus_client not installed; /metrics returns 501')

        @app.get('/metrics')
        def _unavailable():
            return Response('prometheus_client is not installed\n',
                            status=501, mimetype='text/plain')
        return app

    app_info.labels(service=service,
                    version=os.getenv('APP_VERSION', 'dev')).set(1)

    @app.before_request
    def _start_timer():
        request._metrics_start = time.perf_counter()
        http_requests_in_flight.inc()

    @app.after_request
    def _record(response):
        # /metrics measuring itself is noise that grows with scrape frequency.
        if request.path == '/metrics':
            return response

        endpoint = _endpoint_label()
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            # The CLASS, not the code. 200/201/204 answer the same question,
            # and splitting them triples the series count for no insight.
            status=f'{response.status_code // 100}xx',
        ).inc()

        started = getattr(request, '_metrics_start', None)
        if started is not None:
            http_request_duration_seconds.labels(
                method=request.method, endpoint=endpoint,
            ).observe(time.perf_counter() - started)

        return response

    @app.teardown_request
    def _finish(exc=None):
        # teardown, NOT after_request: after_request does not run when a view
        # raises, so the gauge would climb by one on every unhandled exception
        # and never come down. A gauge that only rises is how a perfectly
        # healthy service comes to look permanently overloaded.
        if hasattr(request, '_metrics_start'):
            http_requests_in_flight.dec()

    app.register_blueprint(metrics_bp)
    return app


@metrics_bp.get('/metrics')
def metrics():
    """The scrape endpoint.

    Unauthenticated, deliberately: it is bound inside the cluster and the
    gateway does not route to it. If that ever changes it needs a guard --
    request counts by endpoint tell an attacker which parts of the system are
    used and which are unattended.
    """
    return Response(generate_latest(_registry()), mimetype=CONTENT_TYPE_LATEST)


def _registry():
    """A registry that sees every gunicorn worker, not just this one.

    api runs 2 workers, web runs 4. Each is a separate process with a separate
    registry, so without PROMETHEUS_MULTIPROC_DIR a scrape reports whichever
    worker answered -- half the real numbers for api, a quarter for web.
    Consistently wrong, which is worse than obviously broken.
    """
    multiproc_dir = os.getenv('PROMETHEUS_MULTIPROC_DIR')
    if not multiproc_dir:
        from prometheus_client import REGISTRY
        return REGISTRY

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=multiproc_dir)
    return registry