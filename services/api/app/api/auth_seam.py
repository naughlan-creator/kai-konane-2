"""Bearer token authentication for the api.

`web` never verifies a password and never holds a hash. It posts credentials to
`POST /auth/login`, receives a signed token, and presents that token on every
later call. The api is the only service that can mint or verify one.

The token is an `itsdangerous` signed payload, not a JWT. A JWT would add a
dependency and a header full of algorithm negotiation for no benefit here: there
is exactly one issuer, exactly one verifier, and a shared secret. `itsdangerous`
is already a Flask dependency and its timestamp handling is the part that
matters -- `max_age` is enforced at load time, so an old token cannot be
replayed even though the payload itself is readable.

Readable, not secret: the signature proves the api issued it and that nobody
edited it. It does not hide the contents. Never put anything in the claims that
the bearer should not see.
"""
import functools

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Namespaces the signature. A token minted for this purpose cannot be replayed
# against any other serializer sharing the same secret.
TOKEN_SALT = 'kai-konane-api-token'


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config['API_TOKEN_SECRET'], salt=TOKEN_SALT)


def issue_token(user):
    """Mint a token for a verified user.

    Claims stay minimal: an id to look the user up and a role so the common
    authorisation checks need no query. Anything else would go stale the moment
    the record changed, because a signed token cannot be updated -- only
    reissued.
    """
    return _serializer().dumps({'uid': user.id, 'role': user.role.name})


def read_token(token, max_age=None):
    """Verify and decode a token. Returns the claims, or None if unusable.

    One return value for every failure -- bad signature, expired, malformed --
    because the caller has the same response in all three cases and telling them
    apart only helps someone probing the endpoint.
    """
    if not token:
        return None
    if max_age is None:
        max_age = current_app.config['API_TOKEN_TTL_S']
    try:
        return _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


def _bearer_from_request():
    """The token from `Authorization: Bearer <token>`.

    The scheme is compared case-insensitively because RFC 7235 defines it that
    way and clients differ; the token itself is left untouched.
    """
    header = request.headers.get('Authorization', '')
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer':
        return None
    return token.strip() or None


def _unauthorized(message):
    """401 with the challenge header the spec requires.

    Without WWW-Authenticate a 401 is technically malformed, and HTTP clients
    that retry on a challenge have nothing to act on.
    """
    response = jsonify(error=message)
    response.status_code = 401
    response.headers['WWW-Authenticate'] = f'Bearer realm="api", error="{message}"'
    return response


def token_required(view):
    """Require a valid bearer token, and put its claims on `g`.

    Endpoints read `g.current_user_id` and `g.current_role` rather than querying
    for the user, so a request that only needs an id costs no extra round trip.
    """
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_from_request()
        if token is None:
            return _unauthorized('Authentication required')

        claims = read_token(token)
        if claims is None:
            return _unauthorized('Invalid or expired token')

        g.token_claims = claims
        g.current_user_id = claims.get('uid')
        g.current_role = claims.get('role')
        return view(*args, **kwargs)

    wrapper.__token_required__ = True
    return wrapper
