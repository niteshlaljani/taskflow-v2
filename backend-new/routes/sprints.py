import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends

from database import db
from helpers import now_utc, iso, get_current_user, get_accessible_project, get_accessible_sprint
from models import SprintCreate, SprintUpdate, SprintTaskBody

router = APIRouter(prefix="/api", tags=["sprints"])


@router.get("/projects/{project_id}/sprints")
async def list_sprints(project_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_project(project_id, user)
    return await db.sprints.find({"project_id": project_id}, {"_id": 0}).sort("start_date", -1).to_list(100)


@router.post("/projects/{project_id}/sprints")
async def create_sprint(project_id: str, payload: SprintCreate, user: dict = Depends(get_current_user)):
    _, ws = await get_accessible_project(project_id, user)
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


@router.patch("/sprints/{sprint_id}")
async def update_sprint(sprint_id: str, payload: SprintUpdate, user: dict = Depends(get_current_user)):
    await get_accessible_sprint(sprint_id, user)
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(400, "Nothing to update")
    if update.get("status") == "completed":
        update["completed_at"] = iso(now_utc())
    await db.sprints.update_one({"sprint_id": sprint_id}, {"$set": update})
    return await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})


@router.delete("/sprints/{sprint_id}")
async def delete_sprint(sprint_id: str, user: dict = Depends(get_current_user)):
    _, ws = await get_accessible_sprint(sprint_id, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only workspace owner can delete sprints")
    await db.sprints.delete_one({"sprint_id": sprint_id})
    return {"ok": True}


@router.post("/sprints/{sprint_id}/tasks")
async def add_sprint_tasks(sprint_id: str, payload: SprintTaskBody, user: dict = Depends(get_current_user)):
    await get_accessible_sprint(sprint_id, user)
    await db.sprints.update_one({"sprint_id": sprint_id}, {"$addToSet": {"task_ids": {"$each": payload.task_ids}}})
    return await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})


@router.delete("/sprints/{sprint_id}/tasks/{task_id}")
async def remove_sprint_task(sprint_id: str, task_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_sprint(sprint_id, user)
    await db.sprints.update_one({"sprint_id": sprint_id}, {"$pull": {"task_ids": task_id}})
    return await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})


@router.get("/sprints/{sprint_id}/burndown")
async def sprint_burndown(sprint_id: str, user: dict = Depends(get_current_user)):
    sprint, _ = await get_accessible_sprint(sprint_id, user)
    task_ids = sprint.get("task_ids") or []
    total = len(task_ids)
    start = datetime.fromisoformat(sprint["start_date"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(sprint["end_date"]).replace(tzinfo=timezone.utc)
    days = max(1, (end.date() - start.date()).days)
    today = now_utc()
    tasks = await db.tasks.find({"task_id": {"$in": task_ids}}, {"_id": 0}).to_list(2000)
    completion_dates = []
    for t in tasks:
        if t.get("status") == "done":
            try:
                cdt = datetime.fromisoformat(t["updated_at"])
                if cdt.tzinfo is None:
                    cdt = cdt.replace(tzinfo=timezone.utc)
                completion_dates.append(cdt)
            except Exception:
                continue
    series = []
    cur = start
    while cur.date() <= min(end, today).date():
        completed = sum(1 for d in completion_dates if d.date() <= cur.date())
        ideal = max(0, total - (total * ((cur.date() - start.date()).days) / days))
        series.append({"date": cur.date().isoformat(), "remaining": total - completed, "ideal": round(ideal, 2)})
        cur += timedelta(days=1)
    return {
        "sprint_id": sprint_id, "name": sprint["name"], "total": total,
        "completed": sum(1 for t in tasks if t.get("status") == "done"),
        "series": series,
    }


@router.get("/projects/{project_id}/velocity")
async def project_velocity(project_id: str, user: dict = Depends(get_current_user)):
    await get_accessible_project(project_id, user)
    sprints = await db.sprints.find({"project_id": project_id, "status": "completed"}, {"_id": 0}).sort("completed_at", 1).to_list(50)
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
