from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal

PriorityT = Literal["low", "medium", "high", "urgent"]
StatusT = Literal["backlog", "todo", "in_progress", "done"]


# ── Auth ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionRequest(BaseModel):
    session_id: str


# ── Workspace ─────────────────────────────────────────────
class WorkspaceCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class WorkspaceSwitch(BaseModel):
    workspace_id: str


# ── Project ───────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str
    key: str = Field(min_length=2, max_length=8)
    description: Optional[str] = ""


# ── Task ──────────────────────────────────────────────────
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


# ── Comment ───────────────────────────────────────────────
class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


# ── Sprint ────────────────────────────────────────────────
class SprintCreate(BaseModel):
    name: str
    goal: Optional[str] = ""
    start_date: str
    end_date: str


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[Literal["planned", "active", "completed"]] = None


class SprintTaskBody(BaseModel):
    task_ids: List[str]


# ── Invite ────────────────────────────────────────────────
class InviteCreate(BaseModel):
    expires_in_days: int = 7


# ── Attachment ────────────────────────────────────────────
class AttachmentCreate(BaseModel):
    public_id: str
    secure_url: str
    resource_type: str = "image"
    format: Optional[str] = None
    bytes: Optional[int] = None
    original_filename: Optional[str] = None
