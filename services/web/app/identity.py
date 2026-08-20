"""Who is signed in, rebuilt from JSON instead of the database.

`web` has no ORM, so `current_user` cannot be a model instance. It is a
`SessionUser` wrapping the payload from `GET /users/{id}` -- the same attribute
names the templates and route guards already use, so neither had to change.
"""
from flask import current_app, g, session
from flask_login import UserMixin

from app import api_client
from app.config import login_manager
from app.roles import Role

TOKEN_KEY = 'api_token'


class SessionUser(UserMixin):
    """A user rebuilt from the api's JSON.

    Attribute access falls through to the payload, so `current_user.firstname`
    and `current_user.gender` work exactly as they did against the ORM object.
    `role` is the one field converted eagerly -- see app/roles.py for why.
    """

    def __init__(self, payload):
        self._payload = payload or {}
        self.id = self._payload.get('id')
        self.role = Role.coerce(self._payload.get('role'))

    def __getattr__(self, name):
        """Fall through to the payload for anything not set above.

        Only called when normal lookup fails, so it never shadows UserMixin's
        `is_authenticated` / `is_active` / `is_anonymous`.
        """
        # Guard the private attribute or this recurses during unpickling.
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._payload[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__} has no {name!r}; the api did not send it"
            ) from None

    def get_id(self):
        """Flask-Login stores this in the session cookie, and it must be a str."""
        return str(self.id)

    @property
    def payload(self):
        """The raw dict, for templates that want to iterate it."""
        return self._payload

    def __repr__(self):
        return f"<SessionUser {self.id} {self.role}>"


@login_manager.user_loader
def load_user(user_id):
    """Rehydrate the signed-in user over HTTP, once per request.

    Flask-Login already caches the result for the life of a request, so
    `current_user` does not re-fetch on every reference. The `g` cache below
    makes that explicit and also covers code that calls this function directly.

    Returns None -- meaning anonymous -- for every failure, never an exception.
    Flask-Login invokes this from a template context processor, so raising here
    turns *every page that renders a template* into a 500, including pages that
    require no login at all.
    """
    if 'session_user' in g:
        return g.session_user

    token = session.get(TOKEN_KEY)
    if not token or not user_id:
        return None

    try:
        payload = api_client.get(f'users/{user_id}')
    except api_client.ApiUnauthorized:
        # The token expired or was revoked. Dropping it stops every later call
        # in this request from retrying with a credential we know is dead.
        session.pop(TOKEN_KEY, None)
        return None
    except api_client.ApiError as exc:
        # The api is down or broken. The user is treated as anonymous so pages
        # still render, but the token is deliberately left in place: this is our
        # outage, not their session ending, and it should recover on its own.
        current_app.logger.warning("Could not rehydrate user %s: %s", user_id, exc)
        return None

    g.session_user = SessionUser(payload.get('user') if payload else None)
    return g.session_user


def sign_in(payload, token):
    """Store the token and build the user, after a successful login call."""
    session[TOKEN_KEY] = token
    user = SessionUser(payload)
    g.session_user = user
    return user


def sign_out():
    """Drop the token and the cached user."""
    session.pop(TOKEN_KEY, None)
    g.pop('session_user', None)