import uuid
import jwt
import httpx
import logging
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends

from database import db
from helpers import (
    now_utc, iso, hash_password, verify_password,
    create_access_token, set_jwt_cookie, set_session_cookie,
    clear_auth_cookies, get_current_user,
)
from models import RegisterRequest, LoginRequest, SessionRequest
from config import JWT_SECRET, JWT_ALGORITHM, DEMO_EMAIL, DEMO_PASSWORD

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")

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


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(401, "Invalid credentials")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(user["user_id"], email)
    set_jwt_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"user": user, "access_token": token}


@router.post("/logout")
async def logout(request: Request, response: Response):
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/ws-token")
async def ws_token(user: dict = Depends(get_current_user)):
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


@router.post("/session")
async def auth_session(payload: SessionRequest, response: Response):
    async with httpx.AsyncClient(timeout=15) as cli:
        try:
            r = await cli.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": payload.session_id},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Auth session exchange failed: {e}")

    email = (data.get("email") or "").lower().strip()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture")
    session_token = data["session_token"]

    if not email:
        raise HTTPException(400, "No email returned from auth provider")

    existing = await db.users.find_one({"email": email})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": name, "picture": picture}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "role": "member", "auth_provider": "google", "created_at": iso(now_utc()),
        })

    expires_at = now_utc() + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {"session_token": session_token, "user_id": user_id, "expires_at": expires_at, "created_at": now_utc()}},
        upsert=True,
    )
    set_session_cookie(response, session_token)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user}
