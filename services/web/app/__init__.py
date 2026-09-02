"""Application factory for the web service.

web renders HTML. It holds no models, no database session and no domain logic --
every read and write goes to the api over HTTP through app/api_client.py.
"""
from flask import render_template

from app.config import create_app_object


def create_app(overrides=None):
    app = create_app_object(overrides)

    # Imported inside the factory to match api's structure and to keep the
    # import graph shallow.
    # Imported for its side effect: registering @login_manager.user_loader.
    # Without this import the loader is never attached and every template
    # render raises.
    from app import identity  # noqa: F401
    from app.logging_setup import configure_logging
    from app.metrics import configure_metrics

    configure_logging(app, 'web')
    configure_metrics(app, 'web')
    from app.routes.activity_routes import activity_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.feedback_routes import feedback_bp
    from app.routes.health import health_bp
    from app.routes.learning_content_routes import learning_content_bp
    from app.routes.learning_plan_routes import learning_plan_bp
    from app.routes.preschool_routes import preschool_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.progress_routes import progress_bp
    from app.routes.story_routes import story_bp
    from app.routes.user_routes import user_bp

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

    from app.filters import register_filters
    register_filters(app)

    return app
