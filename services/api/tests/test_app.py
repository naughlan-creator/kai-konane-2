"""Application wiring: blueprints, config and health endpoints."""
from conftest import flask_app


def test_every_blueprint_is_registered():
    """A blueprint that is defined but never registered is a silent 404."""
    # `import app.routes` would bind the name `app`, not `routes`.
    from app import routes

    defined = {getattr(routes, name).name
               for name in dir(routes) if name.endswith('_bp')}
    registered = set(flask_app.blueprints)
    assert defined <= registered, f"not registered: {sorted(defined - registered)}"


def test_the_api_serves_no_html():
    """Since #9 this service is JSON only.

    A template route reappearing here means presentation logic has leaked back
    across the boundary -- which is exactly how the monolith re-forms.
    """
    paths = [str(rule) for rule in flask_app.url_map.iter_rules()]
    non_api = [p for p in paths
               if not p.startswith('/api/') and not p.startswith('/static/')]
    assert sorted(non_api) == ['/healthz', '/readyz'], non_api


def test_healthz_reports_ok(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'