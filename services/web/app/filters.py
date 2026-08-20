"""Jinja filters.

`web` receives datetimes as ISO 8601 strings, and a string has no `.strftime`.
Jinja renders a failed attribute lookup as empty rather than raising, so without
this filter the dates would quietly disappear from five templates instead of
producing an error anyone would notice.
"""
from datetime import datetime

from flask import current_app


def datetimeformat(value, fmt='%Y-%m-%d %H:%M'):
    """Format an ISO 8601 string, a date, or a datetime.

    Returns the input unchanged if it cannot be parsed -- a malformed timestamp
    should look wrong on the page, not blank it or 500 the request.
    """
    if not value:
        return ''
    if isinstance(value, datetime):
        return value.strftime(fmt)
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).strftime(fmt)
    except (TypeError, ValueError):
        return str(value)


def content_image(filename):
    """URL for a content image, which the api owns.

    Covers and page pictures are uploaded through the api and stored beside it,
    so they are not in web's static folder and never will be. Pointing an
    <img> at web's /static would 404 for anything uploaded after the split --
    silently, because a broken image is not an error anyone's tests catch.

    web's own assets -- css, js, the logo -- stay on url_for('static').

    Built from API_PUBLIC_URL, not API_BASE_URL. The browser fetches this, and
    the browser cannot resolve 'api' -- that name only exists inside the compose
    network. Using the server-to-server base here produced an <img> pointing at
    http://api:5000 and a broken picture on every story page.
    """
    if not filename:
        return ''
    return f"{api_public_url()}/api/media/{filename}"


def api_public_url():
    """The base the browser should use to reach the api.

    Empty behind the gateway, which serves both services from one origin.
    """
    return current_app.config['API_PUBLIC_URL']


def register_filters(app):
    app.jinja_env.filters['datetime'] = datetimeformat
    # A global, not a filter: templates call it like url_for().
    app.jinja_env.globals['content_image'] = content_image
    # Templates hand this to the scripts that fetch from the api directly.
    app.jinja_env.globals['api_public_url'] = api_public_url