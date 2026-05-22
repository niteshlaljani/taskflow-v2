import logging
import uuid
import cloudinary
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import (
    CORS_ORIGINS, DEMO_EMAIL, DEMO_PASSWORD,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)
from database import db, client
from helpers import now_utc, iso, hash_password, verify_password
from websocket_manager import board_ws, authenticate_ws

# ── Routes ────────────────────────────────────────────────
from routes.auth import router as auth_router
from routes.workspaces import router as workspace_router
from routes.projects import router as project_router
from routes.tasks import router as task_router
from routes.sprints import router as sprint_router
from routes.notifications import router as notification_router
from routes.cloudinary import router as cloudinary_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

app = FastAPI(title="TaskFlow API")

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(project_router)
app.include_router(task_router)
app.include_router(sprint_router)
app.include_router(notification_router)
app.include_router(cloudinary_router)


# ── Health ────────────────────────────────────────────────
@app.get("/api/")
async def root():
    return {"status": "ok", "service": "TaskFlow API"}


# ── WebSocket ─────────────────────────────────────────────
@app.websocket("/api/ws/board/{project_id}")
async def board_websocket(websocket: WebSocket, project_id: str):
    user = await authenticate_ws(websocket)
    if not user:
        await websocket.close(code=4401)
        return
    user_summary = {"user_id": user["user_id"], "name": user.get("name"), "picture": user.get("picture")}
    await board_ws.connect(project_id, websocket, user_summary)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await board_ws.disconnect(project_id, websocket)


# ── Demo Seed Avatars ─────────────────────────────────────
DEMO_AVATARS = {
    "sarah": "https://images.unsplash.com/photo-1657180881998-c8a03ef22695?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwzfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "david": "https://images.unsplash.com/photo-1758600432264-b8d2a0fd7d83?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHw0fHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "marcus": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwxfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
    "priya": "https://images.unsplash.com/photo-1609436132311-e4b0c9370469?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwyfHxwcm9mZXNzaW9uYWwlMjBwb3J0cmFpdCUyMGZhY2UlMjBuZXV0cmFsJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzkxODM2ODh8MA&ixlib=rb-4.1.0&q=85",
}


async def seed_demo():
    demo_email = DEMO_EMAIL.lower()
    demo_user = await db.users.find_one({"email": demo_email})
    if demo_user is None:
        demo_user_id = "user_demouser0001"
        demo_user = {
            "user_id": demo_user_id, "email": demo_email, "name": "Demo User",
            "picture": DEMO_AVATARS["marcus"], "role": "admin", "auth_provider": "jwt",
            "password_hash": hash_password(DEMO_PASSWORD), "created_at": iso(now_utc()),
        }
        await db.users.insert_one(dict(demo_user))
    else:
        if not verify_password(DEMO_PASSWORD, demo_user.get("password_hash", "")):
            await db.users.update_one({"email": demo_email}, {"$set": {"password_hash": hash_password(DEMO_PASSWORD)}})
    demo_user_id = demo_user["user_id"]

    teammates = [
        {"user_id": "user_sarahj000001", "email": "sarah.j@taskflow.demo", "name": "Sarah J.", "picture": DEMO_AVATARS["sarah"]},
        {"user_id": "user_davidc000001", "email": "david.c@taskflow.demo", "name": "David Chen", "picture": DEMO_AVATARS["david"]},
        {"user_id": "user_priyak000001", "email": "priya.k@taskflow.demo", "name": "Priya K.", "picture": DEMO_AVATARS["priya"]},
    ]
    for tm in teammates:
        await db.users.update_one(
            {"user_id": tm["user_id"]},
            {"$setOnInsert": {**tm, "role": "member", "auth_provider": "demo", "password_hash": "", "created_at": iso(now_utc())}},
            upsert=True,
        )

    ws = await db.workspaces.find_one({"owner_id": demo_user_id})
    if ws is None:
        ws = {
            "workspace_id": "ws_linearsync001", "name": "LinearSync", "slug": "linearsync",
            "owner_id": demo_user_id, "created_at": iso(now_utc()),
        }
        await db.workspaces.insert_one(dict(ws))
    ws_id = ws["workspace_id"]

    proj = await db.projects.find_one({"workspace_id": ws_id, "key": "CORE"})
    if proj is None:
        proj = {
            "project_id": "proj_coreplatform", "workspace_id": ws_id, "name": "Core Platform",
            "key": "CORE", "description": "Engineering / Core Platform",
            "next_task_number": 257, "created_at": iso(now_utc()),
        }
        await db.projects.insert_one(dict(proj))
    proj_id = proj["project_id"]

    if await db.tasks.count_documents({"project_id": proj_id}) == 0:
        seed_tasks = [
            {"number": 254, "title": "Integrate Webhooks for CI/CD Pipeline", "status": "in_progress", "priority": "urgent", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": "Implement webhook system for CI/CD pipelines."},
            {"number": 253, "title": "Server-side rendering investigation", "status": "in_progress", "priority": "medium", "tag": "RESEARCH", "assignee_id": "user_sarahj000001", "description": "Investigate SSR options."},
            {"number": 252, "title": "Migrate auth to httpOnly cookies", "status": "in_progress", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": "Move JWT tokens out of localStorage."},
            {"number": 255, "title": "Refactor Global State Management for Auth", "status": "todo", "priority": "medium", "tag": "INFRASTRUCTURE", "assignee_id": "user_priyak000001", "description": "Reduce re-renders on auth context updates."},
            {"number": 250, "title": "Add keyboard shortcuts for board navigation", "status": "todo", "priority": "low", "tag": "UX", "assignee_id": "user_sarahj000001", "description": "j/k to navigate, e to edit."},
            {"number": 249, "title": "Implement bulk task assignment", "status": "todo", "priority": "medium", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": "Select multiple cards and assign in one action."},
            {"number": 248, "title": "Dark mode polish for empty states", "status": "todo", "priority": "low", "tag": "DESIGN", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 247, "title": "Audit logging for permission changes", "status": "todo", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": ""},
            {"number": 256, "title": "Optimize SVG Rendering Performance", "status": "backlog", "priority": "low", "tag": "PERFORMANCE", "assignee_id": "user_sarahj000001", "description": ""},
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
            {"number": 251, "title": "Fix z-index collisions in dropdowns", "status": "done", "priority": "medium", "tag": "UI FIX", "assignee_id": "user_sarahj000001", "description": ""},
            {"number": 235, "title": "Ship onboarding empty state", "status": "done", "priority": "medium", "tag": "UX", "assignee_id": "user_priyak000001", "description": ""},
            {"number": 234, "title": "Add rate limit middleware", "status": "done", "priority": "high", "tag": "SECURITY", "assignee_id": demo_user_id, "description": ""},
            {"number": 233, "title": "Initial Kanban board MVP", "status": "done", "priority": "urgent", "tag": "FEATURE", "assignee_id": "user_davidc000001", "description": ""},
            {"number": 232, "title": "Set up CI", "status": "done", "priority": "medium", "tag": "INFRA", "assignee_id": "user_sarahj000001", "description": ""},
        ]
        docs = [{
            "task_id": f"task_seed_{t['number']:04d}", "project_id": proj_id, "workspace_id": ws_id,
            "number": t["number"], "key": f"CORE-{t['number']}", "title": t["title"],
            "description": t["description"], "status": t["status"], "priority": t["priority"],
            "assignee_id": t["assignee_id"], "tag": t.get("tag"), "creator_id": demo_user_id,
            "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
        } for t in seed_tasks]
        await db.tasks.insert_many(docs)
        await db.comments.insert_one({
            "comment_id": "cmt_seed_001", "task_id": "task_seed_0254",
            "author_id": "user_sarahj000001",
            "body": "I've started the initial draft for the security validation middleware. Should be ready for review tomorrow.",
            "created_at": iso(now_utc()),
        })


# ── Startup / Shutdown ────────────────────────────────────
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
        logger.info("Demo seed complete")
    except Exception:
        logger.exception("Seed error")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
