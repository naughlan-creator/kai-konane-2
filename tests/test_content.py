"""Authoring activities and stories through the admin forms.

These exercise the paths that changed when services stopped returning strings:
a failure must surface a message AND leave nothing behind.
"""
from conftest import login

from app import app as flask_app
from models import Activity, Page, Question, Story


def question_fields(n=1, correct=1):
    """One question with two answers, in the form's flat field naming."""
    return {
        f"question_id_{n}": "",
        f"question_{n}": f"Question {n}?",
        f"answer_id_{n}_1": "", f"answer_{n}_1": "Yes",
        f"answer_id_{n}_2": "", f"answer_{n}_2": "No",
        f"correct_{n}": str(correct),
    }


def test_admin_creates_an_activity(client, ids):
    login(client, "admin")
    data = {"activity_title": "Test Colours", "stem_code": "SCIENCE",
            "level": "BEGINNER", "description": "Made by a test"}
    data.update(question_fields())

    response = client.post("/admin/add_activity", data=data)
    assert response.status_code == 302

    with flask_app.app_context():
        activity = Activity.query.filter_by(title="Test Colours").first()
        assert activity is not None
        assert activity.stem_code.name == "SCIENCE"
        assert len(activity.questions) == 1
        assert activity.questions[0].correct_answer.content == "Yes"


def test_activity_without_a_correct_answer_is_rejected_and_not_saved(client, ids):
    login(client, "admin")
    data = {"activity_title": "No Correct Answer", "stem_code": "MATH",
            "level": "BEGINNER"}
    data.update(question_fields())
    data.pop("correct_1")            # nothing marked correct

    response = client.post("/admin/add_activity", data=data)
    assert b"exactly one answer marked correct" in response.get_data()

    with flask_app.app_context():
        assert Activity.query.filter_by(title="No Correct Answer").count() == 0


def test_activity_with_a_bad_stem_code_is_rejected(client, ids):
    login(client, "admin")
    data = {"activity_title": "Bad Strand", "stem_code": "NONSENSE",
            "level": "BEGINNER"}
    data.update(question_fields())

    response = client.post("/admin/add_activity", data=data)
    assert b"valid STEM subject" in response.get_data()
    with flask_app.app_context():
        assert Activity.query.filter_by(title="Bad Strand").count() == 0


def test_editing_an_activity_does_not_duplicate_its_questions(client, ids):
    login(client, "admin")
    with flask_app.app_context():
        activity = Activity.query.filter_by(title="Test Colours").first()
        activity_id = activity.id
        question = activity.questions[0]
        question_id, answer_ids = question.id, [a.id for a in question.answers]

    data = {
        "activity_title": "Test Colours v2", "stem_code": "SCIENCE", "level": "BEGINNER",
        "question_id_1": str(question_id), "question_1": "Question 1?",
        "answer_id_1_1": str(answer_ids[0]), "answer_1_1": "Yes",
        "answer_id_1_2": str(answer_ids[1]), "answer_1_2": "No",
        "correct_1": "2",
    }
    assert client.post(f"/admin/update_activity/{activity_id}", data=data).status_code == 302

    with flask_app.app_context():
        activity = flask_app.extensions["sqlalchemy"].session.get(Activity, activity_id)
        assert activity.title == "Test Colours v2"
        assert len(activity.questions) == 1, "editing duplicated the question set"
        assert activity.questions[0].correct_answer.content == "No"


def test_deleting_an_activity_cascades(client, ids):
    login(client, "admin")
    with flask_app.app_context():
        activity_id = Activity.query.filter_by(title="Test Colours v2").first().id

    assert client.post(f"/admin/delete_activity/{activity_id}").status_code == 302

    with flask_app.app_context():
        assert flask_app.extensions["sqlalchemy"].session.get(Activity, activity_id) is None
        assert Question.query.filter_by(activity_id=activity_id).count() == 0


def test_admin_creates_a_story_with_ordered_pages(client, ids):
    login(client, "admin")
    response = client.post("/admin/add_story", data={
        "story_title": "Test Story", "level": "BEGINNER",
        "page_id_1": "", "page_content_1": "Once upon a time.",
        "page_existing_1": "BB_page_1.png",
        "page_id_2": "", "page_content_2": "The end.",
        "page_existing_2": "BB_page_2.png",
    })
    assert response.status_code == 302

    with flask_app.app_context():
        story = Story.query.filter_by(title="Test Story").first()
        assert story is not None
        assert [p.page_number for p in story.pages] == [1, 2]
        assert story.pages[0].image_filename == "BB_page_1.png"
        assert story.pages[-1].is_last_page


def test_story_without_pages_is_rejected(client, ids):
    login(client, "admin")
    response = client.post("/admin/add_story", data={
        "story_title": "Empty Story", "level": "BEGINNER"})
    assert b"at least one page" in response.get_data()
    with flask_app.app_context():
        assert Story.query.filter_by(title="Empty Story").count() == 0


def test_reordering_story_pages_renumbers_them(client, ids):
    login(client, "admin")
    with flask_app.app_context():
        story = Story.query.filter_by(title="Test Story").first()
        story_id = story.id
        page_ids = [p.id for p in story.pages]

    client.post(f"/admin/update_story/{story_id}", data={
        "story_title": "Test Story", "level": "BEGINNER",
        "page_id_1": str(page_ids[1]), "page_content_1": "The end.",
        "page_id_2": str(page_ids[0]), "page_content_2": "Once upon a time.",
    })

    with flask_app.app_context():
        story = flask_app.extensions["sqlalchemy"].session.get(Story, story_id)
        assert [p.line_of_page for p in story.pages] == ["The end.", "Once upon a time."]


def test_deleting_a_story_cascades(client, ids):
    login(client, "admin")
    with flask_app.app_context():
        story_id = Story.query.filter_by(title="Test Story").first().id

    assert client.post(f"/admin/delete_story/{story_id}").status_code == 302
    with flask_app.app_context():
        assert flask_app.extensions["sqlalchemy"].session.get(Story, story_id) is None
        assert Page.query.filter_by(story_id=story_id).count() == 0
