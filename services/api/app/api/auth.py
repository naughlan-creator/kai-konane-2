"""Authentication and registration.

`web` never touches a password hash. It posts credentials here, receives a
user payload plus a signed bearer token, and stores both in its session cookie.
Every later call carries that token; see app/api/auth_seam.py.

The endpoints in this module are the only unauthenticated writes in the api, and
they have to be: you cannot present a token before you have an account.
"""
from flask import current_app, jsonify, request

from app.api import api_bp
from app.api.auth_seam import issue_token
from app.api.serializers import user_out
from app.services.errors import ValidationError
from app.services.registration_service import RegistrationService

registration_service = RegistrationService()


@api_bp.post('/auth/login')
def login():
    """Verify credentials. Body: {"username": ..., "password": ...}.

    401 on failure with a deliberately vague message -- distinguishing "no such
    user" from "wrong password" tells an attacker which usernames exist.
    """
    payload = request.get_json(silent=True) or {}
    user = registration_service.authenticate(payload.get('username'),
                                            payload.get('password'))
    if user is None:
        return jsonify(error='Invalid username or password'), 401

    return jsonify(
        user=user_out(user, relations=True),
        token=issue_token(user),
        expires_in=current_app.config['API_TOKEN_TTL_S'],
    )


@api_bp.get('/users/availability')
def availability():
    """Is this username or email free? Advisory -- see RegistrationService."""
    return jsonify(**registration_service.availability(
        username=request.args.get('username'),
        email=request.args.get('email')))


@api_bp.post('/parents')
def register_parent():
    """Create a parent, their children and each child's learning plan.

    One request, one transaction. The multi-screen wizard is a `web` concern;
    the api sees the finished family.
    """
    payload = request.get_json(silent=True) or {}
    children = payload.get('children')
    if not isinstance(children, list):
        raise ValidationError("children must be a list")

    parent, created = registration_service.register_parent(
        username=payload.get('username'),
        email=payload.get('email'),
        password=payload.get('password'),
        firstname=payload.get('firstname'),
        lastname=payload.get('lastname'),
        education_level=payload.get('education_level'),
        preschool_id=payload.get('preschool_id'),
        children=children,
    )

    return jsonify(
        parent=user_out(parent),
        children=[user_out(child) for child in created],
    ), 201


@api_bp.post('/teachers')
def register_teacher():
    payload = request.get_json(silent=True) or {}
    teacher = registration_service.register_teacher(
        username=payload.get('username'),
        email=payload.get('email'),
        password=payload.get('password'),
        firstname=payload.get('firstname'),
        lastname=payload.get('lastname'),
        preschool_id=payload.get('preschool_id'),
    )
    return jsonify(teacher=user_out(teacher)), 201
