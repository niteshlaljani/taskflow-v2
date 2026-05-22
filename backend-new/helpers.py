import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response
from config import JWT_SECRET, JWT_ALGORITHM
from database import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": now_utc() + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_jwt_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")


# ── Auth dependency ───────────────────────────────────────
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if user:
                return user
        except jwt.PyJWTError:
            pass

    session_token = request.cookies.get("session_token")
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > now_utc():
                user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
                if user:
                    return user

    raise HTTPException(status_code=401, detail="Not authenticated")


# ── Workspace resolver ────────────────────────────────────
async def get_user_workspace(user: dict, active_id=None) -> dict:
    if active_id:
        candidate = await db.workspaces.find_one(
            {"workspace_id": active_id, "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
            {"_id": 0},
        )
        if candidate:
            return candidate

    ws = await db.workspaces.find_one(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        import uuid
        ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        ws = {
            "workspace_id": ws_id,
            "name": f"{user['name'].split()[0]}'s Workspace",
            "slug": f"ws-{ws_id[-6:]}",
            "owner_id": user["user_id"],
            "member_ids": [user["user_id"]],
            "created_at": iso(now_utc()),
        }
        await db.workspaces.insert_one(dict(ws))
        ws.pop("_id", None)
    elif user["user_id"] not in (ws.get("member_ids") or []):
        await db.workspaces.update_one(
            {"workspace_id": ws["workspace_id"]},
            {"$addToSet": {"member_ids": user["user_id"]}},
        )
        ws["member_ids"] = list(set((ws.get("member_ids") or []) + [user["user_id"]]))
    return ws


async def resolve_workspace(request: Request, user: dict) -> dict:
    active = request.headers.get("X-Workspace-Id") or request.cookies.get("active_workspace")
    return await get_user_workspace(user, active)


async def get_accessible_project(project_id: str, user: dict):
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    ws = await db.workspaces.find_one(
        {"workspace_id": proj["workspace_id"], "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Project not found")
    return proj, ws


async def get_accessible_task(task_id: str, user: dict):
    t = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Task not found")
    ws = await db.workspaces.find_one(
        {"workspace_id": t["workspace_id"], "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Task not found")
    return t, ws


async def get_accessible_sprint(sprint_id: str, user: dict):
    sprint = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")
    ws = await db.workspaces.find_one(
        {"workspace_id": sprint["workspace_id"], "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Sprint not found")
    return sprint, ws


async def notify(user_id: str, by_user_id: str, ntype: str, task_id=None, comment_id=None, message=None, project_id=None):
    if not user_id or user_id == by_user_id:
        return
    import uuid
    doc = {
        "notification_id": f"nt_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "by_user_id": by_user_id,
        "type": ntype,
        "task_id": task_id,
        "comment_id": comment_id,
        "project_id": project_id,
        "message": message,
        "read": False,
        "created_at": iso(now_utc()),
    }
    await db.notifications.insert_one(dict(doc))
    doc.pop("_id", None)
