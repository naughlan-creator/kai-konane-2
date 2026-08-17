"""Application factory for the api service."""
from flask import render_template

from app.config import create_app_object


def create_app(overrides=None):
    app = create_app_object(overrides)

    # Imported inside the factory, not at module scope: routes import models,
    # models import config, and config imports back into the package -- a
    # top-level import chain closes that loop and raises on startup.
    from app.cli import register_cli
    from app.routes import (
        activity_bp,
        admin_bp,
        feedback_bp,
        learning_content_bp,
        learning_plan_bp,
        preschool_bp,
        profile_bp,
        progress_bp,
        story_bp,
        user_bp,
    )
    from app.routes.health import health_bp

    for blueprint in (
        user_bp,
        admin_bp,
        preschool_bp,
        feedback_bp,
        activity_bp,
        story_bp,
        learning_content_bp,
        profile_bp,
        learning_plan_bp,
        progress_bp,
        health_bp,
    ):
        app.register_blueprint(blueprint)

    @app.route('/')
    def index():
        return render_template('index.html')

    register_cli(app)

    return app
