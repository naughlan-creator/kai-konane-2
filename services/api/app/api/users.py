"""Users, and the two relationship lookups web's role guards depend on."""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.authz import (
    child_or_403,
    current_user_id,
    require_admin,
    require_owner,
    require_self_or_admin,
    require_visible_user,
)
from app.api.serializers import user_out
from app.models.child import Child
from app.services.child_service import ChildService
from app.services.errors import Forbidden, NotFound, ValidationError
from app.services.parent_service import ParentService
from app.services.teacher_service import TeacherService
from app.services.user_service import UserService

user_service = UserService()
parent_service = ParentService()
teacher_service = TeacherService()
child_service = ChildService()


@api_bp.get('/users/<int:user_id>')
@token_required
def get_user(user_id):
    """Rehydrate a session user.

    `relations=True` embeds children or students, so web's user_loader makes one
    call per request rather than one per `current_user.children` reference.
    """
    require_visible_user(user_id)
    user = user_service.get_user(user_id)
    if user is None:
        raise NotFound("No such user")
    return jsonify(user=user_out(user, relations=True))


@api_bp.get('/users')
@token_required
def list_users():
    """Admin listing. Never includes password hashes -- see user_out."""
    require_admin()
    return jsonify(users=[user_out(u, profile=False)
                          for u in user_service.get_users()])


@api_bp.patch('/users/<int:user_id>')
@token_required
def update_user(user_id):
    """Update the shared account fields. Raises Conflict on a taken
    username or email, which the api maps to 409."""
    require_self_or_admin(user_id)
    payload = request.get_json(silent=True) or {}
    user = user_service.update_user_profile(
        user_id,
        payload.get('username'),
        payload.get('email'),
        payload.get('password'),
    )
    return jsonify(user=user_out(user))


@api_bp.delete('/users/<int:user_id>')
@token_required
def delete_user(user_id):
    require_admin()
    if user_id == current_user_id():
        raise Forbidden("You cannot delete your own account")
    user_service.delete_user(user_id)
    return '', 204


@api_bp.get('/parents/<int:parent_id>/children')
@token_required
def parent_children(parent_id):
    require_owner(parent_id, "Those are not your children")
    parent = parent_service.get_parent(parent_id)
    if parent is None:
        raise NotFound("No such parent")
    return jsonify(children=[user_out(c) for c in parent.children])


@api_bp.get('/teachers/<int:teacher_id>/students')
@token_required
def teacher_students(teacher_id):
    require_owner(teacher_id, "Those are not your learners")
    teacher = teacher_service.get_teacher(teacher_id)
    if teacher is None:
        raise NotFound("No such teacher")
    return jsonify(students=[user_out(c) for c in teacher.students])


@api_bp.get('/teachers')
@token_required
def list_teachers():
    """Used by the signup wizard to offer a teacher per child."""
    return jsonify(teachers=[user_out(t, relations=False)
                             for t in teacher_service.get_teachers()])


@api_bp.patch('/parents/<int:parent_id>')
@token_required
def update_parent(parent_id):
    """Update a parent's profile.

    Changing education_level also updates every child's parent_education,
    because the level model reads that snapshot -- see ParentService.
    """
    require_self_or_admin(parent_id)
    payload = request.get_json(silent=True) or {}
    parent = parent_service.update_parent_profile(
        parent_id,
        payload.get('firstname'),
        payload.get('lastname'),
        payload.get('education_level'),
    )
    return jsonify(parent=user_out(parent))


@api_bp.patch('/teachers/<int:teacher_id>')
@token_required
def update_teacher(teacher_id):
    require_self_or_admin(teacher_id)
    payload = request.get_json(silent=True) or {}
    teacher = teacher_service.update_teacher_profile(
        teacher_id, payload.get('firstname'), payload.get('lastname'))
    return jsonify(teacher=user_out(teacher))


@api_bp.get('/children/<int:child_id>')
@token_required
def get_child(child_id):
    child = child_or_403(child_id, child_service)
    if child is None:
        raise NotFound("No such child")
    return jsonify(child=user_out(child))


@api_bp.patch('/children/<int:child_id>')
@token_required
def update_child(child_id):
    if child_or_403(child_id, child_service) is None:
        raise NotFound("No such child")
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get('age', 0), (int, str)):
        raise ValidationError("age must be a whole number")

    child = parent_service.update_child_profile(
        child_id,
        payload.get('firstname'),
        payload.get('lastname'),
        payload.get('age'),
        payload.get('gender'),
        payload.get('race_ethnicity'),
        payload.get('lunch_type'),
    )
    return jsonify(child=user_out(child))


@api_bp.get('/children')
@token_required
def list_children():
    """Filtered by `?parent_id=` or `?teacher_id=`; unfiltered is admin-only.

    The filter is checked against the token, not trusted from the query string:
    `?parent_id=` naming someone else would otherwise list their children.
    """
    parent_id = request.args.get('parent_id')
    teacher_id = request.args.get('teacher_id')

    if not parent_id and not teacher_id:
        require_admin()

    query = Child.query
    if parent_id:
        if not parent_id.isdigit():
            raise ValidationError("parent_id must be a number")
        require_owner(int(parent_id), "Those are not your children")
        query = query.filter_by(parent_id=int(parent_id))
    if teacher_id:
        if not teacher_id.isdigit():
            raise ValidationError("teacher_id must be a number")
        require_owner(int(teacher_id), "Those are not your learners")
        query = query.filter_by(teacher_id=int(teacher_id))

    return jsonify(children=[user_out(c) for c in query.order_by(Child.id).all()])
