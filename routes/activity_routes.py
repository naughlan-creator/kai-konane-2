from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from services.activity_service import ActivityService
from services.learning_plan_service import LearningPlanService
from services.reward_service import RewardService
from models.learning_plan import Level
from services.child_service import ChildService
import json
from flask import current_app
import traceback
from level_predictor import update_child_level

activity_bp = Blueprint('activity', __name__)
activity_service = ActivityService()
reward_service = RewardService()
child_service = ChildService()
learning_plan_service = LearningPlanService()

@activity_bp.route('/activities')
@login_required
def activity_home():
    learning_plan = learning_plan_service.get_learning_plan_by_child(current_user.id)
    child = child_service.get_child(current_user.id)

    if not learning_plan:
        flash("No learning plan found. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))

    if not child or not child.recommended_level:
        flash("Unable to determine your recommended level. Please contact your teacher.", "warning")
        return redirect(url_for('user.home'))

    activities = activity_service.get_activities()
    completed_activities = activity_service.get_completed_activities(current_user.id)
    
    filtered_activities = []
    level_order = list(Level)
    recommended_level_index = level_order.index(child.recommended_level)

    for activity in activities:
        try:
            activity_level = activity.level if isinstance(activity.level, Level) else Level[activity.level.upper()]
            activity_level_index = level_order.index(activity_level)
            
            # Only include activities at or below the recommended level
            if activity_level_index <= recommended_level_index:
                activity.is_completed = any(ca.learning_content_id == activity.id for ca in completed_activities)
                activity.progress_value = activity_service.get_activity_progress(activity.id, current_user.id)
                filtered_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"Error processing activity {activity.id}: {str(e)}")

    # Sort activities by level, then by stem_code
    filtered_activities.sort(key=lambda x: (level_order.index(x.level), x.stem_code.value))

    return render_template('ActivitySystem/activity_home.html', 
                           activities=filtered_activities, 
                           learning_plan=learning_plan,
                           recommended_level=child.recommended_level)

@activity_bp.route('/add_activity', methods=['POST'])
@login_required
def add_activity():
    title = request.form.get('title')
    stem_code = request.form.get('stem_code')
    level = request.form.get('level')
    cover_image = request.files.get('cover_image')
    questions_data = json.loads(request.form.get('questions_data'))
    
    result = activity_service.add_activity(title, stem_code, level, cover_image, questions_data)

@activity_bp.route('/activity/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))
    return render_template('ActivitySystem/activity_detail.html', activity=activity)

@activity_bp.route('/activity/<int:activity_id>/save_progress', methods=['POST'])
@login_required
def save_progress(activity_id):
    answers = request.form.to_dict()
    progress, message = activity_service.save_activity_progress(activity_id, current_user.id, answers)
    return jsonify({'message': message, 'progress': progress.completion_rate})

@activity_bp.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
def submit_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    answers = request.form
    
    correct_answers = 0
    total_questions = len(activity.questions)
    
    for question in activity.questions:
        user_answer_id = answers.get(f'question_{question.id}')
        if user_answer_id:
            user_answer = next((a for a in question.answers if str(a.id) == user_answer_id), None)
            if user_answer and user_answer.is_correct:
                correct_answers += 1
    
    score = (correct_answers / total_questions) * 100
    activity_service.update_result(activity_id, current_user.id, score)
    activity_service.update_progress(activity_id, current_user.id, score)
    
    # Add reward
    reward_content = f"Completed activity: {activity.title}"
    activity_service.add_reward(activity_id, current_user.id, reward_content)
    
    completed_activities = activity_service.get_completed_activities(current_user.id)
    if len(completed_activities) > 0:
        try:
            success, recommended_level = update_child_level(current_user.id)
            if success:
                learning_plan_service.update_learning_plan_from_recommendation(current_user.id, recommended_level)
                flash(f'Your learning level has been updated to {recommended_level.name}!', 'info')
            else:
                current_app.logger.error(f"Failed to update learning level for user {current_user.id}")
                flash('We couldn\'t update your learning level at this time. We\'ll try again later.', 'warning')
        except Exception as e:
            current_app.logger.error(f"Error updating learning level for user {current_user.id}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            flash('An error occurred while updating your learning level. We\'ll try again later.', 'error')

    return redirect(url_for('activity.activity_home'))

@activity_bp.route('/start/<int:activity_id>', methods=['GET'])
@login_required
def start_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found', 'error')
        return redirect(url_for('activity.activity_home'))
    
    progress = activity_service.get_activity_progress(activity_id, current_user.id)
    
    # Prepare questions and answers data
    questions_data = []
    for question in activity.questions:
        question_data = {
            'id': question.id,
            'content': question.content,
            'answers': [
                {
                    'id': answer.id,
                    'content': answer.content,
                    'is_correct': answer.is_correct
                } for answer in question.answers
            ]
        }
        questions_data.append(question_data)
    
    return render_template('ActivitySystem/activity_page.html', 
                           activity=activity, 
                           progress=progress, 
                           questions_data=jsonify(questions_data).get_data(as_text=True))