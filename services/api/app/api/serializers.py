"""Model -> JSON, implementing the four serialization rules from
docs/architecture.md.

Every rule exists because a template breaks silently without it:

* datetimes as ISO 8601 with an explicit offset -- JSON has no datetime type,
  and a naive `.isoformat()` gives the client no way to know the zone
* enums as objects, so `.name`, `.value` and `.rank` all survive
* relations embedded to the depth the consuming template actually traverses
* nothing pre-formatted for display; `web` owns presentation
"""
from datetime import date, datetime, timezone


def iso(value):
    """A stored timestamp as an unambiguous ISO 8601 string.

    DateTime columns are timezone-naive and hold UTC by convention (see
    utils.utcnow), so UTC is attached here at the boundary -- which is the only
    place the ambiguity matters.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def enum(member):
    """An enum as `{name, value}`, plus `rank` when the enum is ordered.

    Templates read `.name` for logic and `.value` for display; `rank` carries
    the beginner -> advanced ordering that `.value` cannot, because
    alphabetically ADVANCED sorts before BEGINNER.
    """
    if member is None:
        return None
    out = {'name': member.name, 'value': member.value}
    rank = getattr(member, 'rank', None)
    if rank is not None:
        out['rank'] = rank
    return out


# --------------------------------------------------------------- content

def answer_out(answer):
    return {
        'id': answer.id,
        'content': answer.content,
        'position': answer.position,
        # The activity page needs this to play the right sound on selection.
        # Note it also lets a determined reader see the answer in the payload --
        # see the API notes in docs/architecture.md.
        'is_correct': answer.is_correct,
    }


def question_out(question):
    return {
        'id': question.id,
        'content': question.content,
        'position': question.position,
        'answers': [answer_out(a) for a in question.answers],
    }


def activity_out(activity, questions=False, progress=None):
    """An activity.

    `questions=True` embeds questions and answers -- the detail depth used by
    activity_detail.html and activity_page.html. The list views must not pay
    for it.
    """
    out = {
        'id': activity.id,
        'title': activity.title,
        'description': activity.description,
        'type': enum(activity.type),
        'stem_code': enum(activity.stem_code),
        'level': enum(activity.level),
        'cover_image': activity.cover_image,
        'question_count': len(activity.questions),
    }
    if questions:
        out['questions'] = [question_out(q) for q in activity.questions]
    if progress is not None:
        out['progress'] = progress_out(progress)
    return out


def page_out(page):
    return {
        'id': page.id,
        'line_of_page': page.line_of_page,
        'image_filename': page.image_filename,
        'page_number': page.page_number,
        'is_last_page': page.is_last_page,
    }


def story_out(story, pages=False, progress=None):
    out = {
        'id': story.id,
        'title': story.title,
        'description': story.description,
        'type': enum(story.type),
        'level': enum(story.level),
        'cover_page': story.cover_page,
        'page_count': len(story.pages),
    }
    if pages:
        out['pages'] = [page_out(p) for p in story.pages]
    if progress is not None:
        out['progress'] = progress_out(progress)
    return out


# -------------------------------------------------------------- progress

def progress_out(progress, content=False):
    out = {
        'id': progress.id,
        'completion_rate': progress.completion_rate,
        'total_num_questions': progress.total_num_questions,
        'completed': progress.completed,
        'child_id': progress.child_id,
        'learning_content_id': progress.learning_content_id,
    }
    if content and progress.learning_content is not None:
        # parent_progress.html and teacher_progress.html read
        # progress.learning_content.title and .type.value -- a two-level
        # traversal, so the relation must be embedded, not referenced by id.
        out['learning_content'] = {
            'id': progress.learning_content.id,
            'title': progress.learning_content.title,
            'type': enum(progress.learning_content.type),
        }
    return out


def result_out(result, activity=False, child=False):
    out = {
        'id': result.id,
        'child_id': result.child_id,
        'activity_id': result.activity_id,
        'score': result.score,
        'date_acquired': iso(result.date_acquired),
    }
    if activity and result.activity is not None:
        # parent_results.html reads result.activity.stem_code.value
        out['activity'] = {
            'id': result.activity.id,
            'title': result.activity.title,
            'stem_code': enum(result.activity.stem_code),
        }
    if child and result.child is not None:
        # The teacher views need the learner's name; the parent views do not,
        # because a parent already knows whose child it is.
        out['child'] = {
            'id': result.child.id,
            'firstname': result.child.firstname,
            'lastname': result.child.lastname,
        }
    return out


def learning_plan_out(plan):
    return {
        'id': plan.id,
        'child_id': plan.child_id,
        'science_level': enum(plan.science_level),
        'technology_level': enum(plan.technology_level),
        'engineering_level': enum(plan.engineering_level),
        'math_level': enum(plan.math_level),
        'story_level': enum(plan.story_level),
    }
