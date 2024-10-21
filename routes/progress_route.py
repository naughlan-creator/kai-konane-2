from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import Role
from services.progress_service import ProgressService
from services.result_service import ResultService
from models.activity import Activity, StemCode
from models.result import Result
from models.child import Child
from services.activity_service import ActivityService
from services.story_service import StoryService
from sqlalchemy import func
from config import db

progress_bp = Blueprint('progress', __name__)

progress_service = ProgressService()
result_service = ResultService()
activity_service = ActivityService()
story_service = StoryService()

@progress_bp.route('/parent/progress')
@login_required
def parent_progress():
    if current_user.role != Role.PARENT:
        flash("You don't have permission to view this page")
        return redirect(url_for('index'))

    children = current_user.children
    progress_data = {}
    for child in children:
        progress_data[child.id] = progress_service.get_progress_by_child(child.id)

    return render_template('ProgressSystem/parent_progress.html', children=children, progress_data=progress_data)

@progress_bp.route('/parent/results')
@login_required
def parent_results():
    if current_user.role != Role.PARENT:
        flash("You don't have permission to view this page")
        return redirect(url_for('index'))

    children = current_user.children
    results_data = {}
    for child in children:
        results_data[child.id] = result_service.get_results_by_child(child.id)

    return render_template('ProgressSystem/parent_results.html', children=children, results_data=results_data)

@progress_bp.route('/teacher/progress')
@login_required
def teacher_progress():
    if current_user.role != Role.TEACHER:
        flash("You don't have permission to view this page")
        return redirect(url_for('index'))

    progress_data = progress_service.get_progress_by_teacher(current_user.id)
    return render_template('ProgressSystem/teacher_progress.html', progress_data=progress_data)

@progress_bp.route('/teacher/results')
@login_required
def teacher_results():
    if current_user.role != Role.TEACHER:
        flash("You don't have permission to view this page")
        return redirect(url_for('index'))

    results_data = result_service.get_results_by_teacher(current_user.id)
    return render_template('ProgressSystem/teacher_results.html', results_data=results_data)

@progress_bp.route('/api/child_stem_levels/<int:child_id>')
@login_required
def get_child_stem_levels(child_id):
    # Check if the current user has permission to view this child's data
    if current_user.role.name == 'parent':
        if child_id not in [child.id for child in current_user.children]:
            return jsonify({'error': 'Unauthorized'}), 403
    elif current_user.role.name == 'teacher':
        if child_id not in [student.id for student in current_user.students]:
            return jsonify({'error': 'Unauthorized'}), 403

    # Fetch the child's results
    results = (
        db.session.query(
            Activity.stem_code,
            func.avg(Result.score).label('avg_score')
        )
        .join(Result, Result.activity_id == Activity.id)
        .filter(Result.child_id == child_id)
        .group_by(Activity.stem_code)
        .all()
    )

    # Initialize stem_levels dictionary with default values
    stem_levels = {stem_code.name.lower(): 0 for stem_code in StemCode}

    # Update stem_levels with actual scores
    for stem_code, avg_score in results:
        stem_levels[stem_code.name.lower()] = round(avg_score, 2)

    return jsonify(stem_levels)
