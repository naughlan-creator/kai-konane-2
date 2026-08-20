"""Learning plans and content recommendations."""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.authz import require_child_access
from app.api.serializers import activity_out, learning_plan_out, story_out
from app.models.activity import Activity
from app.models.child import Level
from app.services.child_service import ChildService
from app.services.errors import NotFound, ValidationError
from app.services.learning_plan_service import LearningPlanService

learning_plan_service = LearningPlanService()
child_service = ChildService()

STRANDS = ('science_level', 'technology_level', 'engineering_level',
           'math_level', 'story_level')


@api_bp.get('/learning-plans/child/<int:child_id>')
@token_required
def get_plan(child_id):
    require_child_access(child_id, child_service)
    plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if plan is None:
        raise NotFound("That child has no learning plan yet")
    return jsonify(learning_plan=learning_plan_out(plan))


@api_bp.put('/learning-plans/child/<int:child_id>')
@token_required
def put_plan(child_id):
    """Create or replace a child's plan. PUT because there is exactly one per
    child -- the database enforces it -- so this is idempotent rather than
    additive.

    Body: {"science_level": "BEGINNER", ...} for all five strands.
    """
    require_child_access(child_id, child_service)
    payload = request.get_json(silent=True) or {}

    levels = {}
    for field in STRANDS:
        level = Level.coerce(payload.get(field))
        if level is None:
            raise ValidationError(f"{field} must be BEGINNER, INTERMEDIATE or ADVANCED")
        levels[field] = level

    plan = learning_plan_service.create_learning_plan(
        child_id,
        levels['science_level'],
        levels['technology_level'],
        levels['engineering_level'],
        levels['math_level'],
        levels['story_level'],
    )
    return jsonify(learning_plan=learning_plan_out(plan))


@api_bp.get('/learning-plans/child/<int:child_id>/recommendations')
@token_required
def recommendations(child_id):
    """Content at or below the child's level in every strand, beginner-first.

    Activities and stories come back in separate lists rather than one mixed
    array: the templates render them differently and a client should not have to
    branch on a `type` discriminator to lay the page out.
    """
    require_child_access(child_id, child_service)
    plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if plan is None:
        raise NotFound("That child has no learning plan yet")

    recommended = learning_plan_service.recommend_activities(child_id)

    return jsonify(
        activities=[activity_out(item) for item in recommended
                    if isinstance(item, Activity)],
        stories=[story_out(item) for item in recommended
                 if not isinstance(item, Activity)],
    )
