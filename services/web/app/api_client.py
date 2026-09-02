"""The only place `web` makes an HTTP call.

Every read and write in this service goes through here. That is the point: one
file to add a header to, one file to change when the api moves, one file to read
when you want to know what web depends on. A `requests.get` anywhere else in
`web` is a bug.

Errors from the api arrive as `{"error": "..."}` with a meaningful status. This
module turns each status into an exception a route can catch, so routes never
inspect status codes and never see a `requests` object.
"""
import requests, time
from flask import current_app, g, session


class ApiError(Exception):
    """Base for everything below. Carries a message safe to show a user."""

    status = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ApiUnavailable(ApiError):
    """The api could not be reached, or did not answer in time.

    Distinct from every other failure because it is the only one where retrying
    later might work, and the only one that is not the user's doing.
    """


class ApiUnauthorized(ApiError):
    """401 -- the token is missing, invalid or expired.

    Routes must treat this as *log in again*, never as *retry*. An expired token
    plus a retry is an infinite loop.
    """


class ApiForbidden(ApiError):
    """403 -- authenticated, but not allowed to touch this."""


class ApiNotFound(ApiError):
    """404."""


class ApiValidation(ApiError):
    """400 -- the request was wrong. Message is safe to show as a flash."""


class ApiConflict(ApiError):
    """409 -- a uniqueness clash, or a delete that would orphan rows."""


_BY_STATUS = {
    400: ApiValidation,
    401: ApiUnauthorized,
    403: ApiForbidden,
    404: ApiNotFound,
    409: ApiConflict,
}


def _session():
    """One connection pool per request.

    Rendering a page usually means several api calls -- rehydrating the user,
    then fetching the data -- and reusing the connection avoids a fresh TCP
    handshake for each. Scoping it to `flask.g` rather than a module global
    sidesteps the question of whether a `requests.Session` is safe to share
    between worker threads.
    """
    if 'api_session' not in g:
        g.api_session = requests.Session()
    return g.api_session


def _url(path):
    base = current_app.config['API_BASE_URL'].rstrip('/')
    return f"{base}/api/{path.lstrip('/')}"


def _headers(token=None, explicit=None):
    headers = {'Accept': 'application/json'}
    # Forward this request's id so the api's log lines carry the same one.
    # Without it, correlating a page render with the three api calls behind it
    # means guessing from timestamps.
    request_id = getattr(g, 'request_id', None)
    if request_id:
        headers['X-Request-ID'] = request_id
    # An explicit token wins, so login can call the api before a session exists.
    token = token or session.get('api_token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if explicit:
        headers.update(explicit)
    return headers


def _raise_for(response):
    """Turn an error response into the matching exception.

    The api always sends `{"error": ...}`, but a proxy or a crash can produce
    HTML, so the body is parsed defensively -- a JSONDecodeError here would
    otherwise mask the real failure.
    """
    try:
        message = (response.json() or {}).get('error') or response.reason
    except ValueError:
        message = response.reason or f'api returned {response.status_code}'

    error_class = _BY_STATUS.get(response.status_code)
    if error_class is not None:
        raise error_class(message)

    raise ApiError(f'api error {response.status_code}: {message}')


def request(method, path, *, json=None, params=None, token=None, headers=None):
    """Call the api and return the decoded body.

    Returns None for 204, which is what DELETE endpoints send.
    """
    from app.metrics import observe_api_call, observe_api_failure

    started = time.perf_counter()
    try:
        response = _session().request(
            method,
            _url(path),
            json=json,
            params=params,
            headers=_headers(token, headers),
            timeout=current_app.config['API_TIMEOUT_S'],
        )
    except requests.Timeout as exc:
        # Counted separately from any status code: there is no response.
        observe_api_failure('timeout')
        raise ApiUnavailable('The service took too long to respond.') from exc
    except requests.RequestException as exc:
        observe_api_failure('unreachable')
        raise ApiUnavailable('The service is unavailable right now.') from exc

    observe_api_call(method, path, time.perf_counter() - started,
                     f'{response.status_code // 100}xx')

    if response.status_code == 204 or not response.content:
        return None

    if not response.ok:
        _raise_for(response)

    try:
        return response.json()
    except ValueError as exc:
        # A 200 that is not JSON means we are not talking to the api -- a login
        # portal or an error page has intercepted the call.
        raise ApiError('The service returned an unreadable response.') from exc


def post_file(path, field, storage, **kwargs):
    """Forward one uploaded file to the api as multipart.

    The only call that does not send JSON. `storage` is the werkzeug
    FileStorage web received; its stream is handed straight to `requests`
    rather than read into memory, so a large upload is not buffered twice.
    """
    if storage is None or not getattr(storage, 'filename', ''):
        raise ApiValidation('No file was chosen')

    files = {field: (storage.filename, storage.stream, storage.mimetype)}
    try:
        response = _session().post(
            _url(path),
            files=files,
            headers=_headers(kwargs.get('token')),
            timeout=current_app.config['API_TIMEOUT_S'],
        )
    except requests.Timeout as exc:
        raise ApiUnavailable('The upload took too long.') from exc
    except requests.RequestException as exc:
        raise ApiUnavailable('The service is unavailable right now.') from exc

    if not response.ok:
        _raise_for(response)
    return response.json()


def get(path, **kwargs):
    return request('GET', path, **kwargs)


def post(path, **kwargs):
    return request('POST', path, **kwargs)


def patch(path, **kwargs):
    return request('PATCH', path, **kwargs)


def put(path, **kwargs):
    return request('PUT', path, **kwargs)


def delete(path, **kwargs):
    return request('DELETE', path, **kwargs)