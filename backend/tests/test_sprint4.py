"""Sprint 4 backend regression tests.

Covers:
  - Multi-workspace list + switch
  - X-Workspace-Id header scoping
  - Sprints CRUD + add/remove tasks + burndown + velocity
  - Notifications: assignment + comment-triggered + list/unread/read
  - Cloudinary signature
  - Attachments metadata CRUD
  - DELETE /api/projects cascade (tasks, comments, attachments, sprints)
  - CORS regex for preview URL
"""
import os
import uuid
import time
import pytest
import requests
from datetime import date, timedelta

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://flow-dev-1.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@taskflow.com"
DEMO_PASSWORD = "demo1234"
PROJECT_ID = "proj_coreplatform"
LINEARSYNC_WS = "ws_linearsync001"


@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return s


# ---------------- Workspaces list/switch ----------------
class TestWorkspaces:
    def test_list_workspaces_returns_linearsync(self, demo_session):
        r = demo_session.get(f"{API}/workspaces")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        ids = [w["workspace_id"] for w in items]
        assert LINEARSYNC_WS in ids

    def test_switch_workspace_success_sets_cookie(self, demo_session):
        r = demo_session.post(f"{API}/workspaces/switch", json={"workspace_id": LINEARSYNC_WS})
        assert r.status_code == 200, r.text
        assert r.json()["workspace_id"] == LINEARSYNC_WS
        # Cookie should be set
        assert demo_session.cookies.get("active_workspace") == LINEARSYNC_WS

    def test_switch_workspace_no_access_404(self, demo_session):
        r = demo_session.post(f"{API}/workspaces/switch", json={"workspace_id": "ws_nonexistent_xyz"})
        assert r.status_code == 404

    def test_x_workspace_id_header_scopes_projects(self, demo_session):
        # demo only has LinearSync -> sending its id should still work
        r = demo_session.get(f"{API}/projects", headers={"X-Workspace-Id": LINEARSYNC_WS})
        assert r.status_code == 200
        ids = [p["project_id"] for p in r.json()]
        assert PROJECT_ID in ids
        # Header for ws user does not belong to: should fall back to user's ws
        r2 = demo_session.get(f"{API}/projects", headers={"X-Workspace-Id": "ws_fake_other_999"})
        assert r2.status_code == 200  # falls back to user's actual ws, no leak


# ---------------- Sprints ----------------
@pytest.fixture(scope="class")
def sprint_ctx(demo_session):
    """Create a sprint to operate on; cleanup at end of class."""
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=10)).isoformat()
    r = demo_session.post(
        f"{API}/projects/{PROJECT_ID}/sprints",
        json={"name": f"TEST_sprint_{uuid.uuid4().hex[:5]}", "goal": "test", "start_date": start, "end_date": end},
    )
    assert r.status_code == 200, r.text
    sp = r.json()
    yield sp
    # cleanup
    demo_session.delete(f"{API}/sprints/{sp['sprint_id']}")


class TestSprints:
    def test_create_sprint_initial_status_planned(self, sprint_ctx):
        assert sprint_ctx["status"] == "planned"
        assert sprint_ctx["task_ids"] == []
        assert sprint_ctx["sprint_id"].startswith("spr_")

    def test_list_sprints_includes_created(self, demo_session, sprint_ctx):
        r = demo_session.get(f"{API}/projects/{PROJECT_ID}/sprints")
        assert r.status_code == 200
        ids = [s["sprint_id"] for s in r.json()]
        assert sprint_ctx["sprint_id"] in ids

    def test_patch_status_planned_to_active(self, demo_session, sprint_ctx):
        r = demo_session.patch(f"{API}/sprints/{sprint_ctx['sprint_id']}", json={"status": "active"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_add_tasks_to_sprint(self, demo_session, sprint_ctx):
        # Pick 2 real seeded tasks
        tlist = demo_session.get(f"{API}/projects/{PROJECT_ID}/tasks").json()
        tids = [t["task_id"] for t in tlist[:2]]
        r = demo_session.post(f"{API}/sprints/{sprint_ctx['sprint_id']}/tasks", json={"task_ids": tids})
        assert r.status_code == 200
        assert set(tids).issubset(set(r.json()["task_ids"]))

    def test_remove_task_from_sprint(self, demo_session, sprint_ctx):
        tlist = demo_session.get(f"{API}/projects/{PROJECT_ID}/tasks").json()
        tid = tlist[0]["task_id"]
        r = demo_session.delete(f"{API}/sprints/{sprint_ctx['sprint_id']}/tasks/{tid}")
        assert r.status_code == 200
        assert tid not in r.json()["task_ids"]

    def test_burndown_shape(self, demo_session, sprint_ctx):
        r = demo_session.get(f"{API}/sprints/{sprint_ctx['sprint_id']}/burndown")
        assert r.status_code == 200, r.text
        b = r.json()
        for k in ("sprint_id", "name", "total", "completed", "series"):
            assert k in b
        assert isinstance(b["series"], list) and len(b["series"]) >= 1
        first = b["series"][0]
        for k in ("date", "remaining", "ideal"):
            assert k in first

    def test_complete_sets_completed_at(self, demo_session, sprint_ctx):
        r = demo_session.patch(f"{API}/sprints/{sprint_ctx['sprint_id']}", json={"status": "completed"})
        assert r.status_code == 200
        s = r.json()
        assert s["status"] == "completed"
        assert s.get("completed_at"), "completed_at not set on completion"

    def test_velocity_counts_only_completed(self, demo_session, sprint_ctx):
        r = demo_session.get(f"{API}/projects/{PROJECT_ID}/velocity")
        assert r.status_code == 200
        v = r.json()
        assert "sprints" in v and "average" in v
        names = [x["name"] for x in v["sprints"]]
        assert sprint_ctx["name"] in names

    def test_delete_sprint_non_owner_403(self, demo_session, sprint_ctx):
        # New non-owner user (not member of LinearSync) — should 404 not 403
        s = requests.Session()
        em = f"test_{uuid.uuid4().hex[:8]}@example.com"
        s.post(f"{API}/auth/register", json={"email": em, "password": "secret123", "name": "x"})
        r = s.delete(f"{API}/sprints/{sprint_ctx['sprint_id']}")
        # resolve_workspace will use their own ws -> 404 from filter
        assert r.status_code in (403, 404)


# ---------------- Notifications ----------------
class TestNotifications:
    def test_list_notifications_shape(self, demo_session):
        r = demo_session.get(f"{API}/notifications")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_unread_count_shape(self, demo_session):
        r = demo_session.get(f"{API}/notifications/unread-count")
        assert r.status_code == 200
        assert "count" in r.json()
        assert isinstance(r.json()["count"], int)

    def test_assigning_task_creates_notification_for_assignee(self, demo_session):
        # Register a fresh user, accept invite into LinearSync; demo assigns to them
        joiner = requests.Session()
        em = f"test_{uuid.uuid4().hex[:8]}@example.com"
        rj = joiner.post(f"{API}/auth/register", json={"email": em, "password": "secret123", "name": "Joiner"})
        assert rj.status_code == 200
        # create invite as owner, joiner accepts
        inv = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 1}).json()
        ra = joiner.post(f"{API}/invites/{inv['code']}/accept")
        assert ra.status_code == 200
        joiner_user_id = joiner.get(f"{API}/auth/me").json()["user_id"]
        # demo creates a task and assigns to joiner -> should create notification for joiner
        rc = demo_session.post(
            f"{API}/projects/{PROJECT_ID}/tasks",
            json={"title": "TEST_notif_assign", "status": "todo", "assignee_id": joiner_user_id},
        )
        assert rc.status_code == 200, rc.text
        tid = rc.json()["task_id"]
        time.sleep(0.5)
        # Joiner should now see 1 unread notification of type 'assigned'
        rn = joiner.get(f"{API}/notifications")
        assert rn.status_code == 200
        notifs = rn.json()
        assert any(n.get("type") == "assigned" and n.get("task_id") == tid for n in notifs), f"got {notifs}"
        # mark one as read
        nid = next(n["notification_id"] for n in notifs if n["type"] == "assigned" and n["task_id"] == tid)
        rr = joiner.post(f"{API}/notifications/{nid}/read")
        assert rr.status_code == 200
        # comment by demo should create comment-type notification for joiner (assignee)
        rcom = demo_session.post(f"{API}/tasks/{tid}/comments", json={"body": "TEST_notif_comment"})
        assert rcom.status_code == 200
        time.sleep(0.5)
        rn2 = joiner.get(f"{API}/notifications")
        assert any(n.get("type") == "comment" and n.get("task_id") == tid for n in rn2.json())
        # read-all clears unread
        ra2 = joiner.post(f"{API}/notifications/read-all")
        assert ra2.status_code == 200
        rc2 = joiner.get(f"{API}/notifications/unread-count")
        assert rc2.json()["count"] == 0
        # cleanup task
        demo_session.delete(f"{API}/tasks/{tid}")


# ---------------- Cloudinary signature ----------------
class TestCloudinary:
    def test_signature_returns_valid_params(self, demo_session):
        r = demo_session.get(f"{API}/cloudinary/signature", params={"folder": "taskflow/attachments", "resource_type": "auto"})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("signature", "timestamp", "cloud_name", "api_key", "folder", "resource_type"):
            assert k in d and d[k] not in (None, "")
        assert d["folder"] == "taskflow/attachments"
        assert d["resource_type"] == "auto"
        assert isinstance(d["timestamp"], int)
        assert len(d["signature"]) >= 20

    def test_signature_rejects_invalid_folder(self, demo_session):
        r = demo_session.get(f"{API}/cloudinary/signature", params={"folder": "other/x"})
        assert r.status_code == 400

    def test_signature_requires_auth(self):
        r = requests.get(f"{API}/cloudinary/signature")
        assert r.status_code == 401


# ---------------- Attachments ----------------
class TestAttachments:
    def test_create_list_delete_attachment(self, demo_session):
        # Create a task to attach to
        rt = demo_session.post(
            f"{API}/projects/{PROJECT_ID}/tasks",
            json={"title": "TEST_att_task", "status": "todo"},
        )
        tid = rt.json()["task_id"]
        try:
            payload = {
                "public_id": "taskflow/attachments/fake_test_123",
                "secure_url": "https://res.cloudinary.com/dtmuagy3y/image/upload/v1/fake_test_123.png",
                "resource_type": "image",
                "format": "png",
                "bytes": 12345,
                "original_filename": "fake_test.png",
            }
            rc = demo_session.post(f"{API}/tasks/{tid}/attachments", json=payload)
            assert rc.status_code == 200, rc.text
            att = rc.json()
            assert att["public_id"] == payload["public_id"]
            assert att["secure_url"] == payload["secure_url"]
            aid = att["attachment_id"]
            # list
            rl = demo_session.get(f"{API}/tasks/{tid}/attachments")
            assert rl.status_code == 200
            assert any(a["attachment_id"] == aid for a in rl.json())
            # delete - will attempt cloudinary destroy on fake id (returns not_found, but endpoint should still succeed)
            rd = demo_session.delete(f"{API}/attachments/{aid}")
            assert rd.status_code == 200
            # verify gone
            rl2 = demo_session.get(f"{API}/tasks/{tid}/attachments")
            assert not any(a["attachment_id"] == aid for a in rl2.json())
        finally:
            demo_session.delete(f"{API}/tasks/{tid}")

    def test_attachment_delete_by_non_uploader_non_owner_forbidden(self, demo_session):
        # demo (owner) creates task + attachment; joiner (member, non-uploader) attempts delete -> 403
        rt = demo_session.post(
            f"{API}/projects/{PROJECT_ID}/tasks",
            json={"title": "TEST_att_perm", "status": "todo"},
        )
        tid = rt.json()["task_id"]
        rc = demo_session.post(
            f"{API}/tasks/{tid}/attachments",
            json={"public_id": "taskflow/attachments/perm_test", "secure_url": "https://x/y.png", "resource_type": "image"},
        )
        aid = rc.json()["attachment_id"]
        # Joiner accepts invite
        joiner = requests.Session()
        em = f"test_{uuid.uuid4().hex[:8]}@example.com"
        joiner.post(f"{API}/auth/register", json={"email": em, "password": "secret123", "name": "J"})
        inv = demo_session.post(f"{API}/workspaces/invites", json={"expires_in_days": 1}).json()
        joiner.post(f"{API}/invites/{inv['code']}/accept")
        rd = joiner.delete(f"{API}/attachments/{aid}")
        assert rd.status_code == 403, f"expected 403 for non-uploader/non-owner, got {rd.status_code}: {rd.text}"
        # cleanup
        demo_session.delete(f"{API}/attachments/{aid}")
        demo_session.delete(f"{API}/tasks/{tid}")


# ---------------- Project cascade delete ----------------
class TestProjectCascadeDelete:
    def test_delete_project_cascades_tasks_comments_attachments_sprints(self, demo_session):
        # Create project
        key = f"C{uuid.uuid4().hex[:4].upper()}"
        rp = demo_session.post(f"{API}/projects", json={"name": "TEST_cascade", "key": key, "description": ""})
        assert rp.status_code == 200
        pid = rp.json()["project_id"]
        # Create task
        rt = demo_session.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_c_task", "status": "todo"})
        tid = rt.json()["task_id"]
        # Comment on task
        rc = demo_session.post(f"{API}/tasks/{tid}/comments", json={"body": "TEST_c_comment"})
        assert rc.status_code == 200
        # Attachment on task
        ra = demo_session.post(
            f"{API}/tasks/{tid}/attachments",
            json={"public_id": "taskflow/attachments/casc", "secure_url": "https://x/y.png", "resource_type": "image"},
        )
        assert ra.status_code == 200
        # Sprint in project
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=5)).isoformat()
        rs = demo_session.post(
            f"{API}/projects/{pid}/sprints",
            json={"name": "TEST_c_sprint", "goal": "", "start_date": start, "end_date": end},
        )
        assert rs.status_code == 200
        sid = rs.json()["sprint_id"]
        # DELETE project
        rd = demo_session.delete(f"{API}/projects/{pid}")
        assert rd.status_code == 200, rd.text
        # Verify ALL gone
        assert demo_session.get(f"{API}/projects/{pid}").status_code == 404
        assert demo_session.get(f"{API}/tasks/{tid}").status_code == 404
        # comments gone (the GET on task is 404; verify direct count via comments endpoint is not possible w/o task,
        # so check by trying to add another comment -> 404)
        rcom2 = demo_session.post(f"{API}/tasks/{tid}/comments", json={"body": "x"})
        assert rcom2.status_code == 404
        # attachment list: task 404
        assert demo_session.get(f"{API}/tasks/{tid}/attachments").status_code == 404
        # sprint gone -> burndown should 404
        assert demo_session.get(f"{API}/sprints/{sid}/burndown").status_code == 404


# ---------------- CORS ----------------
class TestCORS:
    def test_cors_preflight_from_preview_url(self):
        origin = BASE_URL
        r = requests.options(
            f"{API}/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        # FastAPI/Starlette CORSMiddleware returns 200 on successful preflight
        assert r.status_code in (200, 204), f"preflight failed: {r.status_code}: {r.text}"
        allow = r.headers.get("access-control-allow-origin")
        assert allow == origin or allow == "*", f"expected origin echo, got {allow}"
