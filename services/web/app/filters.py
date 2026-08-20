"""Jinja filters.

`web` receives datetimes as ISO 8601 strings, and a string has no `.strftime`.
Jinja renders a failed attribute lookup as empty rather than raising, so without
this filter the dates would quietly disappear from five templates instead of
producing an error anyone would notice.
"""
from datetime import datetime


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


def register_filters(app):
    app.jinja_env.filters['datetime'] = datetimeformat