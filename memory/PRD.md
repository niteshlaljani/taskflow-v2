# TaskFlow — Product Requirements Document

## Original Problem Statement
Build TaskFlow, a Linear-style project management platform for engineering teams.
Tagline: "Manage projects with ruthless efficiency. Zero fluff, absolute control."

## Architecture
- **Frontend**: React 19 + React Router 7 + Tailwind + framer-motion + lucide-react + @dnd-kit + recharts
- **Backend**: FastAPI + motor (MongoDB async) + WebSockets + Cloudinary
- **Database**: MongoDB (users, workspaces, projects, tasks, comments, user_sessions, invites, sprints, notifications, attachments)
- **Auth**: JWT (httpOnly `access_token` cookie) + Emergent-managed Google OAuth (`session_token` cookie). WS uses short-lived JWT via `?token=` query param.
- **File storage**: Cloudinary (signed direct-upload, backend stores metadata)

## Implemented (2026-01)
### Sprint 1 (Auth + Foundation)
- Marketing landing page, JWT auth, Google OAuth, demo seed (LinearSync workspace, Core Platform / CORE project, 25 tasks, 1 comment).

### Sprint 2 (Core PM)
- Project CRUD, Task CRUD with auto-incrementing keys, Comments, Kanban board, NewIssueModal, TaskDetailPanel, AppIndex (auto-create Inbox for new users), dynamic workspace name.

### Sprint 3 (Drag, Real-time, Team)
- Drag-and-drop Kanban columns (@dnd-kit) with optimistic updates + rollback
- WebSocket real-time sync for task & comment events (auto-reconnect, JWT via `?token=`)
- Live presence avatars in the board header
- Team invite links (`/join/<code>`, 7-day expiry, copy/revoke)
- My Issues, Projects list, Settings, Workspace member model

### Sprint 4 (Sprints, Notifications, Attachments, Multi-workspace)
- **Sprints page** per project: create / start / complete / delete; add or remove tasks; burn-down (ideal vs actual remaining) chart; velocity bar chart and average across completed sprints
- **In-app notifications** dropdown in topbar with unread badge, mark-one / mark-all read, real-time refresh on `notification.created` WS events; events: `assigned` (assignee change) and `comment` (comment on a task you're assigned to)
- **File attachments** in TaskDetailPanel via Cloudinary signed direct-upload (signature minted by backend), metadata stored in `attachments` collection; uploader-or-owner delete with Cloudinary destroy
- **Multi-workspace switcher** in the sidebar (auto-disabled when user only has 1 workspace); `/api/workspaces/switch` sets `active_workspace` cookie and frontend sends `X-Workspace-Id` header on every request via axios interceptor
- **Simple search** in the topbar — emits a `tf:search` window event the Board listens to for client-side substring filtering across key / title / description / tag

### Tech Debt Addressed
- **CORS hardened**: explicit origins via env + regex for `*.preview.emergentagent.com`, credentials enabled
- **Cascade delete on project delete**: removes tasks, comments, attachments, sprints in a single op

## Testing
- Backend: 53/53 pytest passing (auth, projects, tasks, comments, invites, WebSocket, sprints, notifications, attachments, CORS, cascade)
- Frontend: 4 testing-subagent iterations, all flows verified

## Backlog
### Tech Debt — DEFERRED
- Split `server.py` (now ~1500 lines) into `/app/backend/routers/{auth,workspaces,projects,tasks,comments,invites,sprints,notifications,attachments,ws}.py` — see context note below.
- Cloudinary `destroy` on project delete cascade (currently only single-attachment delete destroys remote object)
- Store explicit `done_at` on tasks (burn-down currently uses `updated_at` as completion proxy)
- Stricter `X-Workspace-Id` policy (currently falls back; alt: 403)
- Recharts initial-render width(-1)/height(-1) warning polish (already mitigated with `minHeight/minWidth=0`)

### Product
- Email notifications (Resend / SendGrid) if user later wants out-of-app pings
- @mention autocomplete in comments
- Advanced backend search (full-text on tasks)
- Sprint goal completion checklist, story points, carry-over to next sprint

## Context: why server.py split is deferred
1500 lines is well-organized with clear `# =====` section banners (Auth, Workspaces, Projects, Tasks, Comments, WebSocket, Invites, Sprints, Notifications, Attachments, Health). All endpoints share `db`, `board_ws`, `_notify`, `get_current_user`, `resolve_workspace`, `_authenticate_ws` — splitting requires routing these as module-level state or dependency injection through a shared `app.state`. A safe extraction would take ~30–45 min plus a full regression. Marked P0 for the next refactor pass; functional surface is fully covered.

## 2026-01 Hotfix (post-Sprint 4)

### Fixed
- **Cross-workspace deep linking** — when a user belonged to 2+ workspaces (e.g. their own auto-Inbox + a joined LinearSync via invite), notifications and direct task links resolved to the wrong workspace and showed "Project not found". Introduced `get_accessible_project`, `get_accessible_task`, `get_accessible_sprint` helpers that look up the resource by id and grant access if the user owns OR is a member of the resource's own workspace, regardless of the active workspace cookie.
- **`/api/my-issues` cross-workspace** — now returns assigned tasks from every workspace the user belongs to (was scoped to the active workspace only).
- **Accept invite sets active workspace** — `POST /api/invites/{code}/accept` now sets the `active_workspace` cookie to the joined workspace so subsequent requests default to it. Frontend also writes it to `localStorage.tf_active_workspace`.
- **Views page** — was a no-op redirect, now a real page (`/app/views`) with saved-view filters: All issues, Urgent, Active (in-progress), Recently shipped — aggregated across all the user's projects with click-through to the right board.

### Test status
- 59/59 pytest green (53 prior + 6 new `test_cross_workspace.py` cases)
- Frontend bug-fix flow verified end-to-end with two browser contexts (demo + dummy invitee).
