import traceback

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.level_predictor import update_child_level
from app.models.child import Level
from app.routes.auth import child_required
from app.services.activity_service import ActivityService
from app.services.child_service import ChildService
from app.services.learning_plan_service import LearningPlanService
from app.services.reward_service import RewardService

activity_bp = Blueprint('activity', __name__)
activity_service = ActivityService()
reward_service = RewardService()
child_service = ChildService()
learning_plan_service = LearningPlanService()


def _answers_from_form(form, activity):
    """Turn the posted question_<id> fields into {question_id: answer_id}."""
    answers = {}
    for question in activity.questions:
        value = form.get(f'question_{question.id}')
        if value:
            answers[str(question.id)] = value
    return answers


@activity_bp.route('/activities')
@child_required
def activity_home():
    learning_plan = learning_plan_service.get_learning_plan_by_child(current_user.id)
    child = child_service.get_child(current_user.id)

    if not learning_plan:
        flash("No learning plan found. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))

    if not child:
        flash("Unable to load your profile. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))

    fallback_level = child.recommended_level or Level.BEGINNER
    completed_activities = activity_service.get_completed_activities(current_user.id)
    completed_ids = {progress.learning_content_id for progress in completed_activities}

    filtered_activities = []
    for activity in activity_service.get_activities():
        try:
            activity_level = Level.coerce(activity.level)
            if activity_level is None:
                continue

            # Compare against the level for this activity's own STEM strand.
            # The previous version measured everything against a single
            # recommended_level, so the per-subject learning plan did nothing.
            if activity.stem_code is not None:
                strand_level = getattr(
                    learning_plan, f"{activity.stem_code.name.lower()}_level", None
                ) or fallback_level
            else:
                strand_level = fallback_level

            if activity_level.rank <= strand_level.rank:
                activity.is_completed = activity.id in completed_ids
                activity.progress_value = activity_service.get_activity_progress(
                    activity.id, current_user.id)
                filtered_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"Error processing activity {activity.id}: {str(e)}")

    # Sort by level then STEM strand. Level.rank keeps beginner-first ordering;
    # sorting on level.value would give ADVANCED, BEGINNER, INTERMEDIATE.
    filtered_activities.sort(
        key=lambda a: (a.level.rank, a.stem_code.value if a.stem_code else '')
    )

    return render_template('ActivitySystem/activity_home.html',
                           activities=filtered_activities,
                           learning_plan=learning_plan,
                           recommended_level=fallback_level)

@activity_bp.route('/activity/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))
    return render_template('ActivitySystem/activity_detail.html', activity=activity)

@activity_bp.route('/activity/<int:activity_id>/save_progress', methods=['POST'])
@child_required
def save_progress(activity_id):
    answers = request.form.to_dict()
    progress, message = activity_service.save_activity_progress(activity_id, current_user.id, answers)
    if progress is None:
        return jsonify({'message': message}), 404
    return jsonify({'message': message, 'progress': progress.completion_rate})

@activity_bp.route('/activity/<int:activity_id>/submit', methods=['POST'])
@child_required
def submit_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))

    # Marking lives in the service so the score, the result row, the progress row
    # and the learning plan can never drift apart.
    result, message = activity_service.submit_activity(
        activity_id, current_user.id, _answers_from_form(request.form, activity)
    )
    if result is None:
        flash(message, 'error')
        return redirect(url_for('activity.activity_home'))

    flash(message, 'success')
    reward_service.create_reward_for_activity(current_user.id, activity_id, result.score)

    try:
        success, recommended_level = update_child_level(current_user.id)
        if success:
            learning_plan_service.update_learning_plan_from_recommendation(
                current_user.id, recommended_level)
            flash(f'Your learning level has been updated to {recommended_level.name}!', 'info')
        else:
            current_app.logger.error(f"Failed to update learning level for user {current_user.id}")
    except Exception as e:
        current_app.logger.error(f"Error updating learning level for user {current_user.id}: {str(e)}")
        current_app.logger.error(traceback.format_exc())

    return redirect(url_for('activity.activity_home'))

@activity_bp.route('/start/<int:activity_id>', methods=['GET'])
@child_required
def start_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))

    if not activity.questions:
        flash('This activity has no questions yet.', 'warning')
        return redirect(url_for('activity.activity_home'))

    progress = activity_service.get_activity_progress(activity_id, current_user.id)

    return render_template('ActivitySystem/activity_page.html',
                           activity=activity,
                           progress=progress)
