from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
from services.activity_service import ActivityService
from services.story_service import StoryService
from models.user import User, Role
from models.progress import Progress
from models.learning_content import LCTYPE
from config import db

admin_bp = Blueprint('admin', __name__)

activity_service = ActivityService()
story_service = StoryService()

@admin_bp.route('/admin/home')
@login_required
def admin_home():
    return render_template('UserManagement/admin_home.html')

@admin_bp.route('/admin/view_content')
@login_required
def view_content():
    activities = activity_service.get_activities()
    stories = story_service.get_stories()
    
    # Combine activities and stories into a single list of learning content
    learning_content = []
    
    for activity in activities:
        learning_content.append({
            'name': activity.title,
            'content_type': LCTYPE.ACTIVITY.value,
            'stem_code': activity.stem_code.value,
        })
    
    for story in stories:
        learning_content.append({
            'name': story.title,
            'content_type': LCTYPE.STORY.value,
            'stem_code': '',  # Assuming stories don't have STEM codes
     })
    
    return render_template('ContentManagement/view_learning_content.html', learning_content=learning_content)

@admin_bp.route('/admin/add_content')
@login_required
def add_content():
    return render_template('ContentManagement/add_content.html')

@admin_bp.route('/admin/add_activity', methods=['GET', 'POST'])
@login_required
def add_activity():
    if request.method == 'POST':
        title = request.form['activity_title']
        stem_code = request.form['stem_code']
        level = request.form['level']  # Add this line
        cover_image = request.files['cover_image']
        
        questions_data = []
        for i in range(1, 100):  # Assuming a maximum of 100 questions
            question_key = f'question_{i}'
            if question_key not in request.form:
                break
            question_content = request.form[question_key]
            answers = []
            for j in range(1, 3):  # Assuming a maximum of 2 answers per question
                answer_key = f'answer_{i}_{j}'
                correct_key = f'correct_{i}_{j}'
                if answer_key not in request.form:
                    break
                answers.append({
                    'content': request.form[answer_key],
                    'is_correct': correct_key in request.form
                })
            questions_data.append({
                'content': question_content,
                'answers': answers
            })
        
        result = activity_service.add_activity(title, stem_code, level, cover_image, questions_data)
        flash(result)
        return redirect(url_for('admin.view_content'))
    
    return render_template('ContentManagement/add_activity.html')

@admin_bp.route('/admin/add_story', methods=['GET', 'POST'])
@login_required
def add_story():
    if request.method == 'POST':
        title = request.form['story_title']
        level = request.form['level']
        cover_image = request.files['cover_image']
        
        pages = []
        for i in range(1, 100):  # Assuming a maximum of 100 pages
            page_content_key = f'page_content_{i}'
            page_image_key = f'page_image_{i}'
            is_last_page_key = f'is_last_page_{i}'
            
            if page_content_key not in request.form:
                break
            
            page_data = {
                'line_of_page': request.form[page_content_key],
                'image': request.files[page_image_key],
                'is_last_page': is_last_page_key in request.form
            }
            pages.append(page_data)
        
        new_story = story_service.add_story(title, level, cover_image, pages)
        if new_story:
            flash('Story added successfully!', 'success')
        else:
            flash('Failed to add story.', 'error')
        return redirect(url_for('admin.view_content'))
    
    return render_template('ContentManagement/add_story.html')


@admin_bp.route('/admin/modify_content')
@login_required
def modify_content():
    activities = activity_service.get_activities()
    stories = story_service.get_stories()
    
    learning_content = []
    
    for activity in activities:
        learning_content.append({
            'id': activity.id,
            'name': activity.title,
            'content_type': LCTYPE.ACTIVITY.value,
            'stem_code': activity.stem_code.value,
            'update_url': url_for('admin.update_activity', activity_id=activity.id),
            'delete_url': url_for('admin.delete_activity', activity_id=activity.id)
        })
    
    for story in stories:
        learning_content.append({
            'id': story.id,
            'name': story.title,
            'content_type': LCTYPE.STORY.value,
            'stem_code': '',  # Assuming stories don't have STEM codes
            'update_url': url_for('admin.update_story', story_id=story.id),
            'delete_url': url_for('admin.delete_story', story_id=story.id)
        })
    
    return render_template('ContentManagement/modify_content.html', learning_content=learning_content)

@admin_bp.route('/admin/update_activity/<int:activity_id>', methods=['GET', 'POST'])
@login_required
def update_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found.', 'error')
        return redirect(url_for('admin.view_activities'))  # Assuming you have a view_activities route

    if request.method == 'POST':
        title = request.form['activity_title']
        stem_code = request.form['stem_code']
        level = request.form['level']
        cover_image = request.files['cover_image'] if 'cover_image' in request.files else None

        questions_data = []
        for i in range(1, 100):  # Assuming a maximum of 100 questions
            question_key = f'question_{i}'
            if question_key not in request.form:
                break
            question_content = request.form[question_key]
            answers = []
            for j in range(1, 3):  # Assuming a maximum of 2 answers per question
                answer_key = f'answer_{i}_{j}'
                correct_key = f'correct_{i}_{j}'
                if answer_key not in request.form:
                    break
                answers.append({
                    'content': request.form[answer_key],
                    'is_correct': correct_key in request.form
                })
            questions_data.append({
                'content': question_content,
                'answers': answers
            })

        result = activity_service.update_activity(
            activity_id, title, stem_code, level, cover_image, questions_data
        )
        flash(result, 'success')
        return redirect(url_for('admin.view_content'))  # Redirect to the activity list

    return render_template('ContentManagement/update_activity.html', activity=activity)

@admin_bp.route('/admin/update_story/<int:story_id>', methods=['GET', 'POST'])
@login_required
def update_story(story_id):
    story = story_service.get_story(story_id)
    if not story:
        flash('Story not found.', 'error')
        return redirect(url_for('admin.view_content'))
    
    if request.method == 'POST':
        title = request.form['story_title']
        level = request.form['level']
        cover_image = request.files['cover_image'] if 'cover_image' in request.files else None
        
        pages = []
        for i in range(1, 100):  # Assuming a maximum of 100 pages
            page_content_key = f'page_content_{i}'
            page_image_key = f'page_image_{i}'
            is_last_page_key = f'is_last_page_{i}'
            
            if page_content_key not in request.form:
                break
            
            page_data = {
                'line_of_page': request.form[page_content_key],
                'image': request.files[page_image_key] if page_image_key in request.files else None,
                'is_last_page': is_last_page_key in request.form
            }
            pages.append(page_data)
        
        story_service.update_story(story_id, title, level, cover_image, pages)
        flash('Story updated successfully!', 'success')
        return redirect(url_for('admin.view_content'))
    
    return render_template('ContentManagement/update_story.html', story=story)

@admin_bp.route('/admin/delete_activity/<int:activity_id>')
@login_required
def delete_activity(activity_id):
    result = activity_service.delete_activity(activity_id)
    flash(result)
    return redirect(url_for('admin.modify_content'))

@admin_bp.route('/admin/delete_story/<int:story_id>')
@login_required
def delete_story(story_id):
    result = story_service.delete_story(story_id)
    flash(result)
    return redirect(url_for('admin.modify_content'))

@admin_bp.route('/admin/view_user_data')
@login_required
def view_user_data():
    users = User.query.all()
    return render_template('UserManagement/view_user_data.html', users=users)

@admin_bp.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.role = Role(request.form['role'])
        
        if request.form['password']:
            user.password = generate_password_hash(request.form['password'])
        
        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin.view_user_data'))
    
    return render_template('UserManagement/edit_user.html', user=user, roles=Role)

@admin_bp.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != Role.ADMIN:
        flash('Unauthorized access', 'error')
        return redirect(url_for('admin.view_user_data'))
    
    user = User.query.get_or_404(user_id)
    if user.role == Role.ADMIN:
        flash('Cannot delete admin users', 'error')
        return redirect(url_for('admin.view_user_data'))
    
    # If user is a Child, delete related Progress records first
    if user.type == 'child':
        Progress.query.filter_by(child_id=user.id).delete()
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.view_user_data'))


