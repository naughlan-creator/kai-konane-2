"""Stories.

Level filtering and progress attachment happen in the api: `GET /stories` with
a `child_id` returns only what that child may read, each item already carrying
their progress. Doing it here would mean one request per card.
"""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import api_client
from app.routes.auth import child_required

story_bp = Blueprint('story', __name__)


@story_bp.route('/stories')
@child_required
def stories():
    try:
        visible = api_client.get('stories',
                                 params={'child_id': current_user.id})['stories']
    except api_client.ApiNotFound:
        flash("No learning plan found. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('user.home'))

    # The template reads story.progress_value and story.is_completed; the api
    # sends a nested progress object instead.
    for story in visible:
        progress = story.get('progress') or {}
        story['progress_value'] = progress.get('completion_rate', 0)
        story['is_completed'] = progress.get('completed', False)

    return render_template('StorytellingSystem/stories.html', stories=visible)


# Namespaced under /stories so this route does not swallow every top-level
# numeric URL on the site.
@story_bp.route('/stories/<int:story_id>')
@login_required
def story_detail(story_id):
    try:
        story = api_client.get(f'stories/{story_id}')['story']
    except api_client.ApiNotFound:
        flash('Story not found', 'error')
        return redirect(url_for('story.stories'))

    # Progress rows belong to children; an adult previewing a story must not
    # create one, because progress.child_id is a foreign key into children.
    progress = None
    if getattr(current_user, 'type', None) == 'child':
        listed = api_client.get('stories',
                                params={'child_id': current_user.id})['stories']
        progress = next((s.get('progress') for s in listed
                         if s['id'] == story_id), None)

    return render_template('StorytellingSystem/story_detail.html',
                           story=story, progress=progress)


@story_bp.route('/stories/<int:story_id>/save_progress', methods=['POST'])
@child_required
def save_progress(story_id):
    try:
        current_page = int(request.form.get('current_page', 0))
    except (TypeError, ValueError):
        current_page = 0

    try:
        result = api_client.post(f'stories/{story_id}/progress',
                                 json={'child_id': current_user.id,
                                       'current_page': current_page})
    except api_client.ApiError as e:
        return jsonify({'message': e.message}), 404

    return jsonify({'message': result['message'],
                    'progress': result['completion_rate']})


@story_bp.route('/stories/<int:story_id>/complete', methods=['POST'])
@child_required
def complete_story(story_id):
    # The api marks progress and issues the badge in one transaction and will
    # not hand out a duplicate on a re-read.
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        result = api_client.post(f'stories/{story_id}/complete',
                                 json={'child_id': current_user.id})
    except api_client.ApiError as e:
        if is_ajax:
            return jsonify({'success': False, 'message': e.message}), 404
        flash(e.message, 'error')
        return redirect(url_for('story.stories'))

    if is_ajax:
        return jsonify({'success': True, 'message': result['message']})

    flash('Story completed!', 'success')
    return redirect(url_for('story.stories'))
