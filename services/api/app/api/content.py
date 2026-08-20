"""Activities and stories.

The read endpoints take an optional `child_id`. When present, content is
filtered by that child's per-strand learning plan levels and each item carries
the child's progress -- which is what activity_home.html and stories.html need
in a single call rather than one request per card.
"""
from flask import current_app, jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.authz import require_admin, require_child_access
from app.api.serializers import activity_out, story_out
from app.level_predictor import update_child_level
from app.models.activity import StemCode
from app.models.child import EducationLevel, Level, LunchType
from app.models.user import Role
from app.services.activity_service import ActivityService
from app.services.child_service import ChildService
from app.services.errors import NotFound, ValidationError
from app.services.learning_plan_service import LearningPlanService
from app.services.media import library_images, save_upload
from app.services.reward_service import RewardService
from app.services.story_service import StoryService

activity_service = ActivityService()
child_service = ChildService()
story_service = StoryService()
learning_plan_service = LearningPlanService()
reward_service = RewardService()


def _child_id_arg():
    """`?child_id=` as an int, or None. Rejects garbage rather than ignoring it."""
    raw = request.args.get('child_id')
    if raw is None or raw == '':
        return None
    if not raw.isdigit():
        raise ValidationError("child_id must be a number")
    return int(raw)


def _require_child(child_id):
    """A `?child_id=` filter must belong to the caller.

    Without this, any signed-in user could read another child's tailored
    content list -- and the progress attached to it.
    """
    if child_id is not None:
        require_child_access(child_id, child_service)


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
    _require_child(child_id)
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

    require_child_access(child_id, child_service)

    answers = payload.get('answers') or {}
    if not isinstance(answers, dict):
        raise ValidationError("answers must be an object of question_id -> answer_id")

    result, message = activity_service.submit_activity(
        activity_id, child_id, {str(k): str(v) for k, v in answers.items()})
    if result is None:
        raise ValidationError(message)

    # Scoring, the badge and the level nudge belong together. They used to sit
    # in web's route, which meant `web` needed the reward service and the ML
    # predictor -- neither of which can cross the service boundary. A client
    # that scores an attempt without issuing the badge would leave the two
    # permanently out of step.
    reward_service.create_reward_for_activity(child_id, activity_id, result.score)

    new_level = None
    try:
        updated, recommended = update_child_level(child_id)
        if updated:
            learning_plan_service.update_learning_plan_from_recommendation(
                child_id, recommended)
            new_level = recommended.name
    except Exception:
        # A failed prediction must not lose the attempt that was just marked.
        # The score is already committed; the level simply stays where it was.
        current_app.logger.exception(
            "Level update failed for child %s after activity %s",
            child_id, activity_id)

    return jsonify(score=result.score, message=message,
                   recommended_level=new_level), 201


@api_bp.post('/activities/<int:activity_id>/progress')
@token_required
def save_activity_progress(activity_id):
    """Record partial progress without scoring it."""
    payload = request.get_json(silent=True) or {}
    child_id = payload.get('child_id')
    if not isinstance(child_id, int):
        raise ValidationError("child_id is required")

    require_child_access(child_id, child_service)

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
    _require_child(child_id)
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

    require_child_access(child_id, child_service)

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

    require_child_access(child_id, child_service)

    reward, message = story_service.complete_story(story_id, child_id)
    if reward is None:
        raise NotFound(message)

    return jsonify(reward=reward.content, message=message), 201


# ----------------------------------------------- enum lookups for dropdowns

@api_bp.get('/enums')
def list_enums():
    """Every enum the forms need, so `web` can build its dropdowns.

    `web` imports no models, so it cannot iterate EducationLevel to render a
    <select>. Serving them keeps the option list defined in exactly one place --
    a hard-coded copy in a template would drift the first time a member is added
    and fail silently, because Jinja renders an unmatched option as unselected
    rather than raising.
    """
    def members(enum_class):
        return [
            {'name': m.name, 'value': m.value,
             **({'rank': m.rank} if getattr(m, 'rank', None) is not None else {})}
            for m in enum_class
        ]

    return jsonify(
        EducationLevel=members(EducationLevel),
        LunchType=members(LunchType),
        Level=members(Level),
        StemCode=members(StemCode),
        Role=members(Role),
    )


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


# ----------------------------------------------------- authoring: activities

@api_bp.post('/activities')
@token_required
def create_activity():
    """Create an activity with its questions and answers.

    JSON, not multipart. Images are uploaded separately to `POST /media`, which
    returns a filename that is passed here as `cover_image`. Keeping the content
    endpoints JSON-only means one request shape for every client, and an author
    who re-picks an existing library image uploads nothing at all.
    """
    require_admin()
    payload = request.get_json(silent=True) or {}
    activity = activity_service.add_activity(
        title=payload.get('title'),
        stem_code=payload.get('stem_code'),
        level=payload.get('level'),
        cover_image=None,
        questions_data=payload.get('questions') or [],
        description=payload.get('description'),
        existing_cover=payload.get('cover_image'),
    )
    return jsonify(activity=activity_out(activity, questions=True)), 201


@api_bp.patch('/activities/<int:activity_id>')
@token_required
def update_activity(activity_id):
    """Update an activity, syncing its questions and answers.

    A question carrying an `id` is edited in place; one without is new. Dropping
    the ids would make every save duplicate the whole question set.
    """
    require_admin()
    payload = request.get_json(silent=True) or {}
    activity = activity_service.update_activity(
        activity_id,
        title=payload.get('title'),
        stem_code=payload.get('stem_code'),
        level=payload.get('level'),
        cover_image=None,
        questions_data=payload.get('questions'),
        description=payload.get('description'),
        existing_cover=payload.get('cover_image'),
    )
    return jsonify(activity=activity_out(activity, questions=True))


@api_bp.delete('/activities/<int:activity_id>')
@token_required
def delete_activity(activity_id):
    require_admin()
    activity = activity_service.delete_activity(activity_id)
    # The title comes back in the body because the caller flashes "Deleted X"
    # and cannot read it from a 204.
    return jsonify(deleted={'id': activity_id, 'title': activity.title})


# -------------------------------------------------------- authoring: stories

@api_bp.post('/stories')
@token_required
def create_story():
    """Create a story with its pages, in order."""
    require_admin()
    payload = request.get_json(silent=True) or {}
    story = story_service.add_story(
        title=payload.get('title'),
        level=payload.get('level'),
        cover_image=None,
        pages=_pages_from_payload(payload.get('pages')),
        description=payload.get('description'),
        existing_cover=payload.get('cover_image'),
    )
    return jsonify(story=story_out(story, pages=True)), 201


@api_bp.patch('/stories/<int:story_id>')
@token_required
def update_story(story_id):
    require_admin()
    payload = request.get_json(silent=True) or {}
    story = story_service.update_story(
        story_id,
        title=payload.get('title'),
        level=payload.get('level'),
        cover_image=None,
        pages=_pages_from_payload(payload.get('pages')),
        description=payload.get('description'),
        existing_cover=payload.get('cover_image'),
    )
    return jsonify(story=story_out(story, pages=True))


@api_bp.delete('/stories/<int:story_id>')
@token_required
def delete_story(story_id):
    require_admin()
    story = story_service.delete_story(story_id)
    return jsonify(deleted={'id': story_id, 'title': story.title})


def _pages_from_payload(pages):
    """Shape the JSON pages the way StoryService expects them.

    The service takes an `image` file object or an `existing_image` filename;
    over JSON only the latter is ever present.
    """
    if pages is None:
        return None
    return [
        {
            'id': page.get('id') or None,
            'line_of_page': page.get('line_of_page'),
            'image': None,
            'existing_image': page.get('image_filename') or None,
        }
        for page in pages
    ]


# ------------------------------------------------------------------- media

@api_bp.get('/media')
@token_required
def list_media():
    """Every image an author may pick from."""
    return jsonify(images=library_images())


@api_bp.post('/media')
@token_required
def upload_media():
    """Store one uploaded image and return its filename.

    This is the only multipart endpoint in the api. `web` forwards the file it
    received, gets a filename back, and passes that name to the content
    endpoints -- so an image crosses the boundary once, as bytes, and every
    other reference to it is a short string.
    """
    require_admin()
    filename = save_upload(request.files.get('image'))
    if filename is None:
        raise ValidationError(
            "Upload a .png, .jpg, .jpeg, .gif, .webp or .avif image")
    return jsonify(filename=filename), 201
