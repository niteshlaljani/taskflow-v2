# TaskFlow — Product Requirements Document

## Original Problem Statement
Build TaskFlow, a Linear-style project management platform for engineering teams.
Tagline: "Manage projects with ruthless efficiency. Zero fluff, absolute control."
Sprint 1+2 MVP scope: Auth (JWT + Google), workspaces/projects, task CRUD with assignees/priorities/status, Kanban board view, plus marketing landing page. Demo workspace pre-seeded.

## Architecture
- **Frontend**: React 19 + React Router 7 + Tailwind + framer-motion + lucide-react
- **Backend**: FastAPI + motor (MongoDB async)
- **Database**: MongoDB (users, workspaces, projects, tasks, comments, user_sessions, login_attempts)
- **Auth**: Dual — JWT (httpOnly access_token cookie) AND Emergent-managed Google OAuth (httpOnly session_token cookie). `get_current_user` accepts either.

## User Personas
1. **Engineering Team Lead** (primary) — needs sprint planning, status tracking, team coordination.
2. **Developer / IC** — needs zero-friction task creation and updates.
3. **Product Manager** — needs visibility across boards.

## Core Requirements (static)
- Marketing landing page with hero, feature grid, CTA, footer
- Email/password registration + login (JWT)
- "Continue with Google" via Emergent Auth
- Personal workspace auto-created per user
- Projects with custom keys (e.g. CORE) and auto-incrementing task numbers (CORE-256)
- Tasks with title, description, status (backlog/todo/in_progress/done), priority (low/medium/high/urgent), assignee, tag
- Kanban board grouped by status with dot+count headers
- Slide-over task detail with inline-editable title/description, status/priority/assignee selectors, comment activity
- Issue creation modal (title, description, status/priority/assignee, tag)

## Implemented (2026-01)
- Sprint 1: Auth foundation (JWT register/login/me/logout + Emergent Google session exchange), MongoDB schemas + indexes, demo seed (demo@taskflow.com / demo1234, LinearSync workspace, Core Platform project with 25 tasks across 4 statuses + 1 seed comment)
- Sprint 2: Task CRUD (create/list/update/delete) with auto-incrementing keys; comments CRUD; workspaces & projects endpoints; member listing
- Frontend: Landing, Login, Register, AuthCallback (Emergent), AppShell (dark sidebar + light canvas, dynamic workspace name), Board (Kanban 4 columns), NewIssueModal, TaskDetailPanel (inline edits + comments + status/priority/assignee re-assignment), AppIndex (auto-redirect to first project, auto-creates "Inbox" project for new users)
- Testing: backend 19/19 pytest passing; frontend 100% (validated by testing subagent across 2 iterations)

## Prioritized Backlog
### P0 (Sprint 1+2 — DONE)
- All listed above.

### P1 (Sprint 3 — deferred)
- Drag-and-drop between Kanban columns (react-dnd or @dnd-kit)
- Real-time WebSocket sync across users
- Live presence indicators
- Project/team member invitations + role assignment UI

### P2 (Sprint 4 — deferred)
- Sprint cycles + burn-down charts
- Team velocity tracking
- Time-to-completion analytics
- Saved views / filters / search backend
- Email notifications (SendGrid/Resend)
- File attachments to tasks

## Known Trade-offs / Tech Debt
- `server.py` ~775 lines — could be split into routers/.
- CORS uses `*` with credentials — needs explicit origins for production.
- PillEditor lacks Escape-key close handler (a11y nit).
