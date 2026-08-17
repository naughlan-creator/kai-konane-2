"""Every page renders for the role that owns it, and not for anyone else.

This is the broad safety net: it will not tell you a calculation is wrong, but
it catches template/route contract breaks across the whole app in one run.
"""
import pytest
from conftest import login

# (path, allowed roles). Paths are formatted with the ids fixture.
PAGES = [
    ("/", {"child", "parent", "teacher", "admin", None}),
    ("/healthz", {"child", "parent", "teacher", "admin", None}),
    ("/users/login", {None}),
    ("/users/signup", {"child", "parent", "teacher", "admin", None}),
    ("/users/parent_signup_1", {"child", "parent", "teacher", "admin", None}),
    ("/users/teacher_signup_1", {"child", "parent", "teacher", "admin", None}),

    ("/users/child_home", {"child"}),
    ("/learning-content", {"child"}),
    ("/activities", {"child"}),
    ("/stories", {"child"}),
    ("/stories/{story}", {"child", "parent", "teacher", "admin"}),
    ("/start/{activity}", {"child"}),
    ("/activity/{activity}", {"child", "parent", "teacher", "admin"}),

    ("/users/parent_home", {"parent"}),
    ("/users/view_children", {"parent"}),
    ("/parent/progress", {"parent"}),
    ("/parent/results", {"parent"}),

    ("/users/teacher_home", {"teacher"}),
    ("/users/view_learners", {"teacher"}),
    ("/teacher/progress", {"teacher"}),
    ("/teacher/results", {"teacher"}),
    ("/learning_plans/manage", {"teacher"}),
    ("/learning_plan/create/{child}", {"teacher"}),
    ("/learning_plan/update/{child}", {"teacher"}),
    ("/learning_plan/view/{child}", {"teacher", "parent"}),

    ("/feedbacks/feedback", {"parent", "teacher"}),
    ("/feedbacks/feedback/write", {"parent", "teacher"}),
    ("/feedbacks/feedback/view", {"parent", "teacher"}),
    ("/feedbacks/feedback/past", {"parent", "teacher"}),

    ("/profile", {"child", "parent", "teacher", "admin"}),

    ("/users/admin_home", {"admin"}),
    ("/admin/home", {"admin"}),
    ("/admin/view_content", {"admin"}),
    ("/admin/add_content", {"admin"}),
    ("/admin/add_activity", {"admin"}),
    ("/admin/add_story", {"admin"}),
    ("/admin/modify_content", {"admin"}),
    ("/admin/update_activity/{activity}", {"admin"}),
    ("/admin/update_story/{story}", {"admin"}),
    ("/admin/view_user_data", {"admin"}),
    ("/admin/edit_user/{child}", {"admin"}),
    ("/preschools/admin/preschools", {"admin"}),
    ("/preschools/admin/preschool/{preschool}", {"admin"}),
    ("/preschools/admin/preschool/add", {"admin"}),
    ("/users/get", {"admin"}),
]

ROLES = ["child", "parent", "teacher", "admin", None]


@pytest.mark.parametrize("path,allowed", PAGES)
@pytest.mark.parametrize("role", ROLES)
def test_page_access(client, ids, path, allowed, role):
    url = path.format(**ids)
    if role:
        login(client, role)
    else:
        client.get("/users/logout")

    response = client.get(url)
    assert response.status_code < 500, (
        f"{role or 'anonymous'} GET {url} -> {response.status_code}\n"
        f"{response.get_data(as_text=True)[:400]}")

    if role in allowed:
        assert response.status_code == 200, (
            f"{role or 'anonymous'} should see {url}, got {response.status_code}")
    else:
        assert response.status_code in (302, 403), (
            f"{role or 'anonymous'} should NOT see {url}, got {response.status_code}")
