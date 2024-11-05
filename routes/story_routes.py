from flask import Blueprint, request, url_for, redirect, render_template, jsonify, flash
from services.story_service import StoryService
from models.progress import Progress
from models.learning_content import LCTYPE
from flask_login import login_required, current_user

story_bp = Blueprint('story', __name__)
story_service = StoryService()

@story_bp.route('/stories')
@login_required
def stories():
    stories = story_service.get_stories()
    for story in stories:
        progress = story_service.get_or_create_progress(story.id, current_user.id)
        story.progress_value = progress.completion_rate
        story.is_completed = progress.completion_rate == 100
    return render_template('StorytellingSystem/stories.html', stories=stories)

@story_bp.route('/<int:story_id>')
@login_required
def story_detail(story_id):
    story = story_service.get_story(story_id)
    if not story:
        flash('Story not found', 'error')
        return redirect(url_for('story.stories'))
    progress = story_service.get_or_create_progress(story_id, current_user.id)
    return render_template('StorytellingSystem/story_detail.html', story=story, progress=progress)

@story_bp.route('/<int:story_id>/save_progress', methods=['POST'])
@login_required
def save_progress(story_id):
    current_page = int(request.form.get('current_page', 0))
    progress, message = story_service.save_story_progress(story_id, current_user.id, current_page)
    return jsonify({'message': message, 'progress': progress.completion_rate})

@story_bp.route('/<int:story_id>/complete', methods=['POST'])
@login_required
def complete_story(story_id):
    story = story_service.get_story(story_id)
    story_service.update_progress(story_id, current_user.id, 100)
    
    # Add reward
    reward_content = f"Completed story: {story.title}"
    story_service.add_reward(story_id, current_user.id, reward_content)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Story completed!', 'success')
    return redirect(url_for('story.stories'))