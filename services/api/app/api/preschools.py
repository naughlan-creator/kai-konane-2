"""Preschools.

The list endpoint is deliberately unauthenticated: the signup wizard has to
offer a preschool before anyone has an account, so requiring a token here would
make registration impossible. Nothing sensitive is exposed -- just names.
"""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.serializers import preschool_out
from app.services.errors import NotFound
from app.services.preschool_service import PreschoolService

preschool_service = PreschoolService()


@api_bp.get('/preschools')
def list_preschools():
    return jsonify(preschools=[preschool_out(p)
                               for p in preschool_service.get_preschools()])


@api_bp.get('/preschools/<int:preschool_id>')
@token_required
def get_preschool(preschool_id):
    preschool = preschool_service.get_preschool(preschool_id)
    if preschool is None:
        raise NotFound("No such preschool")
    return jsonify(preschool=preschool_out(preschool, members=True))


@api_bp.post('/preschools')
@token_required
def create_preschool():
    payload = request.get_json(silent=True) or {}
    preschool = preschool_service.add_preschool(payload.get('name'))
    return jsonify(preschool=preschool_out(preschool)), 201


@api_bp.patch('/preschools/<int:preschool_id>')
@token_required
def update_preschool(preschool_id):
    payload = request.get_json(silent=True) or {}
    preschool = preschool_service.update_preschool(preschool_id, payload.get('name'))
    return jsonify(preschool=preschool_out(preschool))


@api_bp.delete('/preschools/<int:preschool_id>')
@token_required
def delete_preschool(preschool_id):
    """Refuses while teachers or learners are still attached -- the service
    raises Conflict, which becomes a 409."""
    preschool_service.delete_preschool(preschool_id)
    return '', 204
