from flask import Blueprint, request, url_for, redirect, render_template, jsonify, flash
from services.story_service import StoryService
from services.learning_plan_service import LearningPlanService
from models.child import Level
from flask_login import login_required, current_user
from routes.auth import child_required

story_bp = Blueprint('story', __name__)
story_service = StoryService()
learning_plan_service = LearningPlanService()

@story_bp.route('/stories')
@child_required
def stories():
    learning_plan = learning_plan_service.get_learning_plan_by_child(current_user.id)
    story_level = (learning_plan.story_level if learning_plan else None) \
        or getattr(current_user, 'recommended_level', None) or Level.BEGINNER

    # Stories used to ignore the learning plan entirely; every child saw every
    # story regardless of their reading level.
    visible = []
    for story in story_service.get_stories():
        level = Level.coerce(story.level)
        if level is None or level.rank > story_level.rank:
            continue
        progress = story_service.get_or_create_progress(story.id, current_user.id)
        story.progress_value = progress.completion_rate
        story.is_completed = progress.completed
        visible.append(story)

    visible.sort(key=lambda s: (s.level.rank, s.id))
    return render_template('StorytellingSystem/stories.html', stories=visible)

# Namespaced under /stories so this route does not swallow every top-level
# numeric URL on the site.
@story_bp.route('/stories/<int:story_id>')
@login_required
def story_detail(story_id):
    story = story_service.get_story(story_id)
    if not story:
        flash('Story not found', 'error')
        return redirect(url_for('story.stories'))
    # Progress rows belong to children; adults previewing a story must not
    # create one (progress.child_id is a foreign key into children).
    progress = None
    if getattr(current_user, 'type', None) == 'child':
        progress = story_service.get_or_create_progress(story_id, current_user.id)
    return render_template('StorytellingSystem/story_detail.html', story=story, progress=progress)

@story_bp.route('/stories/<int:story_id>/save_progress', methods=['POST'])
@child_required
def save_progress(story_id):
    try:
        current_page = int(request.form.get('current_page', 0))
    except (TypeError, ValueError):
        current_page = 0

    progress, message = story_service.save_story_progress(story_id, current_user.id, current_page)
    if progress is None:
        return jsonify({'message': message}), 404
    return jsonify({'message': message, 'progress': progress.completion_rate})

@story_bp.route('/stories/<int:story_id>/complete', methods=['POST'])
@child_required
def complete_story(story_id):
    # complete_story marks progress and issues the reward in one transaction and
    # will not hand out a duplicate badge on a re-read.
    reward, message = story_service.complete_story(story_id, current_user.id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if reward is None:
            return jsonify({'success': False, 'message': message}), 404
        return jsonify({'success': True, 'message': message})

    if reward is None:
        flash(message, 'error')
        return redirect(url_for('story.stories'))

    flash('Story completed!', 'success')
    return redirect(url_for('story.stories'))
