"""Activities and stories.

The read endpoints take an optional `child_id`. When present, content is
filtered by that child's per-strand learning plan levels and each item carries
the child's progress -- which is what activity_home.html and stories.html need
in a single call rather than one request per card.
"""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.serializers import activity_out, story_out
from app.models.activity import StemCode
from app.models.child import Level
from app.services.activity_service import ActivityService
from app.services.errors import NotFound, ValidationError
from app.services.learning_plan_service import LearningPlanService
from app.services.story_service import StoryService

activity_service = ActivityService()
story_service = StoryService()
learning_plan_service = LearningPlanService()


def _child_id_arg():
    """`?child_id=` as an int, or None. Rejects garbage rather than ignoring it."""
    raw = request.args.get('child_id')
    if raw is None or raw == '':
        return None
    if not raw.isdigit():
        raise ValidationError("child_id must be a number")
    return int(raw)


def _progress_by_content(child_id):
    """One lookup for the child's progress, keyed by content id.

    Fetching per card would be an N+1 across the whole listing.
    """
    if child_id is None:
        return {}
    return {p.learning_content_id: p
            for p in activity_service.get_progress_for_child(child_id)}


# ------------------------------------------------------------- activities

@api_bp.get('/activities')
@token_required
def list_activities():
    """Activities, optionally scoped to what one child may see.

    Without `child_id` this is the authoring view: everything, unfiltered.
    """
    child_id = _child_id_arg()
    progress = _progress_by_content(child_id)

    if child_id is not None:
        plan = learning_plan_service.get_learning_plan_by_child(child_id)
        if plan is None:
            raise NotFound("That child has no learning plan yet")
        activities = []
        for strand in StemCode:
            level = plan.get_level(strand)
            if level is None:
                continue
            activities.extend(
                activity_service.get_activities_for_strand(strand, level))
    else:
        activities = activity_service.get_activities()

    # Beginner-first, then by strand. Sorting on level.value would order these
    # alphabetically: ADVANCED, BEGINNER, INTERMEDIATE.
    activities.sort(key=lambda a: (a.level.rank, a.stem_code.value, a.id))

    return jsonify(activities=[
        activity_out(a, progress=progress.get(a.id)) for a in activities
    ])


@api_bp.get('/activities/<int:activity_id>')
@token_required
def get_activity(activity_id):
    """One activity with its questions and answers embedded."""
    activity = activity_service.get_activity(activity_id)
    if activity is None:
        raise NotFound("That activity no longer exists")

    child_id = _child_id_arg()
    progress = None
    if child_id is not None:
        progress = activity_service.get_or_create_progress(activity_id, child_id)

    return jsonify(activity=activity_out(activity, questions=True, progress=progress))


@api_bp.post('/activities/<int:activity_id>/submit')
@token_required
def submit_activity(activity_id):
    """Mark an attempt. Body: {"child_id": N, "answers": {"<question_id>": "<answer_id>"}}."""
    payload = request.get_json(silent=True) or {}
    child_id = payload.get('child_id')
    if not isinstance(child_id, int):
        raise ValidationError("child_id is required")

    answers = payload.get('answers') or {}
    if not isinstance(answers, dict):
        raise ValidationError("answers must be an object of question_id -> answer_id")

    result, message = activity_service.submit_activity(
        activity_id, child_id, {str(k): str(v) for k, v in answers.items()})
    if result is None:
        raise ValidationError(message)

    return jsonify(score=result.score, message=message), 201


@api_bp.post('/activities/<int:activity_id>/progress')
@token_required
def save_activity_progress(activity_id):
    """Record partial progress without scoring it."""
    payload = request.get_json(silent=True) or {}
    child_id = payload.get('child_id')
    if not isinstance(child_id, int):
        raise ValidationError("child_id is required")

    progress, message = activity_service.save_activity_progress(
        activity_id, child_id, payload.get('answers') or {})
    if progress is None:
        raise NotFound(message)

    return jsonify(completion_rate=progress.completion_rate, message=message)


# ---------------------------------------------------------------- stories

@api_bp.get('/stories')
@token_required
def list_stories():
    child_id = _child_id_arg()
    progress = _progress_by_content(child_id)

    if child_id is not None:
        plan = learning_plan_service.get_learning_plan_by_child(child_id)
        if plan is None:
            raise NotFound("That child has no learning plan yet")
        stories = story_service.get_stories_for_level(plan.story_level)
    else:
        stories = story_service.get_stories()

    stories.sort(key=lambda s: (s.level.rank, s.id))

    return jsonify(stories=[
        story_out(s, progress=progress.get(s.id)) for s in stories
    ])


@api_bp.get('/stories/<int:story_id>')
@token_required
def get_story(story_id):
    """One story with its pages embedded, in page order."""
    story = story_service.get_story(story_id)
    if story is None:
        raise NotFound("That story no longer exists")

    child_id = _child_id_arg()
    progress = None
    if child_id is not None:
        progress = story_service.get_or_create_progress(story_id, child_id)

    return jsonify(story=story_out(story, pages=True, progress=progress))


@api_bp.post('/stories/<int:story_id>/progress')
@token_required
def save_story_progress(story_id):
    """Body: {"child_id": N, "current_page": N}."""
    payload = request.get_json(silent=True) or {}
    child_id = payload.get('child_id')
    if not isinstance(child_id, int):
        raise ValidationError("child_id is required")

    try:
        current_page = int(payload.get('current_page', 0))
    except (TypeError, ValueError):
        raise ValidationError("current_page must be a number") from None

    progress, message = story_service.save_story_progress(story_id, child_id, current_page)
    if progress is None:
        raise NotFound(message)

    return jsonify(completion_rate=progress.completion_rate, message=message)


@api_bp.post('/stories/<int:story_id>/complete')
@token_required
def complete_story(story_id):
    """Mark a story read and issue its badge. Idempotent: re-reading does not
    hand out a second badge."""
    payload = request.get_json(silent=True) or {}
    child_id = payload.get('child_id')
    if not isinstance(child_id, int):
        raise ValidationError("child_id is required")

    reward, message = story_service.complete_story(story_id, child_id)
    if reward is None:
        raise NotFound(message)

    return jsonify(reward=reward.content, message=message), 201


# ------------------------------------------------- level lookup for filters

@api_bp.get('/levels')
def list_levels():
    """The Level enum, ordered. `web` needs it to build its dropdowns without
    importing the model."""
    return jsonify(levels=[
        {'name': level.name, 'value': level.value, 'rank': level.rank}
        for level in sorted(Level, key=lambda item: item.rank)
    ])


@api_bp.get('/stem-codes')
def list_stem_codes():
    return jsonify(stem_codes=[
        {'name': code.name, 'value': code.value} for code in StemCode
    ])
