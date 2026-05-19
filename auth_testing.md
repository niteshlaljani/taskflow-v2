# TaskFlow Auth Testing Playbook

Two auth flows coexist on the same User model:
1. **JWT email/password** (cookie `access_token`)
2. **Emergent Google Auth** (cookie `session_token`)

The `/api/auth/me` endpoint checks BOTH cookies (jwt access_token first, then session_token).

## Demo Credentials (JWT)
- Email: `demo@taskflow.com`
- Password: `demo1234`

## JWT Endpoints
- POST `/api/auth/register` — {email, password, name}
- POST `/api/auth/login` — {email, password}
- POST `/api/auth/logout`
- GET `/api/auth/me`

## Google Auth Endpoints
- POST `/api/auth/session` — body {session_id} from URL fragment; sets `session_token` cookie

## Quick Tests
```bash
# Login JWT
curl -c c.txt -X POST "$BACKEND/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"demo@taskflow.com","password":"demo1234"}'

curl -b c.txt "$BACKEND/api/auth/me"
```

## MongoDB Check
```
mongosh test_database
db.users.findOne({email:"demo@taskflow.com"})
db.workspaces.find()
db.projects.find()
db.tasks.countDocuments()
```
