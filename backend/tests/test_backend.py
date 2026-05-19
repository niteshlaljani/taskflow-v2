"""TaskFlow backend regression tests.

Covers: auth (register/login/me/logout/session), workspaces, projects,
tasks CRUD, comments, and auth-gating.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://flow-dev-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@taskflow.com"
DEMO_PASSWORD = "demo1234"
PROJECT_ID = "proj_coreplatform"
SEED_TASK_WITH_COMMENT = "task_seed_0254"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Health ----------------
def test_health():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------------- Auth ----------------
class TestAuth:
    def test_login_demo_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == DEMO_EMAIL
        assert "access_token" in data
        assert s.cookies.get("access_token"), "access_token cookie not set"

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_new_user_and_me(self):
        s = requests.Session()
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "secret123", "name": "Test User"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == email
        assert "access_token" in data
        assert s.cookies.get("access_token")
        # me via cookie
        rm = s.get(f"{API}/auth/me")
        assert rm.status_code == 200
        assert rm.json()["email"] == email

    def test_register_duplicate_fails(self):
        r = requests.post(f"{API}/auth/register", json={"email": DEMO_EMAIL, "password": "secret123", "name": "x"})
        assert r.status_code == 400

    def test_me_unauthenticated_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_bearer_header(self, demo_session):
        token = demo_session.cookies.get("access_token")
        assert token
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert s.cookies.get("access_token")
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # after logout, cookie should be gone; /me should 401
        rm = s.get(f"{API}/auth/me")
        assert rm.status_code == 401

    def test_session_invalid_session_id_returns_4xx(self):
        # External Emergent service will reject; we should get 401 (NOT 500/404)
        r = requests.post(f"{API}/auth/session", json={"session_id": "definitely-invalid-xyz"})
        assert r.status_code in (400, 401), f"expected 4xx, got {r.status_code}: {r.text}"


# ---------------- Auth gating ----------------
class TestAuthGating:
    def test_projects_requires_auth(self):
        r = requests.get(f"{API}/projects")
        assert r.status_code == 401

    def test_workspace_requires_auth(self):
        r = requests.get(f"{API}/workspaces/current")
        assert r.status_code == 401


# ---------------- Workspaces / Projects / Members ----------------
class TestWorkspace:
    def test_current_workspace_is_linearsync(self, demo_session):
        r = demo_session.get(f"{API}/workspaces/current")
        assert r.status_code == 200
        ws = r.json()
        assert ws["name"] == "LinearSync"
        assert ws["workspace_id"] == "ws_linearsync001"

    def test_list_projects_contains_core(self, demo_session):
        r = demo_session.get(f"{API}/projects")
        assert r.status_code == 200
        projects = r.json()
        assert isinstance(projects, list) and len(projects) >= 1
        core = next((p for p in projects if p["project_id"] == PROJECT_ID), None)
        assert core is not None
        assert core["key"] == "CORE"
        assert core["name"] == "Core Platform"

    def test_get_project_core(self, demo_session):
        r = demo_session.get(f"{API}/projects/{PROJECT_ID}")
        assert r.status_code == 200
        assert r.json()["key"] == "CORE"

    def test_members_includes_demo_and_teammates(self, demo_session):
        r = demo_session.get(f"{API}/workspaces/members")
        assert r.status_code == 200
        members = r.json()
        names = {m["name"] for m in members}
        # demo + 3 teammates
        assert "Demo User" in names
        assert "Sarah J." in names
        assert "David Chen" in names
        assert "Priya K." in names


# ---------------- Tasks ----------------
class TestTasks:
    def test_list_seeded_tasks_25_across_statuses(self, demo_session):
        r = demo_session.get(f"{API}/projects/{PROJECT_ID}/tasks")
        assert r.status_code == 200
        tasks = r.json()
        # at least 25 seeded; could have more from previous create tests
        seeded = [t for t in tasks if t["task_id"].startswith("task_seed_")]
        assert len(seeded) == 25, f"expected 25 seeded tasks, got {len(seeded)}"
        by_status = {}
        for t in seeded:
            by_status.setdefault(t["status"], 0)
            by_status[t["status"]] += 1
        for s in ("backlog", "todo", "in_progress", "done"):
            assert by_status.get(s, 0) > 0, f"missing tasks for status {s}"

    def test_create_update_delete_task(self, demo_session):
        # Create
        payload = {"title": "TEST_temp task", "description": "tmp", "status": "todo", "priority": "low"}
        rc = demo_session.post(f"{API}/projects/{PROJECT_ID}/tasks", json=payload)
        assert rc.status_code == 200, rc.text
        t = rc.json()
        assert t["title"] == "TEST_temp task"
        assert t["key"].startswith("CORE-")
        # number should be >= 257 (seed used 254..256; next_task_number starts at 257)
        assert t["number"] >= 257
        task_id = t["task_id"]

        # GET verify persistence
        rg = demo_session.get(f"{API}/tasks/{task_id}")
        assert rg.status_code == 200
        assert rg.json()["title"] == "TEST_temp task"

        # PATCH update
        ru = demo_session.patch(f"{API}/tasks/{task_id}", json={
            "title": "TEST_updated",
            "status": "in_progress",
            "priority": "high",
            "assignee_id": "user_sarahj000001",
            "tag": "BUG",
            "description": "updated desc",
        })
        assert ru.status_code == 200, ru.text
        upd = ru.json()
        assert upd["title"] == "TEST_updated"
        assert upd["status"] == "in_progress"
        assert upd["priority"] == "high"
        assert upd["assignee_id"] == "user_sarahj000001"

        # Verify persistence
        rg2 = demo_session.get(f"{API}/tasks/{task_id}")
        assert rg2.json()["status"] == "in_progress"

        # DELETE
        rd = demo_session.delete(f"{API}/tasks/{task_id}")
        assert rd.status_code == 200
        rg3 = demo_session.get(f"{API}/tasks/{task_id}")
        assert rg3.status_code == 404


# ---------------- Comments ----------------
class TestComments:
    def test_seeded_comment_on_core_254(self, demo_session):
        r = demo_session.get(f"{API}/tasks/{SEED_TASK_WITH_COMMENT}/comments")
        assert r.status_code == 200
        comments = r.json()
        assert len(comments) >= 1
        sarahs = [c for c in comments if c["author_id"] == "user_sarahj000001"]
        assert len(sarahs) >= 1
        assert "security validation" in sarahs[0]["body"].lower()

    def test_add_new_comment(self, demo_session):
        body = f"TEST_comment {uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/tasks/{SEED_TASK_WITH_COMMENT}/comments", json={"body": body})
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["body"] == body
        # Verify it appears in list
        rl = demo_session.get(f"{API}/tasks/{SEED_TASK_WITH_COMMENT}/comments")
        bodies = [x["body"] for x in rl.json()]
        assert body in bodies
