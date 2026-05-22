import uuid
from fastapi import APIRouter, HTTPException, Request, Depends

from database import db
from helpers import now_utc, iso, get_current_user, get_accessible_project, get_accessible_task, notify
from models import TaskCreate, TaskUpdate, CommentCreate
from websocket_manager import board_ws

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_project(project_id, user)
    return await db.tasks.find({"project_id": project_id}, {"_id": 0}).sort("number", -1).to_list(500)


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, payload: TaskCreate, user: dict = Depends(get_current_user)):
    _proj, ws = await get_accessible_project(project_id, user)
    proj = await db.projects.find_one_and_update({"project_id": project_id}, {"$inc": {"next_task_number": 1}})
    if not proj:
        raise HTTPException(404, "Project not found")
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
        await notify(
            user_id=task["assignee_id"], by_user_id=user["user_id"],
            ntype="assigned", task_id=task["task_id"], project_id=project_id,
            message=f"{user.get('name','Someone')} assigned you {task['key']}: {task['title']}",
        )
    return task


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    t, _ = await get_accessible_task(task_id, user)
    return t


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdate, user: dict = Depends(get_current_user)):
    await get_accessible_task(task_id, user)
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k in ["assignee_id", "tag", "description"]}
    if not update:
        raise HTTPException(400, "Nothing to update")
    update["updated_at"] = iso(now_utc())
    result = await db.tasks.update_one({"task_id": task_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Task not found")
    t = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
    await board_ws.broadcast(t["project_id"], {"type": "task.updated", "task": t, "by": user["user_id"]})
    if "assignee_id" in update and update["assignee_id"] and update["assignee_id"] != user["user_id"]:
        await notify(
            user_id=update["assignee_id"], by_user_id=user["user_id"],
            ntype="assigned", task_id=task_id, project_id=t["project_id"],
            message=f"{user.get('name','Someone')} assigned you {t['key']}: {t['title']}",
        )
    return t


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    t, _ = await get_accessible_task(task_id, user)
    await db.tasks.delete_one({"task_id": task_id})
    await db.comments.delete_many({"task_id": task_id})
    await board_ws.broadcast(t["project_id"], {"type": "task.deleted", "task_id": task_id, "by": user["user_id"]})
    return {"ok": True}


# ── My Issues ─────────────────────────────────────────────
@router.get("/my-issues")
async def my_issues(user: dict = Depends(get_current_user)):
    workspaces = await db.workspaces.find(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0, "workspace_id": 1},
    ).to_list(50)
    ws_ids = [w["workspace_id"] for w in workspaces]
    return await db.tasks.find(
        {"workspace_id": {"$in": ws_ids}, "assignee_id": user["user_id"]}, {"_id": 0}
    ).sort("number", -1).to_list(500)


# ── Comments ──────────────────────────────────────────────
@router.get("/tasks/{task_id}/comments")
async def list_comments(task_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_task(task_id, user)
    return await db.comments.find({"task_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(500)


@router.post("/tasks/{task_id}/comments")
async def add_comment(task_id: str, payload: CommentCreate, user: dict = Depends(get_current_user)):
    t, _ = await get_accessible_task(task_id, user)
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
    if t.get("assignee_id"):
        await notify(
            user_id=t["assignee_id"], by_user_id=user["user_id"],
            ntype="comment", task_id=task_id, comment_id=c["comment_id"],
            project_id=t["project_id"],
            message=f"{user.get('name','Someone')} commented on {t['key']}",
        )
    return c


# ── Attachments ───────────────────────────────────────────
@router.get("/tasks/{task_id}/attachments")
async def list_attachments(task_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_task(task_id, user)
    return await db.attachments.find({"task_id": task_id}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.post("/tasks/{task_id}/attachments")
async def add_attachment(task_id: str, payload, user: dict = Depends(get_current_user)):
    t, _ = await get_accessible_task(task_id, user)
    doc = {
        "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "uploader_id": user["user_id"],
        **payload.model_dump(),
        "created_at": iso(now_utc()),
    }
    await db.attachments.insert_one(dict(doc))
    doc.pop("_id", None)
    await board_ws.broadcast(t["project_id"], {"type": "attachment.added", "task_id": task_id, "attachment": doc, "by": user["user_id"]})
    return doc


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str, user: dict = Depends(get_current_user)):
    import cloudinary.uploader
    att = await db.attachments.find_one({"attachment_id": attachment_id}, {"_id": 0})
    if not att:
        raise HTTPException(404, "Attachment not found")
    t, ws = await get_accessible_task(att["task_id"], user)
    if att["uploader_id"] != user["user_id"] and ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the uploader or workspace owner can delete attachments")
    try:
        cloudinary.uploader.destroy(att["public_id"], resource_type=att.get("resource_type", "image"), invalidate=True)
    except Exception:
        pass
    await db.attachments.delete_one({"attachment_id": attachment_id})
    return {"ok": True}
