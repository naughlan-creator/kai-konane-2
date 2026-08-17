from app.config import db as default_db
from app.models.activity import Activity, StemCode
from app.models.answer import Answer
from app.models.child import Level
from app.models.progress import Progress
from app.models.question import Question
from app.models.result import Result
from app.services.errors import NotFound, ValidationError
from app.services.learning_plan_service import LearningPlanService
from app.services.media import resolve_image


class ActivityService:
    def __init__(self, db=None):
        self.db = db or default_db
        self.learning_plan_service = LearningPlanService(self.db)

    # ---------------------------------------------------------------- authoring

    @staticmethod
    def _validate(title, stem_code, level, questions_data):
        """Check an activity before touching the database.

        Validating up front means a bad submission never leaves a half-written
        activity behind.
        """
        if not (title or '').strip():
            raise ValidationError("An activity needs a title")

        code = StemCode.coerce(stem_code)
        if code is None:
            raise ValidationError("Choose a valid STEM subject")

        activity_level = Level.coerce(level)
        if activity_level is None:
            raise ValidationError("Choose a valid level")

        cleaned = []
        for index, question_data in enumerate(questions_data or [], start=1):
            content = (question_data.get('content') or '').strip()
            if not content:
                raise ValidationError(f"Question {index} is missing its text")

            answers = []
            for answer_data in question_data.get('answers') or []:
                answer_content = (answer_data.get('content') or '').strip()
                if not answer_content:
                    continue
                answers.append({
                    'id': answer_data.get('id'),
                    'content': answer_content,
                    'is_correct': bool(answer_data.get('is_correct')),
                })

            if len(answers) < 2:
                raise ValidationError(f"Question {index} needs at least two answers")
            correct = [a for a in answers if a['is_correct']]
            if len(correct) != 1:
                raise ValidationError(
                    f"Question {index} needs exactly one answer marked correct")

            cleaned.append({
                'id': question_data.get('id'),
                'content': content,
                'answers': answers,
            })

        if not cleaned:
            raise ValidationError("An activity needs at least one question")

        return code, activity_level, cleaned

    def add_activity(self, title, stem_code, level, cover_image, questions_data,
                     description=None, existing_cover=None):
        """Create an activity. Raises ValidationError; returns the Activity."""
        code, activity_level, questions = self._validate(
            title, stem_code, level, questions_data)

        try:
            activity = Activity(
                title=title.strip(),
                description=(description or '').strip() or None,
                stem_code=code,
                level=activity_level,
                cover_image=resolve_image(cover_image, existing_cover),
            )

            for position, question_data in enumerate(questions, start=1):
                question = Question(content=question_data['content'], position=position)
                for answer_position, answer_data in enumerate(question_data['answers'], start=1):
                    question.answers.append(Answer(
                        content=answer_data['content'],
                        is_correct=answer_data['is_correct'],
                        position=answer_position,
                    ))
                activity.questions.append(question)

            self.db.session.add(activity)
            self.db.session.commit()
            return activity
        except Exception:
            self.db.session.rollback()
            raise

    def update_activity(self, activity_id, title=None, stem_code=None, level=None,
                        cover_image=None, questions_data=None, description=None,
                        existing_cover=None):
        activity = self.get_activity(activity_id)
        if activity is None:
            raise NotFound("That activity no longer exists")

        code, activity_level, questions = self._validate(
            title or activity.title,
            stem_code or activity.stem_code,
            level or activity.level,
            questions_data)

        try:
            activity.title = (title or activity.title).strip()
            if description is not None:
                activity.description = description.strip() or None
            activity.stem_code = code
            activity.level = activity_level
            activity.cover_image = resolve_image(cover_image, existing_cover,
                                                 activity.cover_image)

            self._sync_questions(activity, questions)

            self.db.session.commit()
            return activity
        except Exception:
            self.db.session.rollback()
            raise

    def _sync_questions(self, activity, questions):
        """Make the stored questions match the submitted ones exactly.

        Rows the author kept are updated in place (so results stay meaningful),
        rows they added are created, and rows they removed are deleted. The old
        version could only ever append, so each save duplicated the question set.
        """
        existing = {question.id: question for question in activity.questions}
        keep = set()

        for position, question_data in enumerate(questions, start=1):
            question = existing.get(_as_int(question_data.get('id')))
            if question is None:
                question = Question(content=question_data['content'], position=position)
                activity.questions.append(question)
            else:
                question.content = question_data['content']
                question.position = position
                keep.add(question.id)

            self._sync_answers(question, question_data['answers'])

        for question in list(activity.questions):
            if question.id is not None and question.id not in keep:
                activity.questions.remove(question)

    @staticmethod
    def _sync_answers(question, answers):
        existing = {answer.id: answer for answer in question.answers}
        keep = set()

        for position, answer_data in enumerate(answers, start=1):
            answer = existing.get(_as_int(answer_data.get('id')))
            if answer is None:
                question.answers.append(Answer(
                    content=answer_data['content'],
                    is_correct=answer_data['is_correct'],
                    position=position,
                ))
            else:
                answer.content = answer_data['content']
                answer.is_correct = answer_data['is_correct']
                answer.position = position
                keep.add(answer.id)

        for answer in list(question.answers):
            if answer.id is not None and answer.id not in keep:
                question.answers.remove(answer)

    def delete_activity(self, activity_id):
        activity = self.get_activity(activity_id)
        if activity is None:
            raise NotFound("That activity no longer exists")

        # Progress, results and rewards all cascade from the model definitions
        # now, so there is nothing to clear by hand.
        self.db.session.delete(activity)
        self.db.session.commit()
        return activity

    # ------------------------------------------------------------------ reading

    def get_activity(self, activity_id):
        return self.db.session.get(Activity, activity_id)

    def get_activities(self):
        return Activity.query.order_by(Activity.id).all()


    def get_activity_progress(self, activity_id, child_id):
        progress = Progress.query.filter_by(child_id=child_id,
                                            learning_content_id=activity_id).first()
        return progress.completion_rate if progress else 0

    def get_or_create_progress(self, activity_id, child_id):
        progress = Progress.query.filter_by(learning_content_id=activity_id,
                                            child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=activity_id, child_id=child_id)
            self.db.session.add(progress)
            self.db.session.commit()
        return progress


    def save_activity_progress(self, activity_id, child_id, answers):
        """Record how far through an activity a child is (not their score)."""
        activity = self.get_activity(activity_id)
        if not activity:
            return None, "Activity not found"

        total_questions = len(activity.questions)
        progress = self.get_or_create_progress(activity_id, child_id)
        progress.total_num_questions = total_questions

        if total_questions:
            answered = sum(1 for question in activity.questions
                           if str(question.id) in answers)
            progress.completion_rate = (answered / total_questions) * 100
        else:
            progress.completion_rate = 0

        self.db.session.commit()
        return progress, "Progress saved successfully"

    def submit_activity(self, activity_id, child_id, answers):
        """Mark an activity, log the attempt and nudge the learning plan."""
        activity = self.get_activity(activity_id)
        if not activity:
            return None, "Activity not found"

        total_questions = len(activity.questions)
        if total_questions == 0:
            return None, "This activity has no questions yet"

        correct_answers = 0
        for question in activity.questions:
            selected = answers.get(str(question.id))
            if selected is None:
                continue
            correct = question.correct_answer
            if correct and str(correct.id) == str(selected):
                correct_answers += 1

        score = int((correct_answers / total_questions) * 100)

        result = Result(child_id=child_id, activity_id=activity_id, score=score)
        self.db.session.add(result)

        progress = self.get_or_create_progress(activity_id, child_id)
        progress.total_num_questions = total_questions
        progress.mark_as_completed()

        self.db.session.commit()

        self.learning_plan_service.update_learning_plan_from_activity(
            child_id, activity.stem_code, score)

        return result, f"Activity submitted successfully. Your score: {score}%"

    def get_completed_activities(self, child_id):
        return Progress.query.filter_by(child_id=child_id, completed=True).all()

    def get_activities_for_strand(self, stem_code, level):
        """Activities in one STEM strand at or below a level.

        Filtering by rank rather than equality: a child at INTERMEDIATE should
        still be able to revisit BEGINNER work.
        """
        allowed = [candidate for candidate in Level if candidate.rank <= level.rank]
        return (Activity.query
                .filter(Activity.stem_code == stem_code, Activity.level.in_(allowed))
                .order_by(Activity.level, Activity.id)
                .all())

    def get_progress_for_child(self, child_id):
        """Every progress row for one child, for bulk attachment to a listing.

        The api attaches progress to each card from this single result; looking
        it up per card would be an N+1 across the whole page.
        """
        return Progress.query.filter_by(child_id=child_id).all()



def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
