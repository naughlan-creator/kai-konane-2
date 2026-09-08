"""OpenTelemetry tracing.

This project already had distributed tracing, hand-rolled: logging_setup.py
generates an id in web, forwards it as X-Request-ID, and the api reuses it, so
one page view shares one id across both services and Log Analytics can group by
it. Building that is why the concepts below are familiar rather than abstract.

It has 3 limits and they only show up once you rely on it.
 * It records that a request happened, not how long each part took.
 * It is one flat id. A page view making 4 api calls produces 4 sets of lines
   sharing one id, with nothing recording that call 3 happened inside call 2.
   Causality is lost
 * It is ours. Nothing else speaks it -- not a managed database, not a message
   broker, not a 3rd party SDK.

OpenTelementry fixes all 3 with a vendor-neutral wire format. A span has a 
duration and a parent, so the shape of the request is preserved; the W3C 
`traceparent` header is understood by every compliant library, so a call through 
`requests` continues the trace with nobody writing code to make it.

X-Request-ID is KEPT, not replaced. It is human-sized -- a person can read one
off a page and quote it in a bug report -- and the existing log format and KQL
queries use it. The right move is a bridge, not a migration.
"""
import logging
import os

logger = logging.getLogger(__name__)

def tracing_enabled():
    """Off unless explicitly switched on.
    
    An exporter that cannot reach its collector retries on a background thread.
    Defaulting this on means every developer running without a collector gets a
    warning every few seconds, learns to ignore warnings, and the habit costs
    something later.
    """
    return os.getenv('OTEL_TRACES_ENABLED', 'false').lower() in ('1', 'true', 'yes')

def configure_tracing(app, service):
    """Instrument Flask and SQLAlchemy.
    
    Returns the app either way. Every failure here is caught and logged: a
    misconfigured collector endpoint must not stop the service starting.
    Observability that can take production down has inverted its own purpose --
    a lesson this project already learned the hard way when the metrics module
    broke the migration Job.
    """
    if not tracing_enabled():
        return app

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning('OTEL_TRACES_ENABLED is set but the opentelemetry '
                       'packages are not installed; continuing without tracing')
        return app

    try:
        # The Resource is what makes a span attributable. Without service.name
        # every trace belongs to "unknown_service" and the backend cannot tell
        # api from web -- which defeats the point of tracing a system that has
        # more than one service in it.
        resource = Resource.create({
            'service.name': os.getenv('OTEL_SERVICE_NAME', f'kai-konane-{service}'),
            'service.version': os.getenv('APP_VERSION', 'dev'),
            'deployment.environment': os.getenv('APP_ENV', 'development'),
        })

        # ParentBased wrapping the ratio sampler, not the ratio sampler alone.
        #
        # This is the subtle one. If each service samples independently at 10%,
        # a trace spanning two services is complete only when BOTH happen to
        # sample it -- 1% of the time -- and the other 19% are traces with a
        # hole in the middle, which is worse than no trace at all.
        #
        # ParentBased says: if an incoming request already carries a sampling
        # decision, honour it. The decision is made once, at the edge, and the
        # whole trace is kept or dropped together.
        ratio = float(os.getenv('OTEL_TRACES_SAMPLER_ARG', '1.0'))
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(root=TraceIdRatioBased(ratio)),
        )

        endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT',
                             'http://jaeger.monitoring.svc.cluster.local:4318')

        # Batch, not Simple. SimpleSpanProcessor exports synchronously when a
        # span ends, adding the collector's latency to every single request --
        # so a slow collector looks like a slow application.
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f'{endpoint.rstrip("/")}/v1/traces')))
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(
            app,
            # Already covered by the probes, and otherwise the overwhelming
            # majority of spans: at a 10s interval per replica they outnumber
            # real traffic on a quiet service by an order of magnitude. The
            # same decision logging_setup.py made, for the same reason.
            excluded_urls='healthz,readyz,metrics',
        )

        # Every query becomes a child span with the statement attached, so a
        # slow endpoint shows WHICH QUERY was slow rather than only that the
        # endpoint was. The highest-value instrumentation in this service,
        # because the api's job is almost entirely queries.
        with app.app_context():
            from app.config import db
            SQLAlchemyInstrumentor().instrument(engine=db.engine)

        app.logger.info('tracing configured', extra={'context': {
            'exporter': endpoint, 'sample_ratio': ratio}})
    except Exception as exc:
        logger.warning('tracing setup failed, continuing without it: %s', exc)

    return app