"""Expected, user-correctable service failures.

Services raise these instead of returning sentence-shaped strings. That gives
each caller what it actually needs:

* `web` catches ServiceError and flashes `str(error)`
* `api` (from Day 2) catches it and returns `{"error": str(error)}, error.status`

A service that returns "User not updated!!!" can serve neither, because the
caller cannot tell success from failure without string matching.
"""


class ServiceError(Exception):
    """Base class. The message is safe to show a user."""
    status = 400


class ValidationError(ServiceError):
    """Input was missing or malformed."""
    status = 400


class NotFound(ServiceError):
    """The requested record does not exist."""
    status = 404


class Conflict(ServiceError):
    """The request collides with existing data (duplicate, in-use, ...)."""
    status = 409


class Forbidden(ServiceError):
    """Authenticated, but not allowed to touch this object."""

    status = 403