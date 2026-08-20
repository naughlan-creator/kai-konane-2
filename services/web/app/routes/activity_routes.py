"""Activities.

Per-strand filtering, scoring, the badge and the level nudge all happen in the
api. This module posts the form and renders the result.
"""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import api_client
from app.routes.auth import child_required

activity_bp = Blueprint('activity', __name__)


def _answers_from_form(form, activity):
    """Turn the posted question_<id> fields into {question_id: answer_id}."""
    answers = {}
    for question in activity['questions']:
        value = form.get(f"question_{question['id']}")
        if value:
            answers[str(question['id'])] = value
    return answers


@activity_bp.route('/activities')
@child_required
def activity_home():
    try:
        activities = api_client.get(
            'activities', params={'child_id': current_user.id})['activities']
        learning_plan = api_client.get(
            f'learning-plans/child/{current_user.id}')['learning_plan']
    except api_client.ApiNotFound:
        flash("No learning plan found. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('user.home'))

    # The template reads activity.is_completed and activity.progress_value; the
    # api sends a nested progress object instead.
    for activity in activities:
        progress = activity.get('progress') or {}
        activity['is_completed'] = progress.get('completed', False)
        activity['progress_value'] = progress.get('completion_rate', 0)

    return render_template('ActivitySystem/activity_home.html',
                           activities=activities,
                           learning_plan=learning_plan,
                           recommended_level=getattr(current_user,
                                                     'recommended_level', None))


@activity_bp.route('/activity/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    try:
        activity = api_client.get(f'activities/{activity_id}')['activity']
    except api_client.ApiNotFound:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))
    return render_template('ActivitySystem/activity_detail.html',
                           activity=activity)


@activity_bp.route('/activity/<int:activity_id>/save_progress', methods=['POST'])
@child_required
def save_progress(activity_id):
    try:
        result = api_client.post(f'activities/{activity_id}/progress',
                                 json={'child_id': current_user.id,
                                       'answers': request.form.to_dict()})
    except api_client.ApiError as e:
        return jsonify({'message': e.message}), 404
    return jsonify({'message': result['message'],
                    'progress': result['completion_rate']})


@activity_bp.route('/activity/<int:activity_id>/submit', methods=['POST'])
@child_required
def submit_activity(activity_id):
    try:
        activity = api_client.get(f'activities/{activity_id}')['activity']
    except api_client.ApiNotFound:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))

    try:
        # One call marks the attempt, logs the result, issues the badge and
        # nudges the plan. Splitting those across calls would let a client
        # score an attempt without awarding the badge.
        result = api_client.post(f'activities/{activity_id}/submit',
                                 json={'child_id': current_user.id,
                                       'answers': _answers_from_form(
                                           request.form, activity)})
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('activity.activity_home'))

    flash(result['message'], 'success')
    if result.get('recommended_level'):
        flash(f"Your learning level has been updated to "
              f"{result['recommended_level']}!", 'info')

    return redirect(url_for('activity.activity_home'))


@activity_bp.route('/start/<int:activity_id>', methods=['GET'])
@child_required
def start_activity(activity_id):
    try:
        activity = api_client.get(f'activities/{activity_id}')['activity']
    except api_client.ApiNotFound:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))

    if not activity['questions']:
        flash('This activity has no questions yet.', 'warning')
        return redirect(url_for('activity.activity_home'))

    progress = (activity.get('progress') or {}).get('completion_rate', 0)

    return render_template('ActivitySystem/activity_page.html',
                           activity=activity, progress=progress)
