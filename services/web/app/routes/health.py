"""Liveness for the web container."""
from flask import Blueprint, current_app, jsonify

health_bp = Blueprint('health', __name__)


@health_bp.get('/healthz')
def healthz():
    """Process is up. Deliberately does not call the api.

    If this checked the api, a slow api would make web look dead and get its
    container killed — one failure would take down two services.
    """
    return jsonify(status='ok', service='web',
                   api_base=current_app.config['API_BASE_URL'])