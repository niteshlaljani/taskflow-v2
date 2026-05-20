from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import time


# ============================================================================
# Config
# ============================================================================
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
DEMO_EMAIL = os.environ.get('DEMO_EMAIL', 'demo@taskflow.com')
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo1234')
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="TaskFlow API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# WebSocket Connection Manager (board real-time sync + presence)
# ============================================================================
class BoardConnectionManager:
    def __init__(self):
        # project_id -> list of (ws, user_summary)
        self.rooms: dict = {}

    async def connect(self, project_id: str, websocket: WebSocket, user: dict):
        await websocket.accept()
        self.rooms.setdefault(project_id, []).append({"ws": websocket, "user": user})
        await self.broadcast_presence(project_id)

    async def disconnect(self, project_id: str, websocket: WebSocket):
        room = self.rooms.get(project_id) or []
        self.rooms[project_id] = [c for c in room if c["ws"] is not websocket]
        if not self.rooms[project_id]:
            self.rooms.pop(project_id, None)
        await self.broadcast_presence(project_id)

    async def broadcast(self, project_id: str, message: dict):
        room = self.rooms.get(project_id) or []
        dead = []
        for c in room:
            try:
                await c["ws"].send_json(message)
            except Exception:
                dead.append(c["ws"])
        for ws in dead:
            await self.disconnect(project_id, ws)

    async def broadcast_presence(self, project_id: str):
        room = self.rooms.get(project_id) or []
        # Deduplicate by user_id
        seen = {}
        for c in room:
            u = c["user"]
            seen[u["user_id"]] = u
        await self.broadcast(project_id, {
            "type": "presence",
            "users": list(seen.values()),
        })


board_ws = BoardConnectionManager()


# ============================================================================
# Helpers
# ============================================================================
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


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")


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


# ============================================================================
# Pydantic Models
# ============================================================================
class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "member"
    auth_provider: str = "jwt"  # "jwt" or "google"
    created_at: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionRequest(BaseModel):
    session_id: str


class WorkspaceCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class Workspace(BaseModel):
    workspace_id: str
    name: str
    slug: str
    owner_id: str
    created_at: str


class ProjectCreate(BaseModel):
    name: str
    key: str = Field(min_length=2, max_length=8)
    description: Optional[str] = ""


class Project(BaseModel):
    project_id: str
    workspace_id: str
    name: str
    key: str
    description: str = ""
    next_task_number: int = 1
    created_at: str


PriorityT = Literal["low", "medium", "high", "urgent"]
StatusT = Literal["backlog", "todo", "in_progress", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    description: Optional[str] = ""
    status: StatusT = "todo"
    priority: PriorityT = "medium"
    assignee_id: Optional[str] = None
    tag: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusT] = None
    priority: Optional[PriorityT] = None
    assignee_id: Optional[str] = None
    tag: Optional[str] = None


class Task(BaseModel):
    task_id: str
    project_id: str
    workspace_id: str
    number: int
    key: str  # e.g. CORE-254
    title: str
    description: str = ""
    status: StatusT
    priority: PriorityT
    assignee_id: Optional[str] = None
    tag: Optional[str] = None
    creator_id: str
    created_at: str
    updated_at: str


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class Comment(BaseModel):
    comment_id: str
    task_id: str
    author_id: str
    body: str
    created_at: str


# ============================================================================
# Auth Dependency
# ============================================================================
async def get_current_user(request: Request) -> dict:
    # 1) Try JWT access_token cookie
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

    # 2) Try session_token cookie (Emergent Google Auth)
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


async def get_user_workspace(user: dict, active_id: Optional[str] = None) -> dict:
    """Resolve the current workspace for a user.
    If `active_id` is provided and the user owns/belongs to it, return it.
    Otherwise return the first workspace the user is in (auto-create if none).
    """
    if active_id:
        candidate = await db.workspaces.find_one(
            {
                "workspace_id": active_id,
                "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}],
            },
            {"_id": 0},
        )
        if candidate:
            return candidate

    # Find workspace where user is owner OR member
    ws = await db.workspaces.find_one(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        # auto-create a personal workspace
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
        # backfill: ensure owner is in member_ids
        await db.workspaces.update_one(
            {"workspace_id": ws["workspace_id"]},
            {"$addToSet": {"member_ids": user["user_id"]}},
        )
        ws["member_ids"] = list(set((ws.get("member_ids") or []) + [user["user_id"]]))
    return ws


async def resolve_workspace(request: Request, user: dict) -> dict:
    """Pick the active workspace from `X-Workspace-Id` header or `active_workspace` cookie if present."""
    active = request.headers.get("X-Workspace-Id") or request.cookies.get("active_workspace")
    return await get_user_workspace(user, active)


async def get_accessible_project(project_id: str, user: dict) -> tuple[dict, dict]:
    """Find a project ANYWHERE the user has access (across all their workspaces).

    Returns (project, workspace). Raises 404 if not found or no access.
    Use this for any endpoint addressed by a specific project_id — it removes the
    'active workspace must match' coupling, so notification-deep-links and
    multi-workspace flows resolve correctly.
    """
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    ws = await db.workspaces.find_one(
        {
            "workspace_id": proj["workspace_id"],
            "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}],
        },
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Project not found")
    return proj, ws


async def get_accessible_task(task_id: str, user: dict) -> tuple[dict, dict]:
    """Find a task across all workspaces the user belongs to. Returns (task, workspace)."""
    t = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Task not found")
    ws = await db.workspaces.find_one(
        {
            "workspace_id": t["workspace_id"],
            "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}],
        },
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Task not found")
    return t, ws


# ============================================================================
# Auth Endpoints
# ============================================================================
@api_router.post("/auth/register")
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "picture": None,
        "role": "member",
        "auth_provider": "jwt",
        "password_hash": hash_password(payload.password),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user_doc)

    token = create_access_token(user_id, email)
    set_jwt_cookie(response, token)
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return {"user": user_doc, "access_token": token}


@api_router.post("/auth/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user["user_id"], email)
    set_jwt_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"user": user, "access_token": token}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    # If there's a session_token, delete the session from DB
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    clear_auth_cookies(response)
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/ws-token")
async def ws_token(user: dict = Depends(get_current_user)):
    """Mint a short-lived JWT to authenticate the WS handshake when cookies aren't forwarded by the ingress."""
    token = jwt.encode(
        {
            "sub": user["user_id"],
            "email": user.get("email", ""),
            "type": "access",
            "exp": now_utc() + timedelta(minutes=30),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {"token": token}


@api_router.post("/auth/session")
async def auth_session(payload: SessionRequest, response: Response):
    """Exchange Emergent session_id (from URL fragment) for a session_token cookie."""
    async with httpx.AsyncClient(timeout=15) as cli:
        try:
            r = await cli.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": payload.session_id},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.exception("Emergent session exchange failed")
            raise HTTPException(status_code=401, detail=f"Auth session exchange failed: {e}")

    email = (data.get("email") or "").lower().strip()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture")
    session_token = data["session_token"]

    if not email:
        raise HTTPException(status_code=400, detail="No email returned from auth provider")

    # Upsert user (link by email if exists)
    existing = await db.users.find_one({"email": email})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "member",
            "auth_provider": "google",
            "created_at": iso(now_utc()),
        })

    # Store session
    expires_at = now_utc() + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "session_token": session_token,
            "user_id": user_id,
            "expires_at": expires_at,
            "created_at": now_utc(),
        }},
        upsert=True,
    )
    set_session_cookie(response, session_token)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user}


# ============================================================================
# Workspaces & Projects
# ============================================================================
@api_router.get("/workspaces/current")
async def current_workspace(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    return ws


@api_router.get("/projects")
async def list_projects(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    items = await db.projects.find({"workspace_id": ws["workspace_id"]}, {"_id": 0}).to_list(200)
    return items


@api_router.post("/projects")
async def create_project(request: Request, payload: ProjectCreate, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    key = payload.key.upper()
    project = {
        "project_id": f"proj_{uuid.uuid4().hex[:12]}",
        "workspace_id": ws["workspace_id"],
        "name": payload.name,
        "key": key,
        "description": payload.description or "",
        "next_task_number": 1,
        "created_at": iso(now_utc()),
    }
    await db.projects.insert_one(dict(project))
    project.pop("_id", None)
    return project


@api_router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str, user: dict = Depends(get_current_user)):
    p, _ = await get_accessible_project(project_id, user)
    return p


# ============================================================================
# Members
# ============================================================================
@api_router.get("/workspaces/members")
async def list_members(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    member_ids = set([ws["owner_id"]])
    for m in (ws.get("member_ids") or []):
        member_ids.add(m)
    # Plus anyone referenced as a task assignee (covers seeded demo teammates)
    assignees = await db.tasks.distinct("assignee_id", {"workspace_id": ws["workspace_id"]})
    for a in assignees:
        if a:
            member_ids.add(a)
    members = await db.users.find(
        {"user_id": {"$in": list(member_ids)}},
        {"_id": 0, "password_hash": 0},
    ).to_list(200)
    return members


# ============================================================================
# Tasks
# ============================================================================
@api_router.get("/projects/{project_id}/tasks")
async def list_tasks(request: Request, project_id: str, user: dict = Depends(get_current_user)):
    proj, ws = await get_accessible_project(project_id, user)
    tasks = await db.tasks.find({"project_id": project_id}, {"_id": 0}).sort("number", -1).to_list(500)
    return tasks


@api_router.post("/projects/{project_id}/tasks")
async def create_task(request: Request, project_id: str, payload: TaskCreate, user: dict = Depends(get_current_user)):
    # Verify access first
    _proj, ws = await get_accessible_project(project_id, user)
    proj = await db.projects.find_one_and_update(
        {"project_id": project_id},
        {"$inc": {"next_task_number": 1}},
    )
    if not proj:
        raise HTTPException(404, "Project not found")
    # default returns the document BEFORE update; this gives us the next number
    number = int(proj.get("next_task_number", 1))

    task = {
        "task_id": f"task_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "workspace_id": ws["workspace_id"],
        "number": number,
        "key": f"{proj['key']}-{number}",
        "title": payload.title,
        "description": payload.description or "",
        "status": payload.status,
        "priority": payload.priority,
        "assignee_id": payload.assignee_id,
        "tag": payload.tag,
        "creator_id": user["user_id"],
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.tasks.insert_one(dict(task))
    task.pop("_id", None)
    await board_ws.broadcast(project_id, {"type": "task.created", "task": task, "by": user["user_id"]})
    if task.get("assignee_id") and task["assignee_id"] != user["user_id"]:
        await _notify(
            user_id=task["assignee_id"],
            by_user_id=user["user_id"],
            ntype="assigned",
            task_id=task["task_id"],
            project_id=project_id,
            message=f"{user.get('name','Someone')} assigned you {task['key']}: {task['title']}",
        )
    return task


@api_router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    return t


@api_router.patch("/tasks/{task_id}")
async def update_task(request: Request, task_id: str, payload: TaskUpdate, user: dict = Depends(get_current_user)):
    _t, ws = await get_accessible_task(task_id, user)
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k in ["assignee_id", "tag", "description"]}
    if not update:
        raise HTTPException(400, "Nothing to update")
    update["updated_at"] = iso(now_utc())
    result = await db.tasks.update_one(
        {"task_id": task_id},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Task not found")
    t = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
    await board_ws.broadcast(t["project_id"], {"type": "task.updated", "task": t, "by": user["user_id"]})
    # Notify on assignment change
    if "assignee_id" in update and update["assignee_id"] and update["assignee_id"] != user["user_id"]:
        await _notify(
            user_id=update["assignee_id"],
            by_user_id=user["user_id"],
            ntype="assigned",
            task_id=task_id,
            project_id=t["project_id"],
            message=f"{user.get('name','Someone')} assigned you {t['key']}: {t['title']}",
        )
    return t


@api_router.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    await db.tasks.delete_one({"task_id": task_id})
    await db.comments.delete_many({"task_id": task_id})
    await board_ws.broadcast(t["project_id"], {"type": "task.deleted", "task_id": task_id, "by": user["user_id"]})
    return {"ok": True}


# ============================================================================
# Comments
# ============================================================================
@api_router.get("/tasks/{task_id}/comments")
async def list_comments(request: Request, task_id: str, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    comments = await db.comments.find({"task_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return comments


async def _notify(user_id: str, by_user_id: str, ntype: str, task_id: str = None, comment_id: str = None, message: str = None, project_id: str = None):
    """Insert a notification and push via WS if user is connected on the board."""
    if not user_id or user_id == by_user_id:
        return
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
    if project_id:
        await board_ws.broadcast(project_id, {"type": "notification.created", "for": user_id, "notification": doc})


@api_router.post("/tasks/{task_id}/comments")
async def add_comment(request: Request, task_id: str, payload: CommentCreate, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    c = {
        "comment_id": f"cmt_{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "author_id": user["user_id"],
        "body": payload.body,
        "created_at": iso(now_utc()),
    }
    await db.comments.insert_one(dict(c))
    c.pop("_id", None)
    await board_ws.broadcast(t["project_id"], {"type": "comment.created", "task_id": task_id, "comment": c, "by": user["user_id"]})
    # Notify task assignee (if not the commenter)
    if t.get("assignee_id"):
        await _notify(
            user_id=t["assignee_id"],
            by_user_id=user["user_id"],
            ntype="comment",
            task_id=task_id,
            comment_id=c["comment_id"],
            project_id=t["project_id"],
            message=f"{user.get('name','Someone')} commented on {t['key']}",
        )
    return c


# ============================================================================
# WebSocket (board real-time + presence)
# ============================================================================
async def _authenticate_ws(websocket: WebSocket) -> Optional[dict]:
    """Authenticate WS by reading either the access_token / session_token cookie."""
    # Try cookies
    token = websocket.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            u = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if u:
                return u
        except jwt.PyJWTError:
            pass

    session_token = websocket.cookies.get("session_token")
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > now_utc():
                u = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
                if u:
                    return u

    # Fallback: ?token=<jwt> query param (since browsers don't allow custom headers on WS)
    qtoken = websocket.query_params.get("token")
    if qtoken:
        try:
            payload = jwt.decode(qtoken, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            u = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if u:
                return u
        except jwt.PyJWTError:
            pass

    return None


@api_router.websocket("/ws/board/{project_id}")
async def board_websocket(websocket: WebSocket, project_id: str):
    user = await _authenticate_ws(websocket)
    if not user:
        await websocket.close(code=4401)
        return
    user_summary = {
        "user_id": user["user_id"],
        "name": user.get("name"),
        "picture": user.get("picture"),
    }
    await board_ws.connect(project_id, websocket, user_summary)
    try:
        while True:
            # Heartbeat/keepalive — clients can also send presence pings (no special handling needed)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await board_ws.disconnect(project_id, websocket)


# ============================================================================
# My Issues
# ============================================================================
@api_router.get("/my-issues")
async def my_issues(request: Request, user: dict = Depends(get_current_user)):
    # Return assigned tasks across ALL workspaces the user belongs to,
    # not just the currently-active one. Notifications & deep links assume this.
    workspaces = await db.workspaces.find(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0, "workspace_id": 1},
    ).to_list(50)
    ws_ids = [w["workspace_id"] for w in workspaces]
    tasks = await db.tasks.find(
        {"workspace_id": {"$in": ws_ids}, "assignee_id": user["user_id"]},
        {"_id": 0},
    ).sort("number", -1).to_list(500)
    return tasks


# ============================================================================
# Project delete
# ============================================================================
@api_router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str, user: dict = Depends(get_current_user)):
    proj, ws = await get_accessible_project(project_id, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the workspace owner can delete projects")
    # Cascade: delete all tasks, their comments, attachments, and any sprints belonging to this project
    task_ids = [t["task_id"] for t in await db.tasks.find({"project_id": project_id}, {"_id": 0, "task_id": 1}).to_list(5000)]
    if task_ids:
        await db.comments.delete_many({"task_id": {"$in": task_ids}})
        await db.attachments.delete_many({"task_id": {"$in": task_ids}})
    await db.tasks.delete_many({"project_id": project_id})
    await db.sprints.delete_many({"project_id": project_id})
    await db.projects.delete_one({"project_id": project_id})
    return {"ok": True}


# ============================================================================
# Workspace Invites
# ============================================================================
class InviteCreate(BaseModel):
    expires_in_days: int = 7


@api_router.post("/workspaces/invites")
async def create_invite(request: Request, payload: InviteCreate, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the workspace owner can create invites")
    code = uuid.uuid4().hex[:10]
    expires = now_utc() + timedelta(days=max(1, min(30, payload.expires_in_days)))
    invite = {
        "invite_id": f"inv_{uuid.uuid4().hex[:12]}",
        "code": code,
        "workspace_id": ws["workspace_id"],
        "created_by": user["user_id"],
        "created_at": iso(now_utc()),
        "expires_at": iso(expires),
        "used_by": [],
    }
    await db.invites.insert_one(dict(invite))
    invite.pop("_id", None)
    return invite


@api_router.get("/workspaces/invites")
async def list_invites(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    if ws["owner_id"] != user["user_id"]:
        return []
    items = await db.invites.find(
        {"workspace_id": ws["workspace_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return items


@api_router.delete("/workspaces/invites/{invite_id}")
async def revoke_invite(request: Request, invite_id: str, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the workspace owner can revoke invites")
    result = await db.invites.delete_one(
        {"invite_id": invite_id, "workspace_id": ws["workspace_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Invite not found")
    return {"ok": True}


@api_router.get("/invites/{code}")
async def get_invite(code: str):
    """Public preview endpoint for an invite code."""
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invite not found")
    expires_at = invite.get("expires_at")
    if isinstance(expires_at, str):
        expires_at_dt = datetime.fromisoformat(expires_at)
    else:
        expires_at_dt = expires_at
    if expires_at_dt and expires_at_dt.tzinfo is None:
        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
    expired = bool(expires_at_dt and expires_at_dt < now_utc())
    ws = await db.workspaces.find_one({"workspace_id": invite["workspace_id"]}, {"_id": 0})
    owner = await db.users.find_one({"user_id": invite["created_by"]}, {"_id": 0, "password_hash": 0})
    return {
        "code": invite["code"],
        "workspace_name": ws["name"] if ws else "Unknown",
        "inviter_name": owner["name"] if owner else "A teammate",
        "expired": expired,
    }


@api_router.post("/invites/{code}/accept")
async def accept_invite(code: str, response: Response, user: dict = Depends(get_current_user)):
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invite not found")
    expires_at = invite.get("expires_at")
    if isinstance(expires_at, str):
        expires_at_dt = datetime.fromisoformat(expires_at)
    else:
        expires_at_dt = expires_at
    if expires_at_dt and expires_at_dt.tzinfo is None:
        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
    if expires_at_dt and expires_at_dt < now_utc():
        raise HTTPException(400, "Invite expired")

    ws = await db.workspaces.find_one({"workspace_id": invite["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(404, "Workspace no longer exists")

    def _set_active(ws_id: str):
        response.set_cookie(
            key="active_workspace",
            value=ws_id,
            httponly=False,
            secure=True,
            samesite="none",
            max_age=60 * 60 * 24 * 365,
            path="/",
        )

    if user["user_id"] in (ws.get("member_ids") or []) or ws["owner_id"] == user["user_id"]:
        _set_active(ws["workspace_id"])
        return {"ok": True, "workspace_id": ws["workspace_id"], "already_member": True}

    await db.workspaces.update_one(
        {"workspace_id": ws["workspace_id"]},
        {"$addToSet": {"member_ids": user["user_id"]}},
    )
    # Remove user's previously-owned empty workspace
    own_ws = await db.workspaces.find_one(
        {"owner_id": user["user_id"], "workspace_id": {"$ne": ws["workspace_id"]}}, {"_id": 0}
    )
    if own_ws:
        proj_count = await db.projects.count_documents({"workspace_id": own_ws["workspace_id"]})
        if proj_count == 0:
            await db.workspaces.delete_one({"workspace_id": own_ws["workspace_id"]})

    await db.invites.update_one({"code": code}, {"$addToSet": {"used_by": user["user_id"]}})
    _set_active(ws["workspace_id"])
    return {"ok": True, "workspace_id": ws["workspace_id"], "already_member": False}


# ============================================================================
# Workspaces — list & switch (multi-workspace support)
# ============================================================================
@api_router.get("/workspaces")
async def list_my_workspaces(user: dict = Depends(get_current_user)):
    items = await db.workspaces.find(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(50)
    return items


class WorkspaceSwitch(BaseModel):
    workspace_id: str


@api_router.post("/workspaces/switch")
async def switch_workspace(payload: WorkspaceSwitch, response: Response, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one(
        {
            "workspace_id": payload.workspace_id,
            "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}],
        },
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Workspace not found or no access")
    response.set_cookie(
        key="active_workspace",
        value=payload.workspace_id,
        httponly=False,  # frontend can read for UI; not sensitive
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 365,
        path="/",
    )
    return ws


# ============================================================================
# Sprints
# ============================================================================
class SprintCreate(BaseModel):
    name: str
    goal: Optional[str] = ""
    start_date: str  # ISO date YYYY-MM-DD
    end_date: str


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[Literal["planned", "active", "completed"]] = None


@api_router.get("/projects/{project_id}/sprints")
async def list_sprints(request: Request, project_id: str, user: dict = Depends(get_current_user)):
    proj, ws = await get_accessible_project(project_id, user)
    items = await db.sprints.find({"project_id": project_id}, {"_id": 0}).sort("start_date", -1).to_list(100)
    return items


@api_router.post("/projects/{project_id}/sprints")
async def create_sprint(request: Request, project_id: str, payload: SprintCreate, user: dict = Depends(get_current_user)):
    proj, ws = await get_accessible_project(project_id, user)
    sprint = {
        "sprint_id": f"spr_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "workspace_id": ws["workspace_id"],
        "name": payload.name,
        "goal": payload.goal or "",
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "task_ids": [],
        "status": "planned",
        "created_at": iso(now_utc()),
        "completed_at": None,
    }
    await db.sprints.insert_one(dict(sprint))
    sprint.pop("_id", None)
    return sprint


async def get_accessible_sprint(sprint_id: str, user: dict) -> tuple[dict, dict]:
    """Find a sprint across all workspaces the user belongs to. Returns (sprint, workspace)."""
    sprint = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")
    ws = await db.workspaces.find_one(
        {
            "workspace_id": sprint["workspace_id"],
            "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}],
        },
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Sprint not found")
    return sprint, ws


@api_router.patch("/sprints/{sprint_id}")
async def update_sprint(request: Request, sprint_id: str, payload: SprintUpdate, user: dict = Depends(get_current_user)):
    _s, ws = await get_accessible_sprint(sprint_id, user)
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(400, "Nothing to update")
    if update.get("status") == "completed":
        update["completed_at"] = iso(now_utc())
    await db.sprints.update_one({"sprint_id": sprint_id}, {"$set": update})
    s = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
    return s


@api_router.delete("/sprints/{sprint_id}")
async def delete_sprint(request: Request, sprint_id: str, user: dict = Depends(get_current_user)):
    _s, ws = await get_accessible_sprint(sprint_id, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only workspace owner can delete sprints")
    await db.sprints.delete_one({"sprint_id": sprint_id})
    return {"ok": True}


class SprintTaskBody(BaseModel):
    task_ids: List[str]


@api_router.post("/sprints/{sprint_id}/tasks")
async def add_sprint_tasks(request: Request, sprint_id: str, payload: SprintTaskBody, user: dict = Depends(get_current_user)):
    _s, _ws = await get_accessible_sprint(sprint_id, user)
    await db.sprints.update_one(
        {"sprint_id": sprint_id},
        {"$addToSet": {"task_ids": {"$each": payload.task_ids}}},
    )
    s = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
    return s


@api_router.delete("/sprints/{sprint_id}/tasks/{task_id}")
async def remove_sprint_task(request: Request, sprint_id: str, task_id: str, user: dict = Depends(get_current_user)):
    _s, _ws = await get_accessible_sprint(sprint_id, user)
    await db.sprints.update_one({"sprint_id": sprint_id}, {"$pull": {"task_ids": task_id}})
    s = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
    return s


@api_router.get("/sprints/{sprint_id}/burndown")
async def sprint_burndown(request: Request, sprint_id: str, user: dict = Depends(get_current_user)):
    """Return ideal vs actual burn-down series for a sprint.

    Series: one entry per day from start_date through min(end_date, today),
    where `remaining` is count of tasks in sprint not yet 'done' as of end-of-day.
    """
    sprint, _ws = await get_accessible_sprint(sprint_id, user)
    task_ids = sprint.get("task_ids") or []
    total = len(task_ids)
    start = datetime.fromisoformat(sprint["start_date"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(sprint["end_date"]).replace(tzinfo=timezone.utc)
    days = max(1, (end.date() - start.date()).days)
    today = now_utc()
    # Pull tasks and their updated_at to estimate completion timeline
    tasks = await db.tasks.find({"task_id": {"$in": task_ids}}, {"_id": 0}).to_list(2000)
    # For tasks currently 'done', use updated_at as completion date; otherwise treat as not completed
    completion_dates = []
    for t in tasks:
        if t.get("status") == "done":
            try:
                cdt = datetime.fromisoformat(t["updated_at"])
            except Exception:
                continue
            if cdt.tzinfo is None:
                cdt = cdt.replace(tzinfo=timezone.utc)
            completion_dates.append(cdt)
    series = []
    cur = start
    one_day = timedelta(days=1)
    while cur.date() <= min(end, today).date():
        completed = sum(1 for d in completion_dates if d.date() <= cur.date())
        remaining = total - completed
        ideal = max(0, total - (total * ((cur.date() - start.date()).days) / days))
        series.append({
            "date": cur.date().isoformat(),
            "remaining": remaining,
            "ideal": round(ideal, 2),
        })
        cur += one_day
    return {
        "sprint_id": sprint_id,
        "name": sprint["name"],
        "total": total,
        "completed": sum(1 for t in tasks if t.get("status") == "done"),
        "series": series,
    }


@api_router.get("/projects/{project_id}/velocity")
async def project_velocity(request: Request, project_id: str, user: dict = Depends(get_current_user)):
    """Return number of tasks completed per completed sprint, plus average."""
    proj, ws = await get_accessible_project(project_id, user)
    sprints = await db.sprints.find(
        {"project_id": project_id, "status": "completed"}, {"_id": 0}
    ).sort("completed_at", 1).to_list(50)
    series = []
    for s in sprints:
        tids = s.get("task_ids") or []
        if not tids:
            series.append({"name": s["name"], "completed": 0, "total": 0})
            continue
        tasks = await db.tasks.find({"task_id": {"$in": tids}}, {"_id": 0, "status": 1}).to_list(2000)
        done = sum(1 for t in tasks if t.get("status") == "done")
        series.append({"name": s["name"], "completed": done, "total": len(tids)})
    avg = round(sum(x["completed"] for x in series) / len(series), 1) if series else 0
    return {"sprints": series, "average": avg}


# ============================================================================
# Notifications
# ============================================================================
@api_router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return items


@api_router.get("/notifications/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    c = await db.notifications.count_documents({"user_id": user["user_id"], "read": False})
    return {"count": c}


@api_router.post("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": nid, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@api_router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True}


# ============================================================================
# Attachments (Cloudinary signed upload)
# ============================================================================
@api_router.get("/cloudinary/signature")
async def cloudinary_signature(
    user: dict = Depends(get_current_user),
    folder: str = Query("taskflow/attachments"),
    resource_type: str = Query("auto", pattern="^(image|video|raw|auto)$"),
):
    if not folder.startswith("taskflow/"):
        raise HTTPException(400, "Invalid folder")
    timestamp = int(time.time())
    # Note: when resource_type=auto, Cloudinary still signs based on these params only
    params = {"timestamp": timestamp, "folder": folder}
    signature = cloudinary.utils.api_sign_request(params, CLOUDINARY_API_SECRET)
    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": CLOUDINARY_CLOUD_NAME,
        "api_key": CLOUDINARY_API_KEY,
        "folder": folder,
        "resource_type": resource_type,
    }


class AttachmentCreate(BaseModel):
    public_id: str
    secure_url: str
    resource_type: str = "image"
    format: Optional[str] = None
    bytes: Optional[int] = None
    original_filename: Optional[str] = None


@api_router.get("/tasks/{task_id}/attachments")
async def list_attachments(request: Request, task_id: str, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    items = await db.attachments.find({"task_id": task_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return items


@api_router.post("/tasks/{task_id}/attachments")
async def add_attachment(request: Request, task_id: str, payload: AttachmentCreate, user: dict = Depends(get_current_user)):
    t, ws = await get_accessible_task(task_id, user)
    doc = {
        "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "uploader_id": user["user_id"],
        "public_id": payload.public_id,
        "secure_url": payload.secure_url,
        "resource_type": payload.resource_type,
        "format": payload.format,
        "bytes": payload.bytes,
        "original_filename": payload.original_filename,
        "created_at": iso(now_utc()),
    }
    await db.attachments.insert_one(dict(doc))
    doc.pop("_id", None)
    await board_ws.broadcast(t["project_id"], {"type": "attachment.added", "task_id": task_id, "attachment": doc, "by": user["user_id"]})
    return doc


@api_router.delete("/attachments/{attachment_id}")
async def delete_attachment(request: Request, attachment_id: str, user: dict = Depends(get_current_user)):
    att = await db.attachments.find_one({"attachment_id": attachment_id}, {"_id": 0})
    if not att:
        raise HTTPException(404, "Attachment not found")
    # Verify task is accessible across user's workspaces
    t, ws = await get_accessible_task(att["task_id"], user)
    # Only uploader or workspace owner can delete
    if att["uploader_id"] != user["user_id"] and ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the uploader or workspace owner can delete attachments")
    # Best-effort Cloudinary delete
    try:
        cloudinary.uploader.destroy(att["public_id"], resource_type=att.get("resource_type", "image"), invalidate=True)
    except Exception:
        logger.exception("Cloudinary destroy failed (continuing)")
    await db.attachments.delete_one({"attachment_id": attachment_id})
    return {"ok": True}


# ============================================================================
# Health
# ============================================================================
@api_router.get("/")
async def root():
    return {"status": "ok", "service": "TaskFlow API"}


# ============================================================================
# Startup: indexes + demo seed
# ============================================================================
DEMO_AVATARS = {
    "sarah": "https://images.unsplash.com/photo-1657180881998-c8a03ef22695?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwzfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "david": "https://images.unsplash.com/photo-1758600432264-b8d2a0fd7d83?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHw0fHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "marcus": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwxfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "priya": "https://images.unsplash.com/photo-1609436132311-e4b0c9370469?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwyfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
}


async def seed_demo():
    """Idempotently seed demo user + workspace + project + tasks."""
    # 1. Demo user
    demo_email = DEMO_EMAIL.lower()
    demo_user = await db.users.find_one({"email": demo_email})
    if demo_user is None:
        demo_user_id = "user_demouser0001"
        demo_user = {
            "user_id": demo_user_id,
            "email": demo_email,
            "name": "Demo User",
            "picture": DEMO_AVATARS["marcus"],
            "role": "admin",
            "auth_provider": "jwt",
            "password_hash": hash_password(DEMO_PASSWORD),
            "created_at": iso(now_utc()),
        }
        await db.users.insert_one(dict(demo_user))
    else:
        # ensure password is the current DEMO_PASSWORD (idempotent reset)
        if not verify_password(DEMO_PASSWORD, demo_user.get("password_hash", "")):
            await db.users.update_one(
                {"email": demo_email},
                {"$set": {"password_hash": hash_password(DEMO_PASSWORD)}},
            )
    demo_user_id = demo_user["user_id"]

    # 2. Teammates (assignees)
    teammates = [
        {"user_id": "user_sarahj000001", "email": "sarah.j@taskflow.demo", "name": "Sarah J.", "picture": DEMO_AVATARS["sarah"]},
        {"user_id": "user_davidc000001", "email": "david.c@taskflow.demo", "name": "David Chen", "picture": DEMO_AVATARS["david"]},
        {"user_id": "user_priyak000001", "email": "priya.k@taskflow.demo", "name": "Priya K.", "picture": DEMO_AVATARS["priya"]},
    ]
    for tm in teammates:
        await db.users.update_one(
            {"user_id": tm["user_id"]},
            {"$setOnInsert": {
                **tm,
                "role": "member",
                "auth_provider": "demo",
                "password_hash": "",
                "created_at": iso(now_utc()),
            }},
            upsert=True,
        )

    # 3. Workspace
    ws = await db.workspaces.find_one({"owner_id": demo_user_id})
    if ws is None:
        ws = {
            "workspace_id": "ws_linearsync001",
            "name": "LinearSync",
            "slug": "linearsync",
            "owner_id": demo_user_id,
            "created_at": iso(now_utc()),
        }
        await db.workspaces.insert_one(dict(ws))
    ws_id = ws["workspace_id"]

    # 4. Project "Core Platform" (key CORE)
    proj = await db.projects.find_one({"workspace_id": ws_id, "key": "CORE"})
    if proj is None:
        proj = {
            "project_id": "proj_coreplatform",
            "workspace_id": ws_id,
            "name": "Core Platform",
            "key": "CORE",
            "description": "Engineering / Core Platform",
            "next_task_number": 257,  # tasks below go up to 256
            "created_at": iso(now_utc()),
        }
        await db.projects.insert_one(dict(proj))
    proj_id = proj["project_id"]

    # 5. Seed tasks (only if no tasks exist yet for this project)
    existing_count = await db.tasks.count_documents({"project_id": proj_id})
    if existing_count == 0:
        seed_tasks = [
            # In Progress (3)
            {"number": 254, "title": "Integrate Webhooks for CI/CD Pipeline", "status": "in_progress", "priority": "urgent", "tag": "FEATURE", "assignee_id": "user_davidc000001",
             "description": "We need to implement a robust webhook system that triggers our CI/CD pipelines whenever code is pushed or merged. This includes:\n\n- Setting up endpoint listeners for GitHub and GitLab\n- Implementing secret validation for security\n- Mapping payload data to our internal build triggers\n- Error handling and retry logic for failed deliveries"},
            {"number": 253, "title": "Server-side rendering investigation", "status": "in_progress", "priority": "medium", "tag": "RESEARCH", "assignee_id": "user_sarahj000001", "description": "Investigate SSR options."},
            {"number": 252, "title": "Migrate auth to httpOnly cookies", "status": "in_progress", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": "Move JWT tokens out of localStorage."},
            # To Do (5)
            {"number": 255, "title": "Refactor Global State Management for Auth", "status": "todo", "priority": "medium", "tag": "INFRASTRUCTURE", "assignee_id": "user_priyak000001", "description": "Reduce re-renders on auth context updates."},
            {"number": 250, "title": "Add keyboard shortcuts for board navigation", "status": "todo", "priority": "low", "tag": "UX", "assignee_id": "user_sarahj000001", "description": "j/k to navigate, e to edit."},
            {"number": 249, "title": "Implement bulk task assignment", "status": "todo", "priority": "medium", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": "Select multiple cards and assign in one action."},
            {"number": 248, "title": "Dark mode polish for empty states", "status": "todo", "priority": "low", "tag": "DESIGN", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 247, "title": "Audit logging for permission changes", "status": "todo", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": ""},
            # Backlog (12)
            {"number": 256, "title": "Optimize SVG Rendering Performance", "status": "backlog", "priority": "low", "tag": "PERFORMANCE", "assignee_id": "user_marcus" if False else "user_sarahj000001", "description": "Reduce icon paint cost on large boards."},
            {"number": 246, "title": "Investigate flicker on board switch", "status": "backlog", "priority": "low", "tag": "BUG", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 245, "title": "Document REST API in OpenAPI", "status": "backlog", "priority": "medium", "tag": "DOCS", "assignee_id": demo_user_id, "description": ""},
            {"number": 244, "title": "Add markdown support to descriptions", "status": "backlog", "priority": "medium", "tag": "FEATURE", "assignee_id": "user_sarahj000001", "description": ""},
            {"number": 243, "title": "Migrate from REST to GraphQL", "status": "backlog", "priority": "low", "tag": "INFRASTRUCTURE", "assignee_id": "user_davidc000001", "description": ""},
            {"number": 242, "title": "Slack notifications on assignment", "status": "backlog", "priority": "medium", "tag": "INTEGRATION", "assignee_id": demo_user_id, "description": ""},
            {"number": 241, "title": "Per-project custom fields", "status": "backlog", "priority": "low", "tag": "FEATURE", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 240, "title": "Re-architect search index", "status": "backlog", "priority": "high", "tag": "PERFORMANCE", "assignee_id": "user_davidc000001", "description": ""},
            {"number": 239, "title": "Mobile responsive board view", "status": "backlog", "priority": "medium", "tag": "UX", "assignee_id": "user_sarahj000001", "description": ""},
            {"number": 238, "title": "Recurring tasks support", "status": "backlog", "priority": "low", "tag": "FEATURE", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 237, "title": "Two-factor authentication", "status": "backlog", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": ""},
            {"number": 236, "title": "Export board as CSV", "status": "backlog", "priority": "low", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": ""},
            # Done (24) - we'll seed 5 visible ones
            {"number": 251, "title": "Fix z-index collisions in dropdowns", "status": "done", "priority": "medium", "tag": "UI FIX", "assignee_id": "user_sarahj000001", "description": ""},
            {"number": 235, "title": "Ship onboarding empty state", "status": "done", "priority": "medium", "tag": "UX", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 234, "title": "Add rate limit middleware", "status": "done", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": ""},
            {"number": 233, "title": "Initial Kanban board MVP", "status": "done", "priority": "urgent", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": ""},
            {"number": 232, "title": "Set up CI", "status": "done", "priority": "medium", "tag": "INFRA", "assignee_id": "user_sarahj000001", "description": ""},
        ]
        docs = []
        for t in seed_tasks:
            docs.append({
                "task_id": f"task_seed_{t['number']:04d}",
                "project_id": proj_id,
                "workspace_id": ws_id,
                "number": t["number"],
                "key": f"CORE-{t['number']}",
                "title": t["title"],
                "description": t["description"],
                "status": t["status"],
                "priority": t["priority"],
                "assignee_id": t["assignee_id"],
                "tag": t.get("tag"),
                "creator_id": demo_user_id,
                "created_at": iso(now_utc()),
                "updated_at": iso(now_utc()),
            })
        await db.tasks.insert_many(docs)

        # Seed one comment on CORE-254 (matches mockup)
        await db.comments.insert_one({
            "comment_id": "cmt_seed_001",
            "task_id": "task_seed_0254",
            "author_id": "user_sarahj000001",
            "body": "I've started the initial draft for the security validation middleware. Should be ready for review tomorrow.",
            "created_at": iso(now_utc() - timedelta(hours=2)),
        })


async def write_test_credentials():
    target = Path("/app/memory")
    target.mkdir(parents=True, exist_ok=True)
    creds = target / "test_credentials.md"
    creds.write_text(
        "# TaskFlow Test Credentials\n\n"
        "## JWT Demo Account\n"
        f"- Email: `{DEMO_EMAIL}`\n"
        f"- Password: `{DEMO_PASSWORD}`\n"
        "- Role: admin\n\n"
        "## Auth Endpoints\n"
        "- POST /api/auth/register\n"
        "- POST /api/auth/login\n"
        "- POST /api/auth/logout\n"
        "- GET  /api/auth/me\n"
        "- POST /api/auth/session  (Emergent Google session_id exchange)\n\n"
        "## Notes\n"
        "- Both JWT cookie (`access_token`) and Emergent session cookie (`session_token`) are accepted by `get_current_user`.\n"
        "- Demo workspace `LinearSync` and project `Core Platform` (key CORE) are auto-seeded.\n"
    )


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.workspaces.create_index("owner_id")
    await db.projects.create_index([("workspace_id", 1), ("key", 1)])
    await db.tasks.create_index([("project_id", 1), ("number", -1)])
    await db.tasks.create_index("task_id", unique=True)
    await db.comments.create_index([("task_id", 1), ("created_at", 1)])
    await db.user_sessions.create_index("session_token", unique=True)
    await db.invites.create_index("code", unique=True)
    await db.invites.create_index("workspace_id")
    await db.sprints.create_index([("project_id", 1), ("status", 1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.attachments.create_index("task_id")
    try:
        await seed_demo()
        await write_test_credentials()
        logger.info("Demo seed complete")
    except Exception:
        logger.exception("Seed error")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ============================================================================
# Mount
# ============================================================================
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
