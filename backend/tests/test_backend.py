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


# ============================================================================
# Sprint 3: My Issues, Project create/delete, Invites, WebSocket
# ============================================================================
import asyncio
import json as _json
import uuid as _uuid


# ---------------- My Issues ----------------
class TestMyIssues:
    def test_my_issues_returns_demo_assigned_tasks(self, demo_session):
        r = demo_session.get(f"{API}/my-issues")
        assert r.status_code == 200, r.text
        tasks = r.json()
        assert isinstance(tasks, list)
        keys = {t["key"] for t in tasks}
        # Spec says CORE-234,237,242,245,247,252 are seeded for demo
        expected = {"CORE-234", "CORE-237", "CORE-242", "CORE-245", "CORE-247", "CORE-252"}
        missing = expected - keys
        assert not missing, f"missing assigned tasks for demo: {missing}; got keys: {sorted(keys)}"
        # All returned tasks should be assigned to demo user
        for t in tasks:
            assert t.get("assignee_id"), f"task {t['key']} has no assignee"

    def test_my_issues_requires_auth(self):
        r = requests.get(f"{API}/my-issues")
        assert r.status_code == 401


# ---------------- Project create/delete ----------------
class TestProjectsCRUD:
    def test_create_and_delete_project(self, demo_session):
        key = f"T{_uuid.uuid4().hex[:4].upper()}"
        payload = {"name": "TEST_proj_mobile", "key": key, "description": "test"}
        rc = demo_session.post(f"{API}/projects", json=payload)
        assert rc.status_code == 200, rc.text
        p = rc.json()
        assert p["name"] == "TEST_proj_mobile"
        assert p["key"] == key
        pid = p["project_id"]
        # Verify visible in list
        rl = demo_session.get(f"{API}/projects")
        assert any(x["project_id"] == pid for x in rl.json())
        # Delete
        rd = demo_session.delete(f"{API}/projects/{pid}")
        assert rd.status_code == 200
        # Verify gone
        rg = demo_session.get(f"{API}/projects/{pid}")
        assert rg.status_code == 404

    def test_delete_project_non_owner_403(self, demo_session):
        # Register a brand-new user (their own workspace, not LinearSync owner)
        s = requests.Session()
        email = f"test_{_uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "secret123", "name": "NonOwner"})
        assert r.status_code == 200
        # Try to delete demo's project (CORE) — they aren't a member, should 404
        rd = s.delete(f"{API}/projects/{PROJECT_ID}")
        assert rd.status_code in (403, 404), f"expected 403/404, got {rd.status_code}"

    def test_delete_project_removes_tasks(self, demo_session):
        key = f"D{_uuid.uuid4().hex[:4].upper()}"
        rc = demo_session.post(f"{API}/projects", json={"name": "TEST_del", "key": key})
        pid = rc.json()["project_id"]
        # Create a task in it
        rt = demo_session.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_t", "status": "todo"})
        assert rt.status_code == 200
        tid = rt.json()["task_id"]
        # Delete project
        demo_session.delete(f"{API}/projects/{pid}")
        rg = demo_session.get(f"{API}/tasks/{tid}")
        assert rg.status_code == 404


# ---------------- Invites ----------------
class TestInvites:
    def test_owner_create_list_revoke_invite(self, demo_session):
        rc = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 7})
        assert rc.status_code == 200, rc.text
        inv = rc.json()
        assert "code" in inv and len(inv["code"]) > 0
        assert "expires_at" in inv
        assert "invite_id" in inv
        code = inv["code"]
        inv_id = inv["invite_id"]
        # List
        rl = demo_session.get(f"{API}/workspaces/invites")
        assert rl.status_code == 200
        assert any(x["invite_id"] == inv_id for x in rl.json())
        # Public get
        rg = requests.get(f"{API}/invites/{code}")
        assert rg.status_code == 200
        body = rg.json()
        assert body["workspace_name"] == "LinearSync"
        assert body["expired"] is False
        # Revoke
        rd = demo_session.delete(f"{API}/workspaces/invites/{inv_id}")
        assert rd.status_code == 200

    def test_invite_create_non_owner_403(self):
        # New user is owner of their own ws; but for LinearSync invite endpoint
        # is per get_user_workspace -> their own. So instead test that a NEW user
        # is owner of their own ws, hence will pass. To check 403, we need a user
        # who is a member of LinearSync but NOT owner. Use invite-accept flow first.
        # Step A: owner creates invite
        owner_s = requests.Session()
        owner_s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        rc = owner_s.post(f"{API}/workspaces/invites", json={"expires_in_days": 7})
        code = rc.json()["code"]
        # Step B: new user accepts
        s = requests.Session()
        email = f"test_{_uuid.uuid4().hex[:8]}@example.com"
        s.post(f"{API}/auth/register", json={"email": email, "password": "secret123", "name": "Joiner"})
        ra = s.post(f"{API}/invites/{code}/accept")
        assert ra.status_code == 200, ra.text
        # Step C: Joiner now is member (not owner) of LinearSync; try to create invite
        rc2 = s.post(f"{API}/workspaces/invites", json={"expires_in_days": 7})
        assert rc2.status_code == 403, f"expected 403 for non-owner, got {rc2.status_code}: {rc2.text}"
        # And revoke as non-owner also 403
        # (use a prev invite id from owner)
        rl = owner_s.get(f"{API}/workspaces/invites")
        if rl.json():
            some_id = rl.json()[0]["invite_id"]
            rd = s.delete(f"{API}/workspaces/invites/{some_id}")
            assert rd.status_code == 403

    def test_accept_invite_idempotent_and_membership_persists(self, demo_session):
        # Owner creates
        rc = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 7})
        code = rc.json()["code"]
        # New user
        s = requests.Session()
        email = f"test_{_uuid.uuid4().hex[:8]}@example.com"
        s.post(f"{API}/auth/register", json={"email": email, "password": "secret123", "name": "Joiner2"})
        ra = s.post(f"{API}/invites/{code}/accept")
        assert ra.status_code == 200
        assert ra.json()["already_member"] is False
        # Second accept is idempotent
        ra2 = s.post(f"{API}/invites/{code}/accept")
        assert ra2.status_code == 200
        assert ra2.json()["already_member"] is True
        # User can now see LinearSync projects
        rp = s.get(f"{API}/projects")
        assert rp.status_code == 200
        proj_ids = [p["project_id"] for p in rp.json()]
        assert PROJECT_ID in proj_ids, f"joined user should see Core Platform; got {proj_ids}"
        # And appears in members list
        rm = s.get(f"{API}/workspaces/members")
        assert rm.status_code == 200
        emails = {m["email"] for m in rm.json()}
        assert email in emails

    def test_get_invite_invalid_code_404(self):
        r = requests.get(f"{API}/invites/nonexistent_xyz")
        assert r.status_code == 404


# ---------------- WebSocket (board real-time + presence) ----------------
class TestWebSocket:
    def test_ws_unauth_closes_4401(self):
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets not installed")
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_url}/api/ws/board/{PROJECT_ID}"

        async def _run():
            try:
                async with websockets.connect(url, open_timeout=10) as ws:
                    await ws.recv()
                return None
            except websockets.exceptions.InvalidStatus as e:
                return e.response.status_code
            except websockets.exceptions.ConnectionClosed as e:
                return e.code
            except Exception as e:
                return str(e)

        code = asyncio.run(_run())
        # Server closes with 4401 (custom WS close code) — but the upgrade may also return 403.
        assert code in (4401, 403, 1006), f"expected close 4401/403, got {code}"

    def test_ws_authenticated_presence_and_task_broadcast(self):
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets not installed")

        # Step 1: Login to obtain JWT token
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200
        token = r.json()["access_token"]
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_url}/api/ws/board/{PROJECT_ID}?token={token}"

        async def _run():
            received = []
            async with websockets.connect(url, open_timeout=15) as ws:
                # First message should be presence
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    received.append(_json.loads(msg))
                except asyncio.TimeoutError:
                    return received, None

                # Create a task via HTTP — should broadcast over WS
                rc = s.post(
                    f"{API}/projects/{PROJECT_ID}/tasks",
                    json={"title": "TEST_ws_broadcast", "status": "todo"},
                )
                task_id = rc.json().get("task_id") if rc.status_code == 200 else None

                # Wait for broadcast
                try:
                    msg2 = await asyncio.wait_for(ws.recv(), timeout=5)
                    received.append(_json.loads(msg2))
                except asyncio.TimeoutError:
                    pass
                return received, task_id

        msgs, task_id = asyncio.run(_run())
        # cleanup
        if task_id:
            s.delete(f"{API}/tasks/{task_id}")

        assert len(msgs) >= 1, f"expected at least 1 WS message; got {msgs}"
        types = [m.get("type") for m in msgs]
        assert any("presence" in (t or "") for t in types), f"expected presence message; got types={types}"
        assert any("task" in (t or "") and "created" in (t or "") for t in types), (
            f"expected task.created broadcast; got types={types}"
        )
