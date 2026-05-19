# TaskFlow — Product Requirements Document

## Original Problem Statement
Build TaskFlow, a Linear-style project management platform for engineering teams.
Tagline: "Manage projects with ruthless efficiency. Zero fluff, absolute control."

## Architecture
- **Frontend**: React 19 + React Router 7 + Tailwind + framer-motion + lucide-react + @dnd-kit
- **Backend**: FastAPI + motor (MongoDB async) + WebSockets
- **Database**: MongoDB (users, workspaces, projects, tasks, comments, user_sessions, invites)
- **Auth**: JWT (httpOnly `access_token` cookie) + Emergent-managed Google OAuth (`session_token` cookie). WS uses short-lived JWT via `?token=` query param.

## User Personas
1. Engineering Team Lead (primary) — sprint planning, status tracking, team coordination
2. Developer / IC — frictionless task creation and updates
3. Product Manager — cross-board visibility

## Implemented (2026-01)
### Sprint 1 (Auth + Foundation)
- Marketing landing page (dark, "ruthless efficiency" hero, feature grid, CTA, footer)
- JWT register/login/me/logout + bcrypt password hashing
- Emergent Google OAuth session exchange
- Auto-created personal workspace per user
- Demo seed: `demo@taskflow.com / demo1234`, LinearSync workspace, Core Platform project (key CORE), 25 tasks across 4 statuses, 1 seed comment

### Sprint 2 (Core PM)
- Project CRUD with auto-incrementing task keys (CORE-256 etc.)
- Task CRUD with title, description, status (backlog/todo/in_progress/done), priority (low/medium/high/urgent), assignee, tag
- Comments on tasks
- Kanban board (4 status columns, dot+count headers, density-optimized cards)
- New Issue modal
- Task detail slide-over with inline-editable title/description and selectors
- Auto-redirect to first project for new users (auto-creates an "Inbox" project)
- Dynamic workspace name in sidebar and topbar

### Sprint 3 (Drag, Real-time, Team)
- **Drag-and-drop** between Kanban columns (@dnd-kit) with optimistic updates and rollback on error
- **WebSocket real-time sync** — task.created/updated/deleted and comment.created broadcast to all viewers; auto-reconnect on close
- **Live presence indicators** — "● LIVE" pulse + green-ringed avatar stack of teammates viewing the same board
- **Team invite links** — owner-generated `/join/<code>` URLs (7-day expiry, revocable)
- **My Issues page** — list of all tasks assigned to me across the workspace
- **Projects list page** — grid view with create + delete (owner only)
- **Settings page** — workspace info, members list, invite link manager
- **Workspace member model** — `workspace.member_ids` joined via invite

## Testing
- Backend: 30/30 pytest passing (auth, projects, tasks, comments, invites, WebSocket presence + broadcasts)
- Frontend: 3 testing-subagent iterations; drag-and-drop, real-time WS, presence, invite flow all verified end-to-end

## Prioritized Backlog
### Sprint 4 (P2 — deferred)
- Sprint cycles + burn-down + velocity (PRD Sprint 4 features)
- Advanced filters/search backend
- Email notifications (SendGrid/Resend)
- File attachments to tasks
- Workspace switcher (multi-workspace per user)

### Tech debt
- Split server.py (~1100 lines) into routers/
- Tighten CORS for production (no `*` with credentials)
- Cascade-delete comments on project delete
