from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import Role
from services.learning_plan_service import LearningPlanService
from models.child import Child

learning_plan_bp = Blueprint('learning_plan', __name__)

learning_plan_service = LearningPlanService()

@learning_plan_bp.route('/learning_plan/create/<int:child_id>', methods=['GET', 'POST'])
@login_required
def create_learning_plan(child_id):
    if current_user.role != Role.TEACHER:
        flash("You don't have permission to create learning plans")
        return redirect(url_for('user.home'))

    child = Child.query.get(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        learning_plan = learning_plan_service.create_learning_plan(
            child_id=child_id,
            science_level=request.form['science_level'],
            technology_level=request.form['technology_level'],
            engineering_level=request.form['engineering_level'],
            math_level=request.form['math_level'],
            story_level=request.form['story_level']
        )
        flash("Learning plan created successfully")
        return redirect(url_for('learning_plan.view_learning_plan', child_id=child_id))

    return render_template('LearningPlanSystem/create_learning_plan.html', child=child)

@learning_plan_bp.route('/learning_plan/view/<int:child_id>')
@login_required
def view_learning_plan(child_id):
    if current_user.role != Role.TEACHER and current_user.role != Role.PARENT:
        flash("You don't have permission to view learning plans")
        return redirect(url_for('user.home'))

    child = Child.query.get(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    learning_plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if not learning_plan:
        flash("No learning plan found for this child")
        return redirect(url_for('user.home'))

    recommended_activities = learning_plan_service.recommend_activities(child_id)

    return render_template('LearningPlanSystem/view_learning_plan.html', child=child, learning_plan=learning_plan, recommended_activities=recommended_activities, Role=Role)

@learning_plan_bp.route('/learning_plan/update/<int:child_id>', methods=['GET', 'POST'])
@login_required
def update_learning_plan(child_id):
    if current_user.role != Role.TEACHER:
        flash("You don't have permission to update learning plans")
        return redirect(url_for('user.home'))

    child = Child.query.get(child_id)
    if not child:
        flash("Child not found")
        return redirect(url_for('user.home'))

    learning_plan = learning_plan_service.get_learning_plan_by_child(child_id)
    if not learning_plan:
        flash("No learning plan found for this child")
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        updated_learning_plan = learning_plan_service.update_learning_plan(
            learning_plan.id,
            science_level=request.form['science_level'],
            technology_level=request.form['technology_level'],
            engineering_level=request.form['engineering_level'],
            math_level=request.form['math_level'],
            story_level=request.form['story_level']
        )
        if updated_learning_plan:
            flash("Learning plan updated successfully")
        else:
            flash("Failed to update learning plan")
        return redirect(url_for('learning_plan.view_learning_plan', child_id=child_id))

    return render_template('LearningPlanSystem/update_learning_plan.html', child=child, learning_plan=learning_plan, Role=Role)

@learning_plan_bp.route('/learning_plans/manage')
@login_required
def manage_learning_plans():
    if current_user.role != Role.TEACHER:
        flash("You don't have permission to manage learning plans")
        return redirect(url_for('user.home'))

    students = Child.query.filter_by(teacher_id=current_user.id).all()
    return render_template('LearningPlanSystem/manage_learning_plans.html', students=students)