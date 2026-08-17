"""Builds a complete, working dataset so the app is usable the moment it starts."""
import os
import secrets
from datetime import timedelta

from config import db
from models import (
    Activity,
    Admin,
    Answer,
    Child,
    EducationLevel,
    Feedback,
    LearningPlan,
    Level,
    LunchType,
    Page,
    Parent,
    Preschool,
    Progress,
    Question,
    Result,
    Reward,
    Role,
    StemCode,
    Story,
    Teacher,
)
from utils import utcnow

from .content import ACTIVITIES, STORIES

PRESCHOOL_NAME = 'Kai Konane Preschool'


def _generated_password(label):
    """A strong random password, reported to the operator once."""
    return f"{label}-{secrets.token_urlsafe(9)}"


# --------------------------------------------------------------------- users

def seed_admin(password=None):
    """Create the administrator if it is missing. Returns (admin, password)."""
    username = os.getenv('ADMIN_USERNAME') or 'admin'
    existing = Admin.query.filter_by(username=username).first()
    if existing:
        return existing, None

    password = password or os.getenv('ADMIN_PASSWORD') or _generated_password('admin')
    admin = Admin(
        username=username,
        email=os.getenv('ADMIN_EMAIL') or 'admin@kaikonane.local',
        name='Site Administrator',
        role=Role.ADMIN,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin, password


def _get_or_create_preschool(name=PRESCHOOL_NAME):
    preschool = Preschool.query.filter_by(name=name).first()
    if preschool is None:
        preschool = Preschool(name=name)
        db.session.add(preschool)
        db.session.flush()
    return preschool


def seed_demo_users(password=None):
    """Create a preschool, a teacher, a parent and two children.

    Wired together exactly as the app expects: the children belong to the
    parent, are taught by the teacher, attend the preschool, and each has a
    learning plan.
    """
    password = password or os.getenv('DEMO_PASSWORD') or _generated_password('demo')
    created = []

    preschool = _get_or_create_preschool()

    teacher = Teacher.query.filter_by(username='teacher').first()
    if teacher is None:
        teacher = Teacher(
            username='teacher',
            email='teacher@kaikonane.local',
            role=Role.TEACHER,
            firstname='Tina',
            lastname='Kahu',
            preschool_id=preschool.id,
        )
        teacher.set_password(password)
        db.session.add(teacher)
        db.session.flush()
        created.append(('teacher', teacher.username))

    parent = Parent.query.filter_by(username='parent').first()
    if parent is None:
        parent = Parent(
            username='parent',
            email='parent@kaikonane.local',
            role=Role.PARENT,
            firstname='Pania',
            lastname='Rewi',
            education_level=EducationLevel.BACHELORS_DEGREE,
        )
        parent.set_password(password)
        db.session.add(parent)
        db.session.flush()
        created.append(('parent', parent.username))

    children_spec = [
        {'username': 'child', 'firstname': 'Ari', 'age': 5, 'gender': 'Female',
         'race_ethnicity': 'group B', 'lunch_type': LunchType.STANDARD,
         'level': Level.BEGINNER},
        {'username': 'child2', 'firstname': 'Nikau', 'age': 6, 'gender': 'Male',
         'race_ethnicity': 'group C', 'lunch_type': LunchType.FREE_REDUCED,
         'level': Level.INTERMEDIATE},
    ]

    children = []
    for spec in children_spec:
        child = Child.query.filter_by(username=spec['username']).first()
        if child is None:
            child = Child(
                username=spec['username'],
                email=f"{spec['username']}@kaikonane.local",
                role=Role.CHILD,
                firstname=spec['firstname'],
                lastname=parent.lastname,
                age=spec['age'],
                gender=spec['gender'],
                parent_id=parent.id,
                teacher_id=teacher.id,
                preschool_id=preschool.id,
                race_ethnicity=spec['race_ethnicity'],
                lunch_type=spec['lunch_type'],
                parent_education=parent.education_level,
                recommended_level=spec['level'],
            )
            child.set_password(password)
            db.session.add(child)
            db.session.flush()
            created.append(('child', child.username))

        if child.learning_plan is None:
            level = child.recommended_level or Level.BEGINNER
            db.session.add(LearningPlan(
                child_id=child.id,
                science_level=level,
                technology_level=level,
                engineering_level=level,
                math_level=level,
                story_level=level,
            ))
        children.append(child)

    db.session.commit()
    return {
        'preschool': preschool,
        'teacher': teacher,
        'parent': parent,
        'children': children,
        'password': password,
        'created': created,
    }


# ------------------------------------------------------------------- content

def seed_content():
    """Insert the starter activities and stories, skipping any already present."""
    added_activities = 0
    added_stories = 0

    for spec in ACTIVITIES:
        if Activity.query.filter_by(title=spec['title']).first():
            continue

        activity = Activity(
            title=spec['title'],
            description=spec.get('description'),
            stem_code=StemCode[spec['stem_code']],
            level=Level[spec['level']],
            cover_image=spec.get('cover_image'),
        )
        for position, question_spec in enumerate(spec['questions'], start=1):
            question = Question(content=question_spec['content'], position=position)
            for answer_position, (text, correct) in enumerate(question_spec['answers'], start=1):
                question.answers.append(Answer(content=text, is_correct=correct,
                                               position=answer_position))
            activity.questions.append(question)

        db.session.add(activity)
        added_activities += 1

    for spec in STORIES:
        if Story.query.filter_by(title=spec['title']).first():
            continue

        story = Story(
            title=spec['title'],
            description=spec.get('description'),
            level=Level[spec['level']],
            cover_page=spec.get('cover_page'),
        )
        for number, (line, image) in enumerate(spec['pages'], start=1):
            story.pages.append(Page(line_of_page=line, image_filename=image,
                                    page_number=number))

        db.session.add(story)
        added_stories += 1

    db.session.commit()
    return added_activities, added_stories


# ----------------------------------------------------------------- demo state

def seed_demo_activity(demo):
    """Give the demo child some history so the dashboards are not empty.

    Progress, a result, a reward and a message between the teacher and the
    parent -- enough that every screen has something real to show.
    """
    children = demo['children']
    if not children:
        return

    child = children[0]

    activity = Activity.query.filter_by(title='Counting to Ten').first()
    if activity is not None:
        existing = Result.query.filter_by(child_id=child.id, activity_id=activity.id).first()
        if existing is None:
            db.session.add(Result(child_id=child.id, activity_id=activity.id, score=100.0,
                                  date_acquired=utcnow() - timedelta(days=2)))
            db.session.add(Reward(child_id=child.id, activity_id=activity.id,
                                  content='Gold Star'))
        progress = Progress.query.filter_by(child_id=child.id,
                                            learning_content_id=activity.id).first()
        if progress is None:
            progress = Progress(learning_content_id=activity.id, child_id=child.id,
                                total_num_questions=len(activity.questions))
            progress.mark_as_completed()
            db.session.add(progress)

    story = Story.query.filter_by(title="Ben the Bear's Big Adventure").first()
    if story is not None:
        progress = Progress.query.filter_by(child_id=child.id,
                                            learning_content_id=story.id).first()
        if progress is None:
            progress = Progress(learning_content_id=story.id, child_id=child.id,
                                total_num_questions=len(story.pages),
                                completion_rate=40.0)
            db.session.add(progress)

    teacher, parent = demo['teacher'], demo['parent']
    if not Feedback.query.filter_by(sender_id=teacher.id, recipient_id=parent.id).first():
        db.session.add(Feedback(
            subject=f"{child.firstname}'s first week",
            message=(f"{child.firstname} finished Counting to Ten with full marks "
                     f"and has started reading Ben the Bear's Big Adventure. "
                     f"A lovely start to the term."),
            sender_id=teacher.id,
            recipient_id=parent.id,
            child_id=child.id,
        ))
    if not Feedback.query.filter_by(sender_id=parent.id, recipient_id=teacher.id).first():
        db.session.add(Feedback(
            subject='Thank you',
            message=(f"Thanks for the update. {child.firstname} has been counting "
                     f"everything in the house all week."),
            sender_id=parent.id,
            recipient_id=teacher.id,
            child_id=child.id,
        ))

    db.session.commit()


def seed_all(with_demo=True, password=None):
    """Seed everything and return a summary for the CLI to print."""
    admin, admin_password = seed_admin()
    activities, stories = seed_content()

    demo = None
    if with_demo:
        demo = seed_demo_users(password)
        seed_demo_activity(demo)

    return {
        'admin': admin,
        'admin_password': admin_password,
        'activities_added': activities,
        'stories_added': stories,
        'demo': demo,
    }
