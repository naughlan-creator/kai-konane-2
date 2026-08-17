"""Application configuration.

Nothing secret is hard-coded here. Everything sensitive comes from the
environment (optionally via a local, git-ignored `.env` file).
"""
import os
import secrets
import sqlite3
import warnings

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

# The service directory (services/api), not the package directory. templates/,
# static/ and instance/ all live beside the package, and services/media.py
# derives the upload path from this.
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _load_dotenv():
    """Read key=value pairs from a .env, without overriding real env vars.

    Walks up from the service directory so the same file serves the repo root
    in development. In a container there is no .env and this is a no-op.
    """
    directory = basedir
    for _ in range(4):
        path = os.path.join(directory, '.env')
        if os.path.exists(path):
            break
        parent = os.path.dirname(directory)
        if parent == directory:
            return
        directory = parent
    else:
        return

    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # A real environment variable always wins over the file.
            os.environ.setdefault(key, value)


_load_dotenv()


def _is_production():
    env = (os.getenv('APP_ENV') or os.getenv('FLASK_ENV') or 'development').lower()
    return env in ('production', 'prod')


IS_PRODUCTION = _is_production()


def _database_uri():
    """Resolve the database URI from the environment.

    Falls back to a local SQLite file so the app is runnable out of the box.
    Never hard-code credentials here -- anything committed is compromised.
    """
    uri = (
        os.getenv('DATABASE_URL')
        or os.getenv('JAWSDB_URL')
        or os.getenv('SQLALCHEMY_DATABASE_URI')
    )
    if uri:
        # Render/Heroku hand out "postgres://", which SQLAlchemy 2.x rejects.
        if uri.startswith('postgres://'):
            uri = uri.replace('postgres://', 'postgresql://', 1)
        return uri

    if IS_PRODUCTION:
        raise RuntimeError(
            "DATABASE_URL must be set in production. Refusing to fall back to "
            "a local SQLite file."
        )

    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return 'sqlite:///' + os.path.join(instance_dir, 'kai_konane.db')


def _secret_key():
    """The session signing key.

    Required in production. In development a random key is generated per run --
    that logs everyone out on restart, which is the correct trade against
    shipping a known key that lets anyone forge a session cookie.
    """
    key = os.getenv('SECRET_KEY')
    if key:
        return key

    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY must be set in production. Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    warnings.warn(
        "SECRET_KEY is not set; using a random key for this run. Sessions will "
        "not survive a restart. Copy .env.example to .env to set one.",
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


# Extensions are created unbound and attached inside the factory. Binding them
# to a module-level app is what makes an application factory impossible.
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app_object(overrides=None):
    """Build and configure the Flask object.

    templates/ and static/ sit beside the package rather than inside it, so
    both folders are passed explicitly -- Flask would otherwise look for them
    under app/ and every render_template would fail.
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(basedir, 'templates'),
        static_folder=os.path.join(basedir, 'static'),
    )

    app.config['SQLALCHEMY_DATABASE_URI'] = _database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = _secret_key()

    # Cap uploads so a large file cannot exhaust memory or disk.
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024

    # Session cookie hardening.
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
        # Recycle connections so a managed Postgres that drops idle sockets does
        # not hand back a dead connection.
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 280,
        }

    # Tests override SQLALCHEMY_DATABASE_URI and TESTING through here.
    app.config.update(overrides or {})

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'user.login'

    return app


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    """SQLite ignores foreign keys unless asked.

    Without this the ON DELETE rules are silently inert on the dev database and
    only start behaving differently once you deploy to Postgres.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
