import uuid
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends

from database import db
from helpers import now_utc, iso, get_current_user, resolve_workspace, get_user_workspace
from models import WorkspaceSwitch, InviteCreate

router = APIRouter(prefix="/api", tags=["workspaces"])


@router.get("/workspaces/current")
async def current_workspace(request: Request, user: dict = Depends(get_current_user)):
    return await resolve_workspace(request, user)


@router.get("/workspaces")
async def list_my_workspaces(user: dict = Depends(get_current_user)):
    items = await db.workspaces.find(
        {"$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]}, {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    return items


@router.post("/workspaces/switch")
async def switch_workspace(payload: WorkspaceSwitch, response: Response, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one(
        {"workspace_id": payload.workspace_id, "$or": [{"owner_id": user["user_id"]}, {"member_ids": user["user_id"]}]},
        {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Workspace not found or no access")
    response.set_cookie(
        key="active_workspace", value=payload.workspace_id,
        httponly=False, secure=True, samesite="none",
        max_age=60 * 60 * 24 * 365, path="/",
    )
    return ws


@router.get("/workspaces/members")
async def list_members(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    member_ids = set([ws["owner_id"]] + (ws.get("member_ids") or []))
    assignees = await db.tasks.distinct("assignee_id", {"workspace_id": ws["workspace_id"]})
    for a in assignees:
        if a:
            member_ids.add(a)
    members = await db.users.find(
        {"user_id": {"$in": list(member_ids)}}, {"_id": 0, "password_hash": 0}
    ).to_list(200)
    return members


# ── Invites ───────────────────────────────────────────────
@router.post("/workspaces/invites")
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


@router.get("/workspaces/invites")
async def list_invites(request: Request, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    if ws["owner_id"] != user["user_id"]:
        return []
    return await db.invites.find({"workspace_id": ws["workspace_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.delete("/workspaces/invites/{invite_id}")
async def revoke_invite(request: Request, invite_id: str, user: dict = Depends(get_current_user)):
    ws = await resolve_workspace(request, user)
    if ws["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the workspace owner can revoke invites")
    result = await db.invites.delete_one({"invite_id": invite_id, "workspace_id": ws["workspace_id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Invite not found")
    return {"ok": True}


@router.get("/invites/{code}")
async def get_invite(code: str):
    from datetime import timezone
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invite not found")
    expires_at = invite.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = __import__('datetime').datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    expired = bool(expires_at and expires_at < now_utc())
    ws = await db.workspaces.find_one({"workspace_id": invite["workspace_id"]}, {"_id": 0})
    owner = await db.users.find_one({"user_id": invite["created_by"]}, {"_id": 0, "password_hash": 0})
    return {
        "code": invite["code"],
        "workspace_name": ws["name"] if ws else "Unknown",
        "inviter_name": owner["name"] if owner else "A teammate",
        "expired": expired,
    }


@router.post("/invites/{code}/accept")
async def accept_invite(code: str, response: Response, user: dict = Depends(get_current_user)):
    from datetime import timezone
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invite not found")
    expires_at = invite.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = __import__('datetime').datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < now_utc():
        raise HTTPException(400, "Invite expired")

    ws = await db.workspaces.find_one({"workspace_id": invite["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(404, "Workspace no longer exists")

    def _set_active(ws_id):
        response.set_cookie(
            key="active_workspace", value=ws_id,
            httponly=False, secure=True, samesite="none",
            max_age=60 * 60 * 24 * 365, path="/",
        )

    if user["user_id"] in (ws.get("member_ids") or []) or ws["owner_id"] == user["user_id"]:
        _set_active(ws["workspace_id"])
        return {"ok": True, "workspace_id": ws["workspace_id"], "already_member": True}

    await db.workspaces.update_one({"workspace_id": ws["workspace_id"]}, {"$addToSet": {"member_ids": user["user_id"]}})
    own_ws = await db.workspaces.find_one(
        {"owner_id": user["user_id"], "workspace_id": {"$ne": ws["workspace_id"]}}, {"_id": 0}
    )
    if own_ws and await db.projects.count_documents({"workspace_id": own_ws["workspace_id"]}) == 0:
        await db.workspaces.delete_one({"workspace_id": own_ws["workspace_id"]})

    await db.invites.update_one({"code": code}, {"$addToSet": {"used_by": user["user_id"]}})
    _set_active(ws["workspace_id"])
    return {"ok": True, "workspace_id": ws["workspace_id"], "already_member": False}
