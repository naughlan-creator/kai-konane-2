"""Application factory for the api service.

Since #9 this service serves JSON and nothing else. It has no templates, no
sessions and no HTML routes -- those moved to services/web, which reaches this
one over HTTP. What stays here is the domain: the models, the services, the
migrations and the database connection, which no other service opens.
"""
from app.config import create_app_object


def create_app(overrides=None):
    app = create_app_object(overrides)

    # Imported inside the factory, not at module scope: api imports models,
    # models import config, and config imports back into the package -- a
    # top-level import chain closes that loop and raises on startup.
    from app.api import api_bp, register_error_handlers
    from app.cli import register_cli
    from app.logging_setup import configure_logging
    from app.metrics import configure_metrics
    from app.routes.health import health_bp

    configure_logging(app, 'api')
    # After logging, so anything metrics reports has somewhere to go.
    configure_metrics(app, 'api')

    app.register_blueprint(api_bp)
    # Not part of the JSON contract: these are hit by the orchestrator, so they
    # sit at the root rather than under /api.
    app.register_blueprint(health_bp)

    register_error_handlers(app)
    register_cli(app)

    return app
