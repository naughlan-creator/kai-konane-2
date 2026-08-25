"""JSON logs with a request id on every line.

Two services behind a gateway means one page view produces log lines in three
places. Without a shared id you cannot tell which api call belongs to which page
render, and the first thing you do when something breaks in production is try to
work that out.

This service originates the id, because it is the one a browser talks to. It
forwards it to the api as `X-Request-ID`, and the api reuses it rather than
minting its own -- so a single id spans the whole hop.

JSON rather than human-readable text because the destination is a log
aggregator, not a terminal. A message like "Updated level for child 4" is
readable but unqueryable; the same content as fields is both.
"""
import json
import logging
import sys
import time
import uuid

from flask import g, has_request_context, request

REQUEST_ID_HEADER = 'X-Request-ID'


class JsonFormatter(logging.Formatter):
    """One JSON object per line.

    Deliberately not using a library: the format is eight fields and adding a
    dependency to a production image to build a dict is a poor trade.
    """

    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        payload = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(record.created))
                  + f'.{int(record.msecs):03d}Z',
            'level': record.levelname,
            'service': self.service,
            'logger': record.name,
            'message': record.getMessage(),
        }

        if has_request_context():
            payload['request_id'] = getattr(g, 'request_id', None)
            payload['method'] = request.method
            payload['path'] = request.path

        # Anything passed as extra={...} rides along as its own field, which is
        # what makes a log line queryable rather than just readable.
        for key, value in getattr(record, 'context', {}).items():
            payload[key] = value

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(app, service):
    """Send everything to stdout as JSON, and stamp each request with an id.

    stdout because that is where a container's logs are collected from. Writing
    to a file inside a container means the logs die with the container.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))

    root = logging.getLogger()
    # Replace rather than append: Flask and gunicorn install their own handlers,
    # and leaving them attached prints every line twice -- once as JSON and once
    # as plain text, which quietly doubles log volume and cost.
    root.handlers = [handler]
    root.setLevel(app.config.get('LOG_LEVEL', 'INFO'))

    # gunicorn's own loggers propagate to root once their handlers are cleared.
    for name in ('gunicorn.error', 'gunicorn.access', 'werkzeug'):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    @app.before_request
    def _assign_request_id():
        # Reuse an inbound id so one page view is one id across every service.
        g.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        g.request_started = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = None
        if hasattr(g, 'request_started'):
            duration_ms = round((time.monotonic() - g.request_started) * 1000, 1)

        # Health checks run every ten seconds per service, and one page view
        # pulls dozens of static assets. Logging either buries real traffic and,
        # on a per-GB-ingested bill, costs money to hide your own signal. A
        # static file that 404s is worth knowing about, so those still log.
        noisy = (request.path in ('/healthz', '/readyz')
                 or (request.path.startswith('/static/')
                     and response.status_code < 400))
        if not noisy:
            app.logger.info('request', extra={'context': {
                'status': response.status_code,
                'duration_ms': duration_ms,
            }})

        # Echo the id back so a browser or curl can quote it in a bug report.
        response.headers[REQUEST_ID_HEADER] = getattr(g, 'request_id', '')
        return response

    return app
