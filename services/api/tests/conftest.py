"""Shared fixtures.

Every test module gets one throwaway database seeded with the demo dataset,
plus a second family that shares nothing with the demo teacher -- which is what
makes the authorisation tests meaningful.
"""
import os
import sys
import tempfile

import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "test-only")
# seed_admin reads ADMIN_PASSWORD; without it the admin gets a random password
# and every admin-role test fails at the login step.
os.environ["ADMIN_PASSWORD"] = "pw"
# CI points TEST_DATABASE_URL at a Postgres service container so the suite runs
# against the engine production uses. Without it, a throwaway SQLite file keeps a
# fresh clone runnable with no database server -- but SQLite is forgiving about
# things Postgres is not (type coercion, enum handling, transactional DDL), so a
# green SQLite run is not proof.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or (
    "sqlite:///" + os.path.join(tempfile.mkdtemp(), "kai_test.db").replace("\\", "/"))

from app import create_app  # noqa: E402
from app.api.auth_seam import issue_token  # noqa: E402
from app.config import db  # noqa: E402
from app.models import (  # noqa: E402
    Activity,
    Child,
    EducationLevel,
    LunchType,
    Parent,
    Role,
    Story,
    Teacher,
    User,
)
from app.seeds import seed_all  # noqa: E402


class TokenClient(FlaskClient):
    """A test client that presents a bearer token by default.

    Every /api endpoint except login, registration and the preschool list
    requires one, so attaching it here keeps the contract tests about the
    contract. A test that sets its own Authorization header -- or the anon
    fixture below -- overrides this.
    """

    token = None

    def open(self, *args, **kwargs):
        headers = Headers(kwargs.get("headers") or {})
        if self.token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.token}"
        kwargs["headers"] = headers
        return super().open(*args, **kwargs)


flask_app = create_app({"TESTING": True})
flask_app.test_client_class = TokenClient


@pytest.fixture(scope="session")
def app():
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        seed_all(with_demo=True, password="pw")
        yield flask_app


@pytest.fixture(scope="session")
def ids(app):
    """Stable primary keys, plus an unrelated family for negative tests."""
    with flask_app.app_context():
        teacher = Teacher.query.filter_by(username="teacher").first()
        parent = Parent.query.filter_by(username="parent").first()
        child = Child.query.filter_by(username="child").first()
        child2 = Child.query.filter_by(username="child2").first()

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

        beginner_activity = Activity.query.filter_by(title="Counting to Ten").first()
        advanced_activity = Activity.query.filter_by(title="Number Patterns").first()
        story = Story.query.filter_by(title="Ben the Bear's Big Adventure").first()

        return {
            "teacher": teacher.id,
            "parent": parent.id,
            "child": child.id,
            "child2": child2.id,
            "outsider": outsider.id,
            "other_teacher": other_teacher.id,
            "outsider_child": outsider_child.id,
            "activity": beginner_activity.id,
            "advanced_activity": advanced_activity.id,
            "story": story.id,
            "preschool": child.preschool_id,
        }


@pytest.fixture(scope="session")
def token(app):
    """A valid token for the seeded admin."""
    with flask_app.app_context():
        return issue_token(User.query.filter_by(username="admin").first())


@pytest.fixture()
def client(app, token):
    c = flask_app.test_client()
    c.token = token
    return c


@pytest.fixture()
def anon_client(app):
    """A client that sends no Authorization header, for the 401 cases."""
    return flask_app.test_client()


def login(client, username, password="pw"):
    client.get("/users/logout")
    return client.post("/users/login", data={"username": username, "password": password})
