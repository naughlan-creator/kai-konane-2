"""Bearer token authentication.

The rest of the api suite runs with a token attached by the test client, so
these are the tests that check the wall itself rather than what is behind it.
"""
import pytest
from app.api.auth_seam import TOKEN_SALT, read_token
from conftest import flask_app
from itsdangerous import URLSafeTimedSerializer

# Every one of these needs a token. The list is the acceptance criterion for #8
# plus one endpoint from each resource module, so a module that forgets the
# decorator is caught here.
PROTECTED = [
    '/api/progress?teacher_id=1',
    '/api/children/1/progress',
    '/api/children/1/results',
    '/api/children/1/stem-levels',
    '/api/users/1',
    '/api/children/1',
    '/api/teachers',
    '/api/activities',
    '/api/stories',
    '/api/learning-plans/child/1',
    '/api/feedback?recipient_id=1',
    '/api/preschools/1',
]

# These must stay open: you cannot present a token before you have an account.
PUBLIC = [
    '/api/preschools',
    '/api/users/availability?username=x',
    '/healthz',
]


# ------------------------------------------------------------------ issuing

def test_login_returns_a_token(anon_client):
    body = anon_client.post('/api/auth/login',
                            json={'username': 'parent', 'password': 'pw'}
                            ).get_json()
    assert body['token']
    assert body['expires_in'] == flask_app.config['API_TOKEN_TTL_S']


def test_failed_login_issues_no_token(anon_client):
    body = anon_client.post('/api/auth/login',
                            json={'username': 'parent', 'password': 'wrong'}
                            ).get_json()
    assert 'token' not in body


def test_token_carries_only_an_id_and_a_role(anon_client):
    """A signed token is readable by anyone holding it. Signing proves origin,
    it does not hide the payload -- so nothing sensitive may go in it."""
    token = anon_client.post('/api/auth/login',
                             json={'username': 'parent', 'password': 'pw'}
                             ).get_json()['token']
    with flask_app.app_context():
        claims = read_token(token)
    assert set(claims) == {'uid', 'role'}
    assert claims['role'] == 'PARENT'


# ------------------------------------------------------------------ the wall

@pytest.mark.parametrize('path', PROTECTED)
def test_protected_endpoints_reject_a_missing_token(anon_client, path):
    response = anon_client.get(path)
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Authentication required'


def test_401_carries_the_challenge_header(anon_client):
    """A 401 without WWW-Authenticate is malformed, and a client that retries on
    a challenge has nothing to act on."""
    response = anon_client.get('/api/progress?teacher_id=1')
    assert response.headers['WWW-Authenticate'].startswith('Bearer ')


@pytest.mark.parametrize('path', PUBLIC)
def test_public_endpoints_need_no_token(anon_client, path):
    assert anon_client.get(path).status_code == 200


def test_registration_stays_open(anon_client, ids):
    """Signup cannot require a token, or nobody can ever get one."""
    response = anon_client.post('/api/teachers', json={
        'username': 'anonteacher', 'email': 'at@x.local', 'password': 'pw',
        'firstname': 'Anon', 'lastname': 'Teacher',
    })
    assert response.status_code == 201


# --------------------------------------------------------------- bad tokens

@pytest.mark.parametrize('header', [
    'Bearer not-a-real-token',
    'Bearer ',
    'Basic dXNlcjpwYXNz',
    'garbage',
    '',
])
def test_malformed_authorization_is_rejected(anon_client, header):
    response = anon_client.get('/api/progress?teacher_id=1',
                               headers={'Authorization': header})
    assert response.status_code == 401


def test_a_tampered_token_is_rejected(anon_client, token):
    """Flipping one character must break the signature."""
    payload, _, signature = token.rpartition('.')
    forged = payload + '.' + ('x' * len(signature))
    response = anon_client.get('/api/progress?teacher_id=1',
                               headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid or expired token'


def test_a_token_signed_with_another_secret_is_rejected(anon_client):
    """The whole point of the signature: only this api can mint one."""
    forged = URLSafeTimedSerializer('some-other-secret', salt=TOKEN_SALT).dumps(
        {'uid': 1, 'role': 'ADMIN'})
    response = anon_client.get('/api/progress?teacher_id=1',
                               headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401


def test_a_token_from_a_different_salt_is_rejected(anon_client):
    """Salting namespaces the signature, so a token minted for another purpose
    with the same secret cannot be replayed here."""
    forged = URLSafeTimedSerializer(
        flask_app.config['API_TOKEN_SECRET'], salt='password-reset').dumps(
            {'uid': 1, 'role': 'ADMIN'})
    response = anon_client.get('/api/progress?teacher_id=1',
                               headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401


def test_an_expired_token_is_rejected(anon_client, token):
    """Age is enforced at load time, so an old token cannot be replayed."""
    original = flask_app.config['API_TOKEN_TTL_S']
    flask_app.config['API_TOKEN_TTL_S'] = -1
    try:
        response = anon_client.get('/api/progress?teacher_id=1',
                                   headers={'Authorization': f'Bearer {token}'})
    finally:
        flask_app.config['API_TOKEN_TTL_S'] = original
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid or expired token'


def test_a_valid_token_is_accepted(client, ids):
    """The positive case, so the tests above cannot pass by rejecting
    everything."""
    assert client.get(f"/api/children/{ids['child']}/progress").status_code == 200


def test_the_scheme_is_case_insensitive(anon_client, token):
    """RFC 7235 defines the scheme case-insensitively and clients differ."""
    response = anon_client.get('/api/preschools/1',
                               headers={'Authorization': f'bearer {token}'})
    assert response.status_code == 200
