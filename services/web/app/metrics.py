"""Prometheus metrics for the web service.

Deliberately a near-copy of services/api/app/metrics.py rather than a shared
library. The two services have separate images, separate dependency lists and
separate deployment cadences; a shared package would need somewhere to live, a
version and a release process, and would couple the two things #9 spent an
issue decoupling. Eighty duplicated lines is the cheaper side of that trade --
and stays cheaper only while the duplication is acknowledged, which is what
this paragraph is for.

What is genuinely different is the second half of the file.
"""
import os
import re
import time

from flask import Blueprint, Response, request

_MULTIPROC_DIR = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
if _MULTIPROC_DIR:
    os.makedirs(_MULTIPROC_DIR, exist_ok=True)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram,
        generate_latest, multiprocess,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False


metrics_bp = Blueprint('metrics', __name__)

_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)

if PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        'http_requests_total', 'Total HTTP requests.',
        ['method', 'endpoint', 'status'])

    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds', 'HTTP request latency.',
        ['method', 'endpoint'], buckets=_LATENCY_BUCKETS)

    http_requests_in_flight = Gauge(
        'http_requests_in_flight', 'Requests currently being served.',
        multiprocess_mode='livesum')

    app_info = Gauge('app_info', 'Build information.', ['service', 'version'])

    # --- the part that is not a copy -----------------------------------
    #
    # A page render can fan out to several api calls. Timing the page tells
    # you it was slow; timing the calls tells you WHICH ONE.
    api_client_duration_seconds = Histogram(
        'api_client_request_duration_seconds',
        'Time spent waiting on the api, measured from web.',
        ['method', 'path'], buckets=_LATENCY_BUCKETS)

    api_client_requests_total = Counter(
        'api_client_requests_total', 'Calls to the api by outcome.',
        ['method', 'path', 'outcome'])

    # Separate from the counter above because these failures have NO HTTP
    # STATUS AT ALL -- a timeout, a refused connection, a DNS failure. They
    # matter most and a status-code metric cannot see them, because there is
    # no response to read a status from.
    api_client_failures_total = Counter(
        'api_client_failures_total', 'Api calls that produced no response.',
        ['reason'])


# Segments that are an id: all digits, or a UUID.
_ID_SEGMENT = re.compile(r'^(\d+|[0-9a-fA-F-]{32,36})$')


def templatise(path):
    """Collapse id segments so /users/3 and /users/7 share one time series.

    A heuristic, and worth being honest about: api_client is handed a concrete
    path, not the template it was built from, so this pattern-matches instead
    of knowing. It catches numeric ids and UUIDs. A slug -- /stories/the-red-
    balloon -- would still leak one series per story.

    The correct fix is for call sites to pass the template. That is ~50 call
    sites, and this buys most of the benefit for none of the churn. If the
    series count ever climbs, this comment is where to start.
    """
    return '/'.join('<id>' if _ID_SEGMENT.match(s) else s
                    for s in path.split('/'))


def observe_api_call(method, path, duration, outcome):
    if not PROMETHEUS_AVAILABLE:
        return
    p = templatise(path)
    api_client_duration_seconds.labels(method=method, path=p).observe(duration)
    api_client_requests_total.labels(method=method, path=p, outcome=outcome).inc()


def observe_api_failure(reason):
    """A call that never produced a response: timeout, DNS, refused."""
    if not PROMETHEUS_AVAILABLE:
        return
    api_client_failures_total.labels(reason=reason).inc()


def _endpoint_label():
    if request.url_rule is not None:
        return request.url_rule.rule
    return '<unmatched>'


def configure_metrics(app, service):
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
        # Static assets are a page-view multiplier and tell you nothing that
        # the page metric does not. Unlike /healthz, which stays -- see below.
        if request.path == '/metrics' or request.path.startswith('/static/'):
            return response

        endpoint = _endpoint_label()
        http_requests_total.labels(
            method=request.method, endpoint=endpoint,
            status=f'{response.status_code // 100}xx').inc()

        started = getattr(request, '_metrics_start', None)
        if started is not None:
            http_request_duration_seconds.labels(
                method=request.method, endpoint=endpoint,
            ).observe(time.perf_counter() - started)
        return response

    @app.teardown_request
    def _finish(exc=None):
        # teardown, not after_request -- see the api's copy.
        if hasattr(request, '_metrics_start'):
            http_requests_in_flight.dec()

    app.register_blueprint(metrics_bp)
    return app


@metrics_bp.get('/metrics')
def metrics():
    return Response(generate_latest(_registry()), mimetype=CONTENT_TYPE_LATEST)


def _registry():
    """web runs FOUR workers -- twice the api's. Without the multiprocess
    directory a scrape reports roughly a quarter of reality."""
    multiproc_dir = os.getenv('PROMETHEUS_MULTIPROC_DIR')
    if not multiproc_dir:
        from prometheus_client import REGISTRY
        return REGISTRY
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=multiproc_dir)
    return registry