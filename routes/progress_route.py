from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from config import db
from models.activity import Activity, StemCode
from models.result import Result
from models.user import Role
from routes.auth import parent_required, teacher_required
from services.activity_service import ActivityService
from services.progress_service import ProgressService
from services.result_service import ResultService
from services.story_service import StoryService

progress_bp = Blueprint('progress', __name__)

progress_service = ProgressService()
result_service = ResultService()
activity_service = ActivityService()
story_service = StoryService()

@progress_bp.route('/parent/progress')
@parent_required
def parent_progress():
    children = current_user.children
    progress_data = {}
    for child in children:
        progress_data[child.id] = progress_service.get_progress_by_child(child.id)

    return render_template('ProgressSystem/parent_progress.html', children=children, progress_data=progress_data)

@progress_bp.route('/parent/results')
@parent_required
def parent_results():
    children = current_user.children
    results_data = {}
    for child in children:
        results_data[child.id] = result_service.get_results_by_child(child.id)

    return render_template('ProgressSystem/parent_results.html', children=children, results_data=results_data)

@progress_bp.route('/teacher/progress')
@teacher_required
def teacher_progress():
    progress_data = progress_service.get_progress_by_teacher(current_user.id)
    return render_template('ProgressSystem/teacher_progress.html', progress_data=progress_data)

@progress_bp.route('/teacher/results')
@teacher_required
def teacher_results():
    results_data = result_service.get_results_by_teacher(current_user.id)
    return render_template('ProgressSystem/teacher_results.html', results_data=results_data)

@progress_bp.route('/api/child_stem_levels/<int:child_id>')
@login_required
def get_child_stem_levels(child_id):
    # role.name is 'PARENT'/'TEACHER' in upper case, so comparing it to
    # 'parent'/'teacher' never matched and the permission check never ran --
    # any signed-in user could read any child's scores. Compare enums instead,
    # and deny by default rather than allowing anything unrecognised.
    if current_user.role == Role.PARENT:
        allowed = child_id in {child.id for child in current_user.children}
    elif current_user.role == Role.TEACHER:
        allowed = child_id in {student.id for student in current_user.students}
    elif current_user.role == Role.ADMIN:
        allowed = True
    elif current_user.role == Role.CHILD:
        allowed = child_id == current_user.id
    else:
        allowed = False

    if not allowed:
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
        if stem_code is not None and avg_score is not None:
            stem_levels[stem_code.name.lower()] = round(avg_score, 2)

    return jsonify(stem_levels)
