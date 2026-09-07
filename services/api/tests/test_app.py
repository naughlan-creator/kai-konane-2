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
    
    The three exceptions are all INFRASTRUCTURE endpoints, not part of the JSON
    contract, which is why they sit at the root rather than under /api:

      /healthz  /readyz   the orchestrator's liveness and readiness probes
      /metrics             Prometheus scrapes it; the gateway does not route
                           to it, and web never calls it

    This list is deliberately exhaustive rather than a prefix match. Adding a
    fourth should require editing this line and thinking about why.
    """
    paths = [str(rule) for rule in flask_app.url_map.iter_rules()]
    non_api = [p for p in paths
               if not p.startswith('/api/') and not p.startswith('/static/')]
    assert sorted(non_api) == ['/healthz', '/metrics', '/readyz'], non_api


def test_healthz_reports_ok(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'