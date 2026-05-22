from fastapi import APIRouter, Depends
from database import db
from helpers import get_current_user

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/notifications/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    c = await db.notifications.count_documents({"user_id": user["user_id"], "read": False})
    return {"count": c}


@router.post("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": nid, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True}
