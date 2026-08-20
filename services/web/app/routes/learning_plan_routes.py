"""Learning plans.

`PUT /learning-plans/child/{id}` creates or replaces, because there is exactly
one plan per child. That is why create and update here both call the same
endpoint rather than choosing between POST and PATCH.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import api_client
from app.roles import Role
from app.routes.auth import roles_required, teacher_required

learning_plan_bp = Blueprint('learning_plan', __name__)

STRANDS = ('science_level', 'technology_level', 'engineering_level',
           'math_level', 'story_level')


def _visible_child(child_id):
    """The child, if the signed-in user is allowed to see them.

    Returns None rather than raising so every caller can flash and redirect,
    which is what these form flows do.
    """
    try:
        child = api_client.get(f'children/{child_id}')['child']
    except api_client.ApiError:
        return None

    if current_user.role == Role.TEACHER and child.get('teacher_id') != current_user.id:
        return None
    if current_user.role == Role.PARENT and child.get('parent_id') != current_user.id:
        return None
    return child


def _levels():
    try:
        return api_client.get('enums')['Level']
    except api_client.ApiError:
        return []


@learning_plan_bp.route('/learning_plan/create/<int:child_id>',
                        methods=['GET', 'POST'])
@teacher_required
def create_learning_plan(child_id):
    child = _visible_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        levels = {field: request.form.get(field) for field in STRANDS}
        try:
            api_client.put(f'learning-plans/child/{child_id}', json=levels)
        except api_client.ApiValidation:
            flash("Please choose a level for every subject")
            return render_template('LearningPlanSystem/create_learning_plan.html',
                                   child=child, Level=_levels())
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('LearningPlanSystem/create_learning_plan.html',
                                   child=child, Level=_levels())

        flash("Learning plan created")
        return redirect(url_for('learning_plan.view_learning_plan',
                                child_id=child_id))

    return render_template('LearningPlanSystem/create_learning_plan.html',
                           child=child, Level=_levels())


@learning_plan_bp.route('/learning_plan/view/<int:child_id>')
@roles_required(Role.TEACHER, Role.PARENT)
def view_learning_plan(child_id):
    child = _visible_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    try:
        learning_plan = api_client.get(
            f'learning-plans/child/{child_id}')['learning_plan']
    except api_client.ApiNotFound:
        flash("No learning plan found for this child")
        return redirect(url_for('user.home'))

    recommended = api_client.get(f'learning-plans/child/{child_id}/recommendations')
    # The template iterates one list; the api separates activities from stories
    # so a client does not have to branch on a type discriminator.
    recommended_activities = recommended['activities'] + recommended['stories']

    return render_template('LearningPlanSystem/view_learning_plan.html',
                           child=child, learning_plan=learning_plan,
                           recommended_activities=recommended_activities,
                           Role=Role)


@learning_plan_bp.route('/learning_plan/update/<int:child_id>',
                        methods=['GET', 'POST'])
@teacher_required
def update_learning_plan(child_id):
    child = _visible_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    try:
        learning_plan = api_client.get(
            f'learning-plans/child/{child_id}')['learning_plan']
    except api_client.ApiNotFound:
        flash("No learning plan found for this child")
        return redirect(url_for('learning_plan.create_learning_plan',
                                child_id=child_id))

    if request.method == 'POST':
        levels = {field: request.form.get(field) for field in STRANDS}
        try:
            api_client.put(f'learning-plans/child/{child_id}', json=levels)
            flash("Learning plan updated successfully")
        except api_client.ApiError as e:
            flash(e.message or "Failed to update learning plan", 'error')
        return redirect(url_for('learning_plan.view_learning_plan',
                                child_id=child_id))

    return render_template('LearningPlanSystem/update_learning_plan.html',
                           child=child, learning_plan=learning_plan,
                           Role=Role, Level=_levels())


@learning_plan_bp.route('/learning_plans/manage')
@teacher_required
def manage_learning_plans():
    students = api_client.get(
        'children', params={'teacher_id': current_user.id})['children']
    return render_template('LearningPlanSystem/manage_learning_plans.html',
                           students=students)
