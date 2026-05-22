import uuid
from fastapi import APIRouter, HTTPException, Request, Depends

from database import db
from helpers import now_utc, iso, get_current_user, resolve_workspace, get_accessible_project
from models import ProjectCreate

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects")
async def list_projects(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    return await db.projects.find({"workspace_id": ws["workspace_id"]}, {"_id": 0}).to_list(200)


@router.post("/projects")
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


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    p, _ = await get_accessible_project(project_id, user)
    return p


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    proj, ws = await get_accessible_project(project_id, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the workspace owner can delete projects")
    task_ids = [t["task_id"] for t in await db.tasks.find({"project_id": project_id}, {"_id": 0, "task_id": 1}).to_list(5000)]
    if task_ids:
        await db.comments.delete_many({"task_id": {"$in": task_ids}})
        await db.attachments.delete_many({"task_id": {"$in": task_ids}})
    await db.tasks.delete_many({"project_id": project_id})
    await db.sprints.delete_many({"project_id": project_id})
    await db.projects.delete_one({"project_id": project_id})
    return {"ok": True}
