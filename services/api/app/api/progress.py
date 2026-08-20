"""Progress, results and the STEM chart data.

The teacher variants embed one level deeper than the parent variants: a parent
already knows whose child a row belongs to, a teacher does not.
"""
from flask import g, jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.authz import require_child_access, require_owner
from app.api.serializers import progress_out, result_out
from app.services.child_service import ChildService
from app.services.errors import Forbidden, NotFound, ValidationError
from app.services.progress_service import ProgressService
from app.services.result_service import ResultService

child_service = ChildService()
progress_service = ProgressService()
result_service = ResultService()


def _teacher_id_arg():
    raw = request.args.get('teacher_id')
    if raw is None or raw == '':
        return None
    if not raw.isdigit():
        raise ValidationError("teacher_id must be a number")
    return int(raw)


@api_bp.get('/children/<int:child_id>/progress')
@token_required
def child_progress(child_id):
    """One child's progress, with the content title and type embedded --
    parent_progress.html reads progress.learning_content.type.value."""
    require_child_access(child_id, child_service)
    rows = progress_service.get_progress_by_child(child_id)
    return jsonify(progress=[progress_out(row, content=True) for row in rows])


@api_bp.get('/progress')
@token_required
def progress_index():
    """`?teacher_id=` returns every learner's progress for that teacher, with
    the child embedded so the table can be grouped by name."""
    teacher_id = _teacher_id_arg()
    if teacher_id is None:
        raise ValidationError("teacher_id is required")

    require_owner(teacher_id, "Those are not your learners")
    rows = progress_service.get_progress_by_teacher(teacher_id)
    return jsonify(progress=[
        dict(progress_out(row, content=True),
             child={'id': row.child.id,
                    'firstname': row.child.firstname,
                    'lastname': row.child.lastname} if row.child else None)
        for row in rows
    ])


@api_bp.get('/children/<int:child_id>/results')
@token_required
def child_results(child_id):
    """Attempt history, newest first. Embeds the activity because
    parent_results.html reads result.activity.stem_code.value."""
    require_child_access(child_id, child_service)
    rows = result_service.get_results_by_child(child_id)
    return jsonify(results=[result_out(row, activity=True) for row in rows])


@api_bp.get('/results')
@token_required
def results_index():
    teacher_id = _teacher_id_arg()
    if teacher_id is None:
        raise ValidationError("teacher_id is required")

    require_owner(teacher_id, "Those are not your learners")
    rows = result_service.get_results_by_teacher(teacher_id)
    return jsonify(results=[result_out(row, activity=True, child=True)
                            for row in rows])


@api_bp.get('/children/<int:child_id>/stem-levels')
@token_required
def stem_levels(child_id):
    """Mean score per STEM strand, for the radar chart.

    The ownership check moved here with the endpoint. It cannot stay in `web`:
    the gateway sends every /api/* path straight to this service, so a guard in
    web would simply never run. Deny by default -- an unrecognised role gets
    nothing rather than everything.
    """
    child = child_service.get_child(child_id)
    if child is None:
        raise NotFound("No such child")

    role = g.current_role
    viewer_id = g.current_user_id
    if role == 'ADMIN':
        allowed = True
    elif role == 'PARENT':
        allowed = child.parent_id == viewer_id
    elif role == 'TEACHER':
        allowed = child.teacher_id == viewer_id
    elif role == 'CHILD':
        allowed = child.id == viewer_id
    else:
        allowed = False

    if not allowed:
        raise Forbidden("That is not your learner")

    return jsonify(result_service.get_stem_levels(child_id))
