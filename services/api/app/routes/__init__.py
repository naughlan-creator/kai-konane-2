"""Non-JSON routes.

All that remains after #9: the health endpoints, which are not part of the JSON
contract and are hit by the container orchestrator rather than by `web`.
The HTML blueprints that used to live here now belong to services/web.
"""
from app.routes.health import health_bp

__all__ = ['health_bp']
