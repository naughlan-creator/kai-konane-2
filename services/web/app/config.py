"""Settings for the web service.

web holds no database and no domain logic, so this file is a fraction of the
api's. What it does own: the session cookie key, and where the api lives.
"""
import os
import secrets
import warnings

from flask import Flask
from flask_login import LoginManager

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _load_dotenv():
    """Read a .env from the repo root, without adding a dependency.

    A real environment variable always wins, so a container's config cannot be
    silently overridden by a file that got baked into the image.
    """
    path = os.path.join(basedir, '..', '..', '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _is_production():
    env = (os.getenv('APP_ENV') or os.getenv('FLASK_ENV') or 'development').lower()
    return env in ('production', 'prod')


IS_PRODUCTION = _is_production()


def _secret_key():
    """Signs web's session cookie. This is not API_TOKEN_SECRET.

    That one signs api tokens and lives only in the api. Keeping them apart
    means a leak of either does not compromise the other.
    """
    key = os.getenv('SECRET_KEY')
    if key:
        return key
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY must be set in production. Generate one with:\n"
            " python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    warnings.warn(
        "SECRET_KEY is not set; using a random key for this run. You will be "
        "logged out on restart.",
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


login_manager = LoginManager()


def create_app_object(overrides=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(basedir, 'templates'),
        static_folder=os.path.join(basedir, 'static'),
    )

    app.config['SECRET_KEY'] = _secret_key()

    # Where the api lives. In compose this becomes http://api:5000
    # Where *this process* reaches the api. A container hostname is fine here.
    app.config['API_BASE_URL'] = os.getenv('API_BASE_URL', 'http://127.0.0.1:5000')

    # Where the *browser* reaches the api, for <img> sources and fetch() calls.
    # These are not the same thing: API_BASE_URL is 'http://api:5000' in compose,
    # and 'api' is a Docker-internal hostname the browser cannot resolve. Empty
    # means same-origin, which is correct behind the gateway -- nginx routes
    # /api/ onward. Set it to http://127.0.0.1:5000 when running the two
    # services directly with no gateway in front.
    app.config['API_PUBLIC_URL'] = os.getenv('API_PUBLIC_URL', '').rstrip('/')
    # A slow api must not become a hung page. Every call carries this.
    app.config['API_TIMEOUT_S'] = float(os.getenv('API_TIMEOUT_S', '3'))

    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = (
        os.getenv('SESSION_COOKIE_SECURE', str(IS_PRODUCTION)).lower()
        in ('1', 'true', 'yes')
    )

    app.config.update(overrides or {})

    login_manager.init_app(app)
    login_manager.login_view = 'user.login'

    return app