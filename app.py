from flask import render_template
from config import app, db
from routes import *
from services import *
from models import *

# Registers the `flask init-db`, `seed`, `check`, ... commands.
import cli  # noqa: F401  (imported for its side effects)

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
    from sqlalchemy import text
    try:
        db.session.execute(text('SELECT 1'))
        return {'status': 'ok'}, 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return {'status': 'error'}, 503


if __name__ == '__main__':
    app.run(debug=True)
