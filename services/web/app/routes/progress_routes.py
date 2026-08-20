"""Progress and results.

The teacher views ask the api for one flat list per teacher; the parent views
ask per child, because the templates group by child and a parent has few.

`/api/child_stem_levels/<id>` is deliberately absent: it moved to the api as
`GET /api/children/{id}/stem-levels`, ownership check included. The gateway
sends every /api/* path to the api service, so a copy here would never run.
"""
from flask import Blueprint, render_template
from flask_login import current_user

from app import api_client
from app.routes.auth import parent_required, teacher_required

progress_bp = Blueprint('progress', __name__)


def _children_of_current_parent():
    return api_client.get('children',
                          params={'parent_id': current_user.id})['children']


@progress_bp.route('/parent/progress')
@parent_required
def parent_progress():
    children = _children_of_current_parent()
    progress_data = {
        child['id']: api_client.get(f"children/{child['id']}/progress")['progress']
        for child in children
    }
    return render_template('ProgressSystem/parent_progress.html',
                           children=children, progress_data=progress_data)


@progress_bp.route('/parent/results')
@parent_required
def parent_results():
    children = _children_of_current_parent()
    results_data = {
        child['id']: api_client.get(f"children/{child['id']}/results")['results']
        for child in children
    }
    return render_template('ProgressSystem/parent_results.html',
                           children=children, results_data=results_data)


@progress_bp.route('/teacher/progress')
@teacher_required
def teacher_progress():
    progress_data = api_client.get('progress',
                                   params={'teacher_id': current_user.id})['progress']
    return render_template('ProgressSystem/teacher_progress.html',
                           progress_data=progress_data)


@progress_bp.route('/teacher/results')
@teacher_required
def teacher_results():
    results_data = api_client.get('results',
                                  params={'teacher_id': current_user.id})['results']
    return render_template('ProgressSystem/teacher_results.html',
                           results_data=results_data)
