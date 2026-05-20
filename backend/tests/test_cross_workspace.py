"""Cross-workspace deep-linking + Views regression tests (Iter 5).

Validates the bug fix where a user belonging to MULTIPLE workspaces could not
access a project owned by another workspace because the project endpoints
were forcing `active_workspace` to match. The fix introduced
`get_accessible_project / _task / _sprint` helpers and also broadened
`/api/my-issues` to query across all workspaces a user belongs to. Accepting
an invite now sets the `active_workspace` cookie to the joined workspace.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://flow-dev-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@taskflow.com"
DEMO_PASSWORD = "demo1234"


# ----------------- helpers -----------------
def _register(prefix="dummy"):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "pw12345678", "name": f"Test {prefix}",
    })
    assert r.status_code == 200, r.text
    return s, email


@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def demo_invite_code(demo_session):
    r = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 7})
    assert r.status_code == 200, r.text
    return r.json()["code"]


# =========================================================================
# 1) Cross-workspace deep linking
# =========================================================================
class TestCrossWorkspaceDeepLink:
    """Dummy user has 2 workspaces (own auto Inbox + joined LinearSync).
    Accessing the LinearSync project must succeed regardless of which one is
    the 'active' workspace cookie."""

    def test_full_scenario(self, demo_session, demo_invite_code):
        # --- Register userB and call /me which auto-creates their own ws ---
        s_b, email_b = _register("uB")
        me = s_b.get(f"{API}/auth/me")
        assert me.status_code == 200
        user_b_id = me.json()["user_id"]

        # Trigger workspace auto-creation by listing projects (mirrors AppIndex flow)
        s_b.get(f"{API}/projects")
        # /workspaces — userB should have at least 1 workspace (own)
        own = s_b.get(f"{API}/workspaces").json()
        assert len(own) >= 1, f"expected ws auto-created, got {own}"
        own_ws_id = own[0]["workspace_id"]

        # Simulate AppIndex auto-creating a project in their own workspace.
        proj_resp = s_b.post(
            f"{API}/projects",
            json={"name": "TEST_Inbox", "key": "INB"},
            headers={"X-Workspace-Id": own_ws_id},
        )
        assert proj_resp.status_code == 200, proj_resp.text

        # --- Accept invite to LinearSync (demo's workspace) ---
        accept = s_b.post(f"{API}/invites/{demo_invite_code}/accept")
        assert accept.status_code == 200, accept.text
        joined_ws_id = accept.json()["workspace_id"]
        # Cookie must be set to joined workspace
        assert s_b.cookies.get("active_workspace") == joined_ws_id

        # userB now belongs to TWO workspaces (own + LinearSync)
        ws_list = s_b.get(f"{API}/workspaces").json()
        ws_ids = [w["workspace_id"] for w in ws_list]
        assert joined_ws_id in ws_ids
        assert own_ws_id in ws_ids, "Inbox workspace must be retained because it had projects"
        assert len(ws_ids) >= 2

        # --- Demo (owner) assigns a task in CORE project to userB ---
        # Create a task in CORE so we can deterministically assign userB
        core_pid = "proj_coreplatform"
        t = demo_session.post(
            f"{API}/projects/{core_pid}/tasks",
            json={"title": "TEST_xws_assigned", "assignee_id": user_b_id, "priority": "high"},
        )
        assert t.status_code == 200, t.text
        task_id = t.json()["task_id"]

        # --- Force userB's active_workspace cookie back to OWN ws ---
        # This is the exact bug scenario: active != project's workspace
        s_b.cookies.set("active_workspace", own_ws_id)

        # GET /projects/{id} should succeed (was 404 before fix)
        r = s_b.get(f"{API}/projects/{core_pid}")
        assert r.status_code == 200, f"Cross-workspace project GET failed: {r.status_code} {r.text}"
        assert r.json()["project_id"] == core_pid

        # GET /projects/{id}/tasks should succeed
        r = s_b.get(f"{API}/projects/{core_pid}/tasks")
        assert r.status_code == 200, r.text
        ids = [tt["task_id"] for tt in r.json()]
        assert task_id in ids

        # GET /my-issues should include the assigned task across workspaces
        r = s_b.get(f"{API}/my-issues")
        assert r.status_code == 200
        my = r.json()
        assert any(tt["task_id"] == task_id for tt in my), "my-issues missing cross-ws task"

        # cleanup
        demo_session.delete(f"{API}/tasks/{task_id}")


# =========================================================================
# 2) accept-invite cookie semantics
# =========================================================================
class TestAcceptInviteCookie:
    def test_accept_sets_active_workspace_cookie(self, demo_session, demo_invite_code):
        s, _ = _register("inv")
        # Pre-condition: cookie not set
        assert not s.cookies.get("active_workspace")
        r = s.post(f"{API}/invites/{demo_invite_code}/accept")
        assert r.status_code == 200
        body = r.json()
        assert s.cookies.get("active_workspace") == body["workspace_id"]

    def test_accept_idempotent_when_already_member(self, demo_session, demo_invite_code):
        s, _ = _register("inv2")
        r1 = s.post(f"{API}/invites/{demo_invite_code}/accept")
        assert r1.status_code == 200
        first_ws = r1.json()["workspace_id"]
        # Second call should still set cookie and report already_member
        r2 = s.post(f"{API}/invites/{demo_invite_code}/accept")
        assert r2.status_code == 200
        assert r2.json()["workspace_id"] == first_ws
        assert r2.json().get("already_member") is True
        assert s.cookies.get("active_workspace") == first_ws


# =========================================================================
# 3) Sprint endpoints — accessible regardless of active workspace
# =========================================================================
class TestSprintCrossWorkspace:
    @pytest.fixture(scope="class")
    def joined_session_and_sprint(self, demo_session):
        # Create an invite for this test class
        r = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 1})
        code = r.json()["code"]
        s, _ = _register("spr")
        r2 = s.post(f"{API}/invites/{code}/accept")
        assert r2.status_code == 200
        joined_ws = r2.json()["workspace_id"]
        # Demo creates a sprint
        from datetime import datetime, timedelta, timezone
        start = datetime.now(timezone.utc).date().isoformat()
        end = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
        sp = demo_session.post(
            f"{API}/projects/proj_coreplatform/sprints",
            json={"name": "TEST_xws_sprint", "start_date": start, "end_date": end, "goal": "x"},
        )
        assert sp.status_code == 200, sp.text
        sprint_id = sp.json()["sprint_id"]
        yield s, joined_ws, sprint_id
        demo_session.delete(f"{API}/sprints/{sprint_id}")

    def test_get_sprint_works_with_mismatched_active_ws(self, joined_session_and_sprint):
        s, joined_ws, sprint_id = joined_session_and_sprint
        # Force active ws to user's own (not joined)
        s.get(f"{API}/projects")  # trigger auto-create if needed
        own = s.get(f"{API}/workspaces").json()
        other = next((w for w in own if w["workspace_id"] != joined_ws), None)
        if other:
            s.cookies.set("active_workspace", other["workspace_id"])
        # No GET /sprints/{id} endpoint; use PATCH (no-op-ish) to verify
        # `get_accessible_sprint` works regardless of active ws.
        r = s.patch(f"{API}/sprints/{sprint_id}", json={"goal": "TEST_xws_goal"})
        assert r.status_code == 200, r.text
        assert r.json()["sprint_id"] == sprint_id

        # Also exercise add/remove task endpoints (both use get_accessible_sprint)
        # add a real task created by demo to be safe — create one quickly via API
        # (we just sanity check the endpoint accepts the call without a 4xx workspace error)
        r2 = s.post(f"{API}/sprints/{sprint_id}/tasks", json={"task_ids": []})
        assert r2.status_code == 200, r2.text

    def test_burndown_cross_workspace(self, joined_session_and_sprint):
        s, _, sprint_id = joined_session_and_sprint
        r = s.get(f"{API}/sprints/{sprint_id}/burndown")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "series" in body


# =========================================================================
# 4) Attachment delete uses get_accessible_task (no active-ws coupling)
# =========================================================================
class TestAttachmentCrossWorkspace:
    def test_uploader_can_delete_with_mismatched_active_ws(self, demo_session):
        # Create invite, register dummy, accept
        code = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 1}).json()["code"]
        s, _ = _register("att")
        r = s.post(f"{API}/invites/{code}/accept")
        joined_ws = r.json()["workspace_id"]

        # Demo creates a task, dummy uploads an attachment
        t = demo_session.post(
            f"{API}/projects/proj_coreplatform/tasks",
            json={"title": "TEST_xws_att"},
        ).json()
        task_id = t["task_id"]

        att = s.post(f"{API}/tasks/{task_id}/attachments", json={
            "public_id": f"test_{uuid.uuid4().hex[:8]}",
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/test.png",
            "resource_type": "image", "format": "png", "bytes": 100,
            "original_filename": "TEST_xws.png",
        })
        assert att.status_code == 200, att.text
        att_id = att.json()["attachment_id"]

        # Force dummy's active ws to something other than joined
        s.get(f"{API}/projects")
        own = s.get(f"{API}/workspaces").json()
        other = next((w for w in own if w["workspace_id"] != joined_ws), None)
        if other:
            s.cookies.set("active_workspace", other["workspace_id"])

        # Dummy (uploader) should be able to delete despite mismatched active ws
        d = s.delete(f"{API}/attachments/{att_id}")
        assert d.status_code == 200, d.text

        # cleanup
        demo_session.delete(f"{API}/tasks/{task_id}")
