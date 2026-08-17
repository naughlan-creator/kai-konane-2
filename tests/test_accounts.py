"""Profiles, preschools and the learner journey.

Covers the service methods that now raise instead of returning a sentence, so a
regression shows up as a missing flash rather than a silent no-op.
"""
from conftest import login

from app import app as flask_app
from models import Child, Parent, Preschool, Progress, Result, User


def db_session():
    return flask_app.extensions["sqlalchemy"].session


# --------------------------------------------------------------- profiles

def test_parent_updates_their_own_profile(client, ids):
    login(client, "parent")
    response = client.post("/update_profile", data={
        "username": "parent", "email": "parent@kaikonane.local",
        "firstname": "Pania", "lastname": "Rewi-Smith",
        "education_level": "MASTERS_DEGREE"}, follow_redirects=True)
    assert b"Profile updated" in response.get_data()

    with flask_app.app_context():
        parent = Parent.query.filter_by(username="parent").first()
        assert parent.lastname == "Rewi-Smith"
        assert parent.education_level.name == "MASTERS_DEGREE"
        # The child snapshot must move with it or predictions drift.
        assert all(c.parent_education.name == "MASTERS_DEGREE" for c in parent.children)


def test_taking_someone_elses_username_is_rejected(client, ids):
    login(client, "parent")
    response = client.post("/update_profile", data={
        "username": "teacher", "email": "parent@kaikonane.local",
        "firstname": "Pania", "lastname": "Rewi-Smith",
        "education_level": "MASTERS_DEGREE"}, follow_redirects=True)
    assert b"already taken" in response.get_data()

    with flask_app.app_context():
        assert User.query.filter_by(username="parent").count() == 1


def test_parent_cannot_edit_another_familys_child(client, ids):
    login(client, "parent")
    response = client.post(f"/update_child_profile/{ids['outsider_child']}", data={
        "firstname": "Hacked", "lastname": "X", "age": "5",
        "gender": "Female", "lunch_type": "STANDARD"}, follow_redirects=True)
    assert b"only update your own" in response.get_data()

    with flask_app.app_context():
        assert db_session().get(Child, ids["outsider_child"]).firstname == "Ola"


def test_non_numeric_age_is_rejected(client, ids):
    login(client, "parent")
    response = client.post(f"/update_child_profile/{ids['child']}", data={
        "firstname": "Ari", "lastname": "Rewi", "age": "five",
        "gender": "Female", "lunch_type": "STANDARD"}, follow_redirects=True)
    assert b"whole number" in response.get_data()


# ------------------------------------------------------------- preschools

def test_admin_adds_a_preschool(client, ids):
    login(client, "admin")
    response = client.post("/preschools/admin/preschool/add",
                           data={"name": "Rivendell Preschool"}, follow_redirects=True)
    assert b"Rivendell Preschool" in response.get_data()
    with flask_app.app_context():
        assert Preschool.query.filter_by(name="Rivendell Preschool").count() == 1


def test_duplicate_preschool_name_is_rejected(client, ids):
    login(client, "admin")
    response = client.post("/preschools/admin/preschool/add",
                           data={"name": "Rivendell Preschool"}, follow_redirects=True)
    assert b"already exists" in response.get_data()
    with flask_app.app_context():
        assert Preschool.query.filter_by(name="Rivendell Preschool").count() == 1


def test_blank_preschool_name_is_rejected(client, ids):
    login(client, "admin")
    response = client.post("/preschools/admin/preschool/add",
                           data={"name": "   "}, follow_redirects=True)
    assert b"enter a preschool name" in response.get_data()


def test_occupied_preschool_cannot_be_deleted(client, ids):
    login(client, "admin")
    response = client.post(
        f"/preschools/admin/preschool/delete/{ids['preschool']}", follow_redirects=True)
    assert b"Move the teachers and learners out" in response.get_data()
    with flask_app.app_context():
        assert db_session().get(Preschool, ids["preschool"]) is not None


def test_empty_preschool_can_be_deleted(client, ids):
    login(client, "admin")
    with flask_app.app_context():
        target = Preschool.query.filter_by(name="Rivendell Preschool").first().id

    client.post(f"/preschools/admin/preschool/delete/{target}", follow_redirects=True)
    with flask_app.app_context():
        assert db_session().get(Preschool, target) is None


# -------------------------------------------------------- learner journey

def test_child_submitting_an_activity_records_a_result_and_progress(client, ids):
    with flask_app.app_context():
        from models import Activity
        activity = db_session().get(Activity, ids["activity"])
        answers = {f"question_{q.id}": str(q.correct_answer.id) for q in activity.questions}
        before = Result.query.filter_by(child_id=ids["child"],
                                        activity_id=ids["activity"]).count()

    login(client, "child")
    assert client.post(f"/activity/{ids['activity']}/submit",
                       data=answers).status_code == 302

    with flask_app.app_context():
        after = Result.query.filter_by(child_id=ids["child"],
                                       activity_id=ids["activity"]).count()
        assert after == before + 1, "results are an append-only attempt log"
        latest = (Result.query.filter_by(child_id=ids["child"], activity_id=ids["activity"])
                  .order_by(Result.date_acquired.desc()).first())
        assert latest.score == 100

        progress = Progress.query.filter_by(child_id=ids["child"],
                                            learning_content_id=ids["activity"]).first()
        assert progress.completed is True


def test_completing_a_story_is_idempotent(client, ids):
    from models import Reward
    login(client, "child")
    client.post(f"/stories/{ids['story']}/complete")
    client.post(f"/stories/{ids['story']}/complete")

    with flask_app.app_context():
        assert Reward.query.filter_by(child_id=ids["child"],
                                      story_id=ids["story"]).count() == 1


def test_child_only_sees_content_at_or_below_their_level(client, ids):
    login(client, "child")
    body = client.get("/activities").get_data(as_text=True)
    assert "Counting to Ten" in body                 # BEGINNER
    assert "Number Patterns" not in body             # ADVANCED
