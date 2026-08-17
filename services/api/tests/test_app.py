"""Application wiring: blueprints, config and health endpoints.

Separate from test_pages.py, which asks whether pages render for the right
role. This file asks whether the app is assembled correctly at all.
"""
from conftest import flask_app


def test_every_blueprint_is_registered():
    """A wildcard-to-explicit import rewrite silently drops names.

    routes/__init__.py used to be consumed with `from routes import *`, so a
    missing blueprint was invisible. Now that app.py imports each one by name,
    this catches an omission at test time instead of as a 404 in the browser.
    """
    # `import app.routes` would bind the name `app`, not `routes`.
    from app import routes

    defined = {getattr(routes, name).name
               for name in dir(routes) if name.endswith('_bp')}
    registered = set(flask_app.blueprints)
    assert defined <= registered, f"not registered: {sorted(defined - registered)}"


def test_healthz_reports_ok(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'