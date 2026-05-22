import jwt
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from config import JWT_SECRET, JWT_ALGORITHM
from database import db


class BoardConnectionManager:
    def __init__(self):
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
        seen = {}
        for c in room:
            u = c["user"]
            seen[u["user_id"]] = u
        await self.broadcast(project_id, {"type": "presence", "users": list(seen.values())})


board_ws = BoardConnectionManager()


async def authenticate_ws(websocket: WebSocket):
    now = datetime.now(timezone.utc)

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
            if expires_at and expires_at > now:
                u = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
                if u:
                    return u

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
