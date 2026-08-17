import os

from flask import render_template
from sqlalchemy import text

# Registers the `flask init-db`, `seed`, `check`, ... commands.
import cli  # noqa: F401  (imported for its side effects)
from config import app, db
from routes import (
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

app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(preschool_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(activity_bp)
app.register_blueprint(story_bp)
app.register_blueprint(learning_content_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(learning_plan_bp)
app.register_blueprint(progress_bp)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    """Liveness probe: confirms the process is up and the database answers."""
    try:
        db.session.execute(text('SELECT 1'))
        return {'status': 'ok'}, 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return {'status': 'error'}, 503


if __name__ == '__main__':
    # Port and host come from the environment so the same entrypoint works for
    # local dev and inside a container. gunicorn overrides both in production.
    # Windows reserves some port ranges (netsh interface ipv4 show
    # excludedportrange protocol=tcp) -- set PORT if 5000 is one of them.
    app.run(host=os.getenv('HOST', '127.0.0.1'),
            port=int(os.getenv('PORT', '5000')),
            debug=True)
