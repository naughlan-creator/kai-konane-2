import os
from werkzeug.utils import secure_filename
from models.activity import Activity, StemCode, Level
from services.learning_plan_service import LearningPlanService
from models.question import Question
from models.answer import Answer
from models.result import Result
from models.reward import Reward
from models.progress import Progress
from config import db

class ActivityService:
    def __init__(self):
        self.db = db
        self.UPLOAD_FOLDER = os.path.join('static', 'images')
        self.learning_plan_service = LearningPlanService()

    def add_activity(self, title, stem_code, level, cover_image, questions_data):
        try:
            cover_filename = self._save_image(cover_image)
            activity = Activity(
                title=title,
                stem_code=stem_code,
                level=level,
                cover_image=cover_filename
            )

            for question_data in questions_data:
                question_content = question_data.get('content')
                answer_data = question_data.get('answers')

                question = Question(content=question_content)

                for answer_data in answer_data:
                    answer_content = answer_data.get('content')
                    is_correct = answer_data.get('is_correct')
                    answer = Answer(content=answer_content, is_correct=is_correct)
                    question.answers.append(answer)

                activity.questions.append(question)

            self.db.session.add(activity)
            self.db.session.commit()
            return "Activity added!!!"
        
        except Exception as e:
            self.db.session.rollback()
            return f"Activity not added!!! Error: {str(e)}"

    def get_activity(self, activity_id):
        activity = Activity.query.filter_by(id=activity_id).first()
        if activity:
            return activity
        return None

    def get_activities(self):
        return Activity.query.all()

    def update_activity(self, activity_id, title=None, stem_code=None, level=None, cover_image=None, questions_data=None):
        activity = self.get_activity(activity_id)
        if not activity:
            return f"Activity not found!!!"
        
        if title:
            activity.title = title
        if stem_code:
            activity.stem_code = StemCode[stem_code.upper()]
        if level:
            activity.level = Level[level.upper()]
        if cover_image:
            activity.cover_image = self._save_image(cover_image)

        if questions_data:
            for question_data in questions_data:
                question_id = question_data.get('id')
                question = Question.query.filter_by(id=question_id).first()
                
                if question:
                    question.content = question_data.get('content')
                    answers_data = question_data.get('answers')

                    for answer_data in answers_data:
                        answer_id = answer_data.get('id')
                        answer = Answer.query.filter_by(id=answer_id).first()
                        if answer:
                            answer.content = answer_data.get('content')
                            answer.is_correct = answer_data.get('is_correct')
                        else:
                            new_answer = Answer(content=answer_data.get('content'), is_correct=answer_data.get('is_correct'))
                            question.answers.append(new_answer)
                else:
                    new_question = Question(content=question_data.get('content'))
                    answers_data = question_data.get('answers')

                    for answer_data in answers_data:
                        new_answer = Answer(content=answer_data.get('content'), is_correct=answer_data.get('is_correct'))
                        new_question.answers.append(new_answer)
                    activity.questions.append(new_question)

        self.db.session.commit()
        return "Activity updated!!!"
    
    def _save_image(self, image):
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(self.UPLOAD_FOLDER, filename))
            return filename
        return None

    def delete_activity(self, activity_id):
        activity = self.get_activity(activity_id)
        if not activity:
            return f"Activity not found!!!"

        self.db.session.delete(activity)
        self.db.session.commit()
        return "Activity deleted!!!"
    
    def get_activity_progress(self, activity_id, child_id):
        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=activity_id).first()
        if progress:
            return progress.completion_rate
        return 0  # Return 0 if no progress is found

    def save_activity_progress(self, activity_id, child_id, answers):
        activity = self.get_activity(activity_id)
        if not activity:
            return None, "Activity not found"

        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=activity_id).first()
        if not progress:
            progress = Progress(child_id=child_id, learning_content_id=activity_id, total_num_questions=len(activity.questions))
            self.db.session.add(progress)

        answered_questions = len(answers)
        progress.completion_rate = (answered_questions / len(activity.questions)) * 100

        self.db.session.commit()

        return progress, "Progress saved successfully"

    def submit_activity(self, activity_id, child_id, answers):
        activity = Activity.query.get(activity_id)
        if not activity:
            return None, "Activity not found"

        total_questions = len(activity.questions)
        correct_answers = 0

        for question in activity.questions:
            if str(question.id) in answers:
                selected_answer_id = int(answers[str(question.id)])
                correct_answer = next((a for a in question.answers if a.is_correct), None)
                if correct_answer and correct_answer.id == selected_answer_id:
                    correct_answers += 1

        score = int((correct_answers / total_questions) * 100)

        result, message = Result(child_id=child_id, activity_id=activity_id, score=score)
        db.session.add(result)

        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=activity_id).first()
        if not progress:
            progress = Progress(child_id=child_id, learning_content_id=activity_id, total_num_questions=total_questions)
            db.session.add(progress)

        progress.completion_rate = score
        progress.completed = True

        db.session.commit()

        self.learning_plan_service.update_learning_plan_from_activity(child_id, activity.stem_code, score)

        return result, message, f"Activity submitted successfully. Your score: {score}%"
    
    def get_or_create_progress(self, activity_id, child_id):
        progress = Progress.query.filter_by(learning_content_id=activity_id, child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=activity_id, child_id=child_id)
            db.session.add(progress)
            db.session.commit()
        return progress
    
    def update_progress(self, activity_id, child_id, completion_rate):
        progress = Progress.query.filter_by(learning_content_id=activity_id, child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=activity_id, child_id=child_id, completion_rate=completion_rate)
            db.session.add(progress)
        else:
            progress.completion_rate = completion_rate
        db.session.commit()

    def get_or_create_result(self, activity_id, child_id):
        result = Result.query.filter_by(activity_id=activity_id, child_id=child_id).first()
        if not result:
            result = Result(activity_id=activity_id, child_id=child_id)
            db.session.add(result)
            db.session.commit()
        return result

    def update_result(self, activity_id, child_id, score):
        result = Result.query.filter_by(activity_id=activity_id, child_id=child_id).first()
        if not result:
            result = Result(activity_id=activity_id, child_id=child_id, score=score)
            db.session.add(result)
        else:
            result.score = score
        db.session.commit()

    def add_reward(self, activity_id, child_id, content):
        reward = Reward(
            activity_id=activity_id,
            child_id=child_id,
            content=content
        )
        db.session.add(reward)
        db.session.commit()

    def get_completed_activities(self, user_id):
        return Progress.query.filter_by(child_id=user_id, completion_rate=100).all()
