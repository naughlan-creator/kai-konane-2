"""OpenTelemetry tracing for the web service.

See services/api/app/tracing.py for why tracing was added ALONGSIDE the
existing X-Request-ID correlation rather than instead of it.

One difference, and it is the reason this file exists separately: web is where
a trace STARTS. A browser sends no traceparent header, so the span created here
is a root span, and the sampling decision made here is the one every downstream
service inherits.

web is also the only service that makes outbound HTTP calls, so
RequestsInstrumentor matters here and is meaningless in the api.
"""
import logging
import os

logger = logging.getLogger(__name__)


def tracing_enabled():
    return os.getenv('OTEL_TRACES_ENABLED', 'false').lower() in ('1', 'true', 'yes')


def configure_tracing(app, service):
    if not tracing_enabled():
        return app

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning('OTEL_TRACES_ENABLED is set but the opentelemetry '
                       'packages are not installed; continuing without tracing')
        return app

    try:
        resource = Resource.create({
            'service.name': os.getenv('OTEL_SERVICE_NAME', f'kai-konane-{service}'),
            'service.version': os.getenv('APP_VERSION', 'dev'),
            'deployment.environment': os.getenv('APP_ENV', 'development'),
        })

        # web is the edge, so this is where the sampling decision is MADE
        # rather than inherited. ParentBased still matters: it is what makes
        # the api honour what web decided instead of rolling its own dice.
        ratio = float(os.getenv('OTEL_TRACES_SAMPLER_ARG', '1.0'))
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(root=TraceIdRatioBased(ratio)),
        )

        endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT',
                             'http://jaeger.monitoring.svc.cluster.local:4318')
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f'{endpoint.rstrip("/")}/v1/traces')))
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(
            app, excluded_urls='healthz,readyz,metrics,static')

        # THE line that makes the trace span two services.
        #
        # It patches `requests` so every call carries a `traceparent` header
        # describing the current span. The api reads it and makes its spans
        # CHILDREN of this one.
        #
        # Nothing in api_client.py changes -- the propagation is invisible at
        # the call site, which is exactly why it is reliable: there is no place
        # for anyone to forget to forward a header. Compare that with
        # X-Request-ID, which api_client has to remember to send by hand.
        RequestsInstrumentor().instrument()

        app.logger.info('tracing configured', extra={'context': {
            'exporter': endpoint, 'sample_ratio': ratio}})
    except Exception as exc:
        logger.warning('tracing setup failed, continuing without it: %s', exc)

    return app