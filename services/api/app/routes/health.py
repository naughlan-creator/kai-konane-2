"""Liveness and readiness endpoints.

Kept apart from the feature blueprints because the container orchestrator
depends on them: /healthz answers "is the process alive", /readyz answers
"can it actually serve traffic". Compose waits on /readyz before starting
dependents, so it must be the one that touches the database.
"""
import os
import time

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.config import db

health_bp = Blueprint('health', __name__)
_START = time.time()


@health_bp.get('/healthz')
def healthz():
    """Liveness. Never touches the database -- a slow query must not look
    like a dead process and get the container killed."""
    return jsonify(status='ok',
                   version=os.getenv('APP_VERSION', 'dev'),
                   uptime_s=int(time.time() - _START))


@health_bp.get('/readyz')
def readyz():
    """Readiness: the database answers."""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify(status='ready')
    except Exception:
        return jsonify(status='not-ready'), 503
