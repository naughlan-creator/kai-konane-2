"""Progress, results and the STEM chart data.

The teacher variants embed one level deeper than the parent variants: a parent
already knows whose child a row belongs to, a teacher does not.
"""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.serializers import progress_out, result_out
from app.services.errors import ValidationError
from app.services.progress_service import ProgressService
from app.services.result_service import ResultService

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
    rows = result_service.get_results_by_child(child_id)
    return jsonify(results=[result_out(row, activity=True) for row in rows])


@api_bp.get('/results')
@token_required
def results_index():
    teacher_id = _teacher_id_arg()
    if teacher_id is None:
        raise ValidationError("teacher_id is required")

    rows = result_service.get_results_by_teacher(teacher_id)
    return jsonify(results=[result_out(row, activity=True, child=True)
                            for row in rows])


@api_bp.get('/children/<int:child_id>/stem-levels')
@token_required
def stem_levels(child_id):
    """Mean score per STEM strand, for the radar chart.

    This is the endpoint that replaces web's `/api/child_stem_levels/<id>`,
    which the gateway would otherwise swallow. static/js/stem_graph.js fetches
    this path.
    """
    return jsonify(result_service.get_stem_levels(child_id))
