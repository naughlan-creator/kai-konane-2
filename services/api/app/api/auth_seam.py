"""The seam where #8 attaches token authentication.

Right now this is a no-op, so #7's endpoints can be built and tested without
waiting on the auth work. That is safe only because nothing routes to `/api/*`
from outside yet -- the gateway arrives in #10, and #8 lands before it.

#8 replaces the body of `token_required` with signature verification and puts
the authenticated user on `flask.g`. Nothing else in the api needs to change,
which is the point of having the seam rather than scattering checks later.
"""
import functools


def token_required(view):
    """Marks an endpoint as requiring `Authorization: Bearer` (see #8)."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        # TODO(#8): verify the signed token, 401 on failure, set g.current_user.
        return view(*args, **kwargs)

    wrapper.__token_required__ = True
    return wrapper
