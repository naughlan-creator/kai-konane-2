"""The JSON API.

Mounted at `/api` inside this service, not at the root. Two reasons:

* the HTML routes still own `/activities` and `/stories` until #9, so a JSON
  route at the same path would collide
* the gateway forwards `/api/*` without stripping the prefix
  (`proxy_pass http://api:5000;` -- no trailing slash), so a path is identical
  whether you curl the api directly or go through the gateway

Errors come from services as ServiceError subclasses, each carrying the status
it should map to. Handling that once here means no route needs a try/except.
"""
from flask import Blueprint, jsonify, request

from app.services.errors import ServiceError

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.errorhandler(ServiceError)
def _service_error(error):
    """ValidationError -> 400, NotFound -> 404, Conflict -> 409.

    This one belongs on the blueprint: a ServiceError is raised inside a view,
    so Flask already knows which blueprint is handling the request.
    """
    return jsonify(error=str(error)), error.status


def register_error_handlers(app):
    """Routing failures must be registered app-wide, not on the blueprint.

    404 and 405 are raised during URL matching, before Flask knows which
    blueprint a path belongs to -- so `@api_bp.errorhandler(404)` never fires
    for an unmatched /api path and the client gets Flask's HTML error page.
    Checking the path here is what keeps the api's responses JSON while the
    HTML routes keep their normal error pages.
    """
    @app.errorhandler(404)
    def _not_found(error):
        if request.path.startswith('/api/'):
            return jsonify(error='No such endpoint'), 404
        return error

    @app.errorhandler(405)
    def _method_not_allowed(error):
        if request.path.startswith('/api/'):
            return jsonify(error='Method not allowed for this endpoint'), 405
        return error


# Imported for their side effect of registering routes on api_bp. Must come
# after api_bp exists, and are the reason this file has no other logic.
from app.api import content  # noqa: E402,F401
