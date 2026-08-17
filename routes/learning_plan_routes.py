from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from config import db
from level_predictor import update_child_level
from models.child import Child, Level
from models.user import Role
from routes.auth import roles_required, teacher_required
from services.learning_plan_service import LearningPlanService

learning_plan_bp = Blueprint('learning_plan', __name__)

learning_plan_service = LearningPlanService()


def _teachers_child(child_id):
    """Return the child if the signed-in teacher is allowed to see them."""
    child = db.session.get(Child, child_id)
    if child is None:
        return None
    if current_user.role == Role.TEACHER and child.teacher_id != current_user.id:
        return None
    if current_user.role == Role.PARENT and child.parent_id != current_user.id:
        return None
    return child


@learning_plan_bp.route('/learning_plan/create/<int:child_id>', methods=['GET', 'POST'])
@teacher_required
def create_learning_plan(child_id):
    child = _teachers_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        success, recommended_level = update_child_level(child_id)

        if success:
            levels = [recommended_level] * 5
            message = "Learning plan created successfully with ML recommendations"
        else:
            # Fall back to the teacher's form values. These arrive as strings and
            # are coerced to Level inside the service.
            levels = [request.form.get(field) for field in
                      ('science_level', 'technology_level', 'engineering_level',
                       'math_level', 'story_level')]
            if any(Level.coerce(value) is None for value in levels):
                flash("Please choose a level for every subject")
                return render_template('LearningPlanSystem/create_learning_plan.html',
                                       child=child, Level=Level)
            message = "Learning plan created with manual settings"

        # create_learning_plan no longer re-runs the predictor and discards these
        # arguments, and it updates an existing plan instead of inserting a
        # second one for the same child.
        learning_plan_service.create_learning_plan(child_id, *levels)
        flash(message)
        return redirect(url_for('learning_plan.view_learning_plan', child_id=child_id))

    return render_template('LearningPlanSystem/create_learning_plan.html', child=child, Level=Level)

@learning_plan_bp.route('/learning_plan/view/<int:child_id>')
@roles_required(Role.TEACHER, Role.PARENT)
def view_learning_plan(child_id):
    child = _teachers_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    learning_plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if not learning_plan:
        flash("No learning plan found for this child")
        return redirect(url_for('user.home'))

    recommended_activities = learning_plan_service.recommend_activities(child_id)

    return render_template('LearningPlanSystem/view_learning_plan.html', child=child,
                           learning_plan=learning_plan,
                           recommended_activities=recommended_activities, Role=Role)

@learning_plan_bp.route('/learning_plan/update/<int:child_id>', methods=['GET', 'POST'])
@teacher_required
def update_learning_plan(child_id):
    child = _teachers_child(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    learning_plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if not learning_plan:
        flash("No learning plan found for this child")
        return redirect(url_for('learning_plan.create_learning_plan', child_id=child_id))

    if request.method == 'POST':
        updated_learning_plan = learning_plan_service.update_learning_plan(
            learning_plan.id,
            science_level=request.form.get('science_level'),
            technology_level=request.form.get('technology_level'),
            engineering_level=request.form.get('engineering_level'),
            math_level=request.form.get('math_level'),
            story_level=request.form.get('story_level')
        )
        if updated_learning_plan:
            flash("Learning plan updated successfully")
        else:
            flash("Failed to update learning plan")
        return redirect(url_for('learning_plan.view_learning_plan', child_id=child_id))

    return render_template('LearningPlanSystem/update_learning_plan.html', child=child,
                           learning_plan=learning_plan, Role=Role, Level=Level)

@learning_plan_bp.route('/learning_plans/manage')
@teacher_required
def manage_learning_plans():
    students = Child.query.filter_by(teacher_id=current_user.id).all()
    return render_template('LearningPlanSystem/manage_learning_plans.html', students=students)
