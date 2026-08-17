"""Feedback system: correspondent scoping, learner ownership, read/history split.

First file of the api test suite (issue #8).
    venv/Scripts/python.exe -m pytest tests/test_feedback.py -v
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "test-only")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(), "feedback_test.db").replace("\\", "/")

from conftest import flask_app  # noqa: E402
from app.config import db  # noqa: E402
from app.models import Child, EducationLevel, Feedback, LunchType, Parent, Role, Teacher  # noqa: E402
from app.seeds import seed_all  # noqa: E402


@pytest.fixture(scope="module")
def ids():
    """Demo family, plus a second family that shares nothing with them."""
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        demo = seed_all(with_demo=True, password="pw")["demo"]

        outsider = Parent(username="outsider", email="o@x.local", role=Role.PARENT,
                          firstname="Olive", lastname="Ndlovu",
                          education_level=EducationLevel.HIGH_SCHOOL)
        outsider.set_password("pw")
        other_teacher = Teacher(username="otherteach", email="ot@x.local",
                                role=Role.TEACHER, firstname="Otto", lastname="Kruger")
        other_teacher.set_password("pw")
        db.session.add_all([outsider, other_teacher])
        db.session.flush()

        outsider_child = Child(username="olivekid", email="ok@x.local", role=Role.CHILD,
                               firstname="Ola", lastname="Ndlovu", age=5, gender="Female",
                               parent_id=outsider.id, teacher_id=other_teacher.id,
                               lunch_type=LunchType.STANDARD,
                               parent_education=EducationLevel.HIGH_SCHOOL)
        outsider_child.set_password("pw")
        db.session.add(outsider_child)
        db.session.commit()

        yield {
            "teacher": demo["teacher"].id,
            "parent": demo["parent"].id,
            "child": demo["children"][0].id,
            "outsider": outsider.id,
            "outsider_child": outsider_child.id,
        }

@pytest.fixture()
def client():
    return flask_app.test_client()


def login(client, username):
    client.get("/users/logout")
    client.post("/users/login", data={"username": username, "password": "pw"})


def sent(subject):
    with flask_app.app_context():
        return Feedback.query.filter_by(subject=subject).count()


def test_picker_renders_names_and_a_usable_link(ids, client):
    """Jinja renders missing attributes as '', so a shape mismatch is silent."""
    login(client, "teacher")
    body = client.get("/feedbacks/feedback/write").get_data(as_text=True)
    assert "Pania" in body                                # the parent's name
    assert "Ari" in body                                  # a shared learner
    assert f"recipient_id={ids['parent']}" in body        # Select actually works


def test_teacher_can_message_their_own_parent(ids, client):
    login(client, "teacher")
    r = client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["parent"]), "subject": "Week one",
        "content": "Settling in well.", "child_id": str(ids["child"])})
    assert r.status_code == 302
    assert sent("Week one") == 1


def test_teacher_cannot_message_an_unrelated_parent(ids, client):
    login(client, "teacher")
    client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["outsider"]), "subject": "Not allowed", "content": "x"})
    assert sent("Not allowed") == 0


def test_cannot_attach_a_learner_you_do_not_share(ids, client):
    login(client, "teacher")
    client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["parent"]), "subject": "Wrong learner",
        "content": "x", "child_id": str(ids["outsider_child"])})
    assert sent("Wrong learner") == 0


def test_non_numeric_child_id_does_not_500(ids, client):
    login(client, "teacher")
    r = client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["parent"]), "subject": "Bad id",
        "content": "x", "child_id": "abc"})
    assert r.status_code < 500


def test_reading_moves_a_message_from_inbox_to_history(ids, client):
    login(client, "teacher")
    client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["parent"]), "subject": "Reading test",
        "content": "x", "child_id": str(ids["child"])})
    with flask_app.app_context():
        msg_id = Feedback.query.filter_by(subject="Reading test").first().id

    login(client, "parent")
    assert "Reading test" in client.get("/feedbacks/feedback/view").get_data(as_text=True)
    client.get(f"/feedbacks/feedback/read/{msg_id}")
    assert "Reading test" not in client.get("/feedbacks/feedback/view").get_data(as_text=True)
    assert "Reading test" in client.get("/feedbacks/feedback/past").get_data(as_text=True)


def test_a_child_cannot_send_feedback(ids, client):
    login(client, "child")
    r = client.post("/feedbacks/feedback/submit", data={
        "recipient_id": str(ids["parent"]), "subject": "From a child", "content": "x"})
    assert r.status_code == 302
    assert sent("From a child") == 0