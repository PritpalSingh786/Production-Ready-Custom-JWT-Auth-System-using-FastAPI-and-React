# AuthFlow — Full-Stack Authentication System

A practical full-stack authentication project built with **React + Vite**, **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, **JWT**, **CSRF protection**, and **Socket.IO**.

This README explains the project in simple language: what each technology does, why it is used, how the frontend and backend communicate, where data is stored, how background email jobs run, how token refresh works, how CSRF protection is applied, and how to test the APIs with the included Postman collection.

---

## 1. Project at a glance

The application provides:

- User registration and email verification.
- Login with a short-lived JWT access token.
- Refresh-token based session continuation.
- Refresh-token rotation and server-side session tracking in Redis.
- Secure web refresh/logout requests with CSRF protection.
- Protected APIs.
- Forgot-password and password-reset flows.
- A separate secure password-change flow for suspicious/new-login alerts.
- Logout from all devices after password changes.
- Real-time remote logout notifications through Socket.IO.
- Background email delivery through Celery.
- API rate limiting on registration and login.
- A ready-to-import Postman collection.

### Technology and its job

| Technology | What it does here | Why it is used |
|---|---|---|
| React | Builds the browser interface | Reusable components and a responsive UI |
| Vite | Runs/builds the frontend | Fast development server and production build |
| Redux Toolkit | Keeps authentication state | One shared place for access token, user and session status |
| Axios | Sends API requests | Central request/response interceptors for bearer tokens and refresh |
| FastAPI | Provides backend APIs | Validation, dependencies and fast Python API development |
| PostgreSQL | Stores permanent application data | Users, devices, account status and timestamps |
| SQLAlchemy | Talks to PostgreSQL | Python ORM for database queries and models |
| Alembic | Manages schema migrations | Tracks database structure changes |
| Redis | Stores short-lived/session data | Fast token lookup, revocation, expiry and Celery broker |
| JWT | Represents signed access/refresh credentials | Stateless token format with expiry and claims |
| bcrypt | Hashes passwords | The original password is not stored as plain text |
| Celery | Runs background jobs | Email sending and logout notifications do not block API responses |
| Socket.IO | Sends real-time events | A logged-in browser can be told when its session is ended elsewhere |
| Jinja2 | Renders email-link result pages | Backend HTML pages for verification/reset links |
| SlowAPI | Limits selected endpoints | Reduces rapid repeated registration/login attempts |
| Postman | Tests backend endpoints | Reusable requests, variables, cookies and scripts |

---

## 2. Repository structure

The important project files are organised approximately like this:

```text
fastapi-react-jwtauth/
│
├── fastapi_auth_project/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, routers, Socket.IO wrapper
│   │   ├── config.py               # Environment configuration
│   │   ├── database.py             # SQLAlchemy engine and DB session
│   │   ├── redis_client.py         # Redis connection
│   │   ├── celery_app.py           # Celery application and Redis broker
│   │   ├── limiter.py              # Rate limiter
│   │   ├── models/user.py          # User and Device database models
│   │   ├── schemas/user.py         # Pydantic request/response schemas
│   │   ├── routers/users.py        # Registration, login, refresh, logout, etc.
│   │   ├── auth/jwt_auth.py        # Bearer-token authentication dependency
│   │   ├── utils/
│   │   │   ├── jwt_utils.py       # JWT creation, decoding and token versions
│   │   │   ├── tokens.py          # Redis token/session helpers
│   │   │   ├── csrf.py            # CSRF generation and validation
│   │   │   └── email_utils.py     # SMTP email sender
│   │   ├── tasks/email_tasks.py    # Celery background tasks
│   │   └── socketio_server.py     # Socket.IO connection and rooms
│   ├── templates/users/            # Verification and password pages
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/api.js              # Axios client and token-refresh interceptors
│   │   ├── app/store.js            # Redux store
│   │   ├── features/auth/          # Auth API and Redux slice
│   │   ├── pages/                  # Login, Register, Dashboard, Forgot Password
│   │   ├── components/             # Protected route, navbar, expiry modal, etc.
│   │   └── hooks/useSocketIO.js    # Real-time logout listener
│   ├── vite.config.js              # Development API/WebSocket proxy
│   ├── nginx.conf                  # Production reverse proxy
│   └── Dockerfile
│
├── postmanCollection.json          # Importable Postman collection
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 3. How data is stored

The project deliberately uses **PostgreSQL and Redis for different kinds of data**. They are not interchangeable.

### PostgreSQL — permanent application data

PostgreSQL is the main database. SQLAlchemy models define the tables.

#### `users` table

The `User` model stores account information such as:

- `id`: internal UUID primary key.
- `user_id`: user's login name; unique.
- `email`: unique email address.
- `hashed_password`: bcrypt hash, never the plain password.
- `email_verified`: whether the email link has been verified.
- `is_active`: whether the account can log in.
- `is_staff`: staff flag.
- `date_joined`, `last_login`, `created_at`, `updated_at`.
- `is_deleted`: soft-delete flag.
- Optional profile fields such as first name, last name, phone and profile picture.

Example conceptually:

```text
users
┌──────────────────────────────────────┬──────────────┬─────────────────┐
│ id                                   │ user_id      │ email_verified  │
├──────────────────────────────────────┼──────────────┼─────────────────┤
│ 7c... (UUID)                         │ alex_01      │ true            │
└──────────────────────────────────────┴──────────────┴─────────────────┘
```

The password column contains a bcrypt hash similar in shape to `$2b$...`, not the user's original password.

#### `devices` table

The `Device` model tracks devices/browsers used by a user:

- `id`: internal UUID.
- `user_id`: foreign key to `users.id`.
- `device_id`: public device/session identifier included in JWT claims.
- `device_name`: currently derived from the browser's User-Agent.
- `user_agent`, `ip_address`.
- `is_active`, `is_deleted`.
- Creation/update timestamps.

A unique constraint exists on `(user_id, device_name)`. This lets the application update an existing matching device record instead of always inserting another one.

**Important:** User and device records are stored in PostgreSQL. Raw refresh tokens are not stored in PostgreSQL.

### Redis — sessions, token metadata and temporary tokens

Redis is used for information that needs quick lookup or automatic expiry.

#### Refresh-token records

The key format is:

```text
hash-rt-for-user-<user UUID>
```

It is a Redis Hash. Each field is the refresh token's JWT `jti` (unique token ID), and its value is JSON metadata:

```json
{
  "jti": "unique-jwt-id",
  "user_id": "user-uuid",
  "device_id": "device-uuid",
  "platform": "web",
  "device_name": "browser user-agent",
  "ip_address": "client-ip",
  "created_at": "UTC timestamp"
}
```

The refresh JWT itself is held by the browser in the `refresh_token` **HttpOnly cookie** for web clients. Redis keeps the server-side record that tells the backend whether that refresh session is still allowed.

When a refresh request arrives, the backend:
1. Verifies the JWT signature, issuer, audience, expiry and token type.
2. Reads its `jti`.
3. Looks for that `jti` in the user's Redis hash.
4. Checks the user's token version.
5. Creates a new access token and refresh token.
6. Stores the new refresh-token metadata.
7. Deletes the old `jti` entry.
8. Sends the replacement refresh token as a new HttpOnly cookie.

This is **refresh-token rotation**. A previously used refresh token is no longer present in the session hash.

The Redis hash receives an expiry based on `REFRESH_TOKEN_LIFETIME` (in days). The current helper applies the expiry to the user's hash.

#### Token version

Key format:

```text
token-version:<user UUID>
```

A newly seen user starts at version `0`. JWTs contain a `ver` claim. On every protected request, the backend compares the JWT's version with the current Redis version.

When a password is changed, the backend increments the version. All previously issued access and refresh tokens then have an old version and are rejected, even if their JWT expiry time has not arrived yet.

#### Temporary email/password tokens

The project also uses Redis keys with automatic expiry:

| Redis key pattern | Purpose | Current lifetime |
|---|---|---:|
| `email_verify:<user_id>:<token>` | Email verification | 300 seconds / 5 minutes |
| `password_reset:<user_id>:<token>` | Forgot-password link | 300 seconds / 5 minutes |
| `pwd_reset:<user_id>` | New-login security/password-change token | 180 seconds / 3 minutes |
| `token-version:<user_id>` | Current token generation/version | No expiry is set by the current helper |
| `hash-rt-for-user-<user_id>` | Refresh-session metadata | Refresh lifetime in days |

Redis automatically removes keys when their TTL expires. This is why temporary verification/reset tokens do not need a separate cleanup scheduler.

---

## 4. JWT authentication explained

JWT means **JSON Web Token**. The backend signs the token using `SECRET_KEY` and the configured `JWT_ALGORITHM`.

This project creates two token types.

### Access token

- Short lifetime, configured by `ACCESS_TOKEN_LIFETIME` in **minutes**.
- Sent by the frontend in the `Authorization` header.
- Used to call protected endpoints.
- Contains claims such as `user_id`, `device_id`, `platform`, `type`, `ver`, `exp`, `iat`, `iss`, `aud` and `jti`.

Example request:

```http
GET /api/users/authenticated/
Authorization: Bearer <ACCESS_TOKEN>
```

The backend's `get_current_auth()` dependency validates the bearer token and then checks:
- JWT signature and expiry.
- Token type is `access`.
- Issuer and audience.
- Token version matches Redis.
- User exists, is not deleted and is active.

If any check fails, the endpoint returns an authentication error.

### Refresh token

- Longer lifetime, configured by `REFRESH_TOKEN_LIFETIME` in **days**.
- Used only to obtain a new access token.
- For web login, the backend sends it in an HttpOnly cookie.
- For non-web clients, the API schema supports returning/sending it in the response body.

An HttpOnly cookie cannot be read by normal frontend JavaScript. This reduces the chance that injected JavaScript can simply read and copy the refresh token.

### Why two tokens?

The access token is short-lived, which limits the time window if it is exposed. The refresh token lasts longer, but is more tightly controlled: it is held in an HttpOnly cookie for web, checked against Redis, rotated on use, and can be revoked server-side.

### Token lifetime configuration

```env
ACCESS_TOKEN_LIFETIME=15
REFRESH_TOKEN_LIFETIME=7
```

This means a 15-minute access token and a 7-day refresh token.

The browser refresh cookie is also set with `max_age = REFRESH_TOKEN_LIFETIME * 86400`. Keep cookie lifetime and refresh JWT lifetime aligned.

---

## 5. Complete frontend-to-backend login flow

The normal browser login flow works like this:

```text
User
 │
 ▼
React Login page
 │  userId + password + platform="web"
 ▼
Axios → POST /api/users/login/
 │
 ▼
FastAPI
 │
 ├─ Find user in PostgreSQL
 ├─ Check bcrypt password hash
 ├─ Check email_verified and is_active
 ├─ Find/create Device record in PostgreSQL
 ├─ Read token version from Redis
 ├─ Create access JWT
 ├─ Create refresh JWT
 ├─ Store refresh jti/device metadata in Redis
 └─ Set refresh_token as HttpOnly cookie
 │
 ▼
Response: access token + user data
 │
 ▼
Redux loginSuccess()
 ├─ Keeps access token in Redux
 └─ Persists access token and basic user data in localStorage
 │
 ▼
React navigates to /dashboard
 │
 ▼
GET /authenticated/ with Bearer access token
 │
 ▼
FastAPI validates JWT + Redis token version + PostgreSQL user
 │
 ▼
Dashboard receives user + device_id
 │
 ▼
Socket.IO connects using access token
```

### Why login does not immediately call refresh

A successful login already returns a fresh access token and sets the refresh cookie. Calling `/token/refresh/` immediately after login would rotate a perfectly valid refresh token for no reason.

The frontend therefore saves the login access token and opens the dashboard. It only attempts refresh after a protected request receives `401 Unauthorized`.

### Where frontend authentication state lives

`frontend/src/features/auth/authSlice.js` is the Redux Toolkit slice.

It manages:
- `accessToken`
- `user`
- `deviceId`
- `isAuthenticated`
- `isLoading`
- `error` and `successMessage`
- `sessionExpired`
- Socket.IO connection reference

The current frontend persists the **access token**, basic user object and device ID in `localStorage`. The refresh token is not stored there; it remains in the backend-set HttpOnly cookie.

Example of the login response shape:

```json
{
  "access": "<access-jwt>",
  "user": {
    "id": "user-uuid",
    "userId": "alex_01",
    "email": "alex@example.com"
  },
  "refresh": "Token sent via HttpOnly Cookie"
}
```

The exact UUID and token values are generated by the server.

---

## 6. Access-token expiry and automatic refresh

The central implementation is `frontend/src/app/api.js`.

It creates an Axios instance with:

```javascript
const api = axios.create({
  baseURL: "/api/users",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});
```

- `baseURL` keeps API paths short.
- `withCredentials: true` allows the browser to send/receive cookies.
- The Vite proxy forwards `/api` to FastAPI in development, keeping browser requests same-origin.

### Request interceptor

Before a request is sent, the interceptor reads the current access token from Redux and attaches:

```http
Authorization: Bearer <access-token>
```

For `/token/refresh/` and `/logout/`, it also obtains a CSRF token and attaches:

```http
X-CSRF-Token: <csrf-token>
```

### Response interceptor

If a protected API returns `401`:
1. The interceptor checks that the request has not already been retried.
2. It does not try refresh for login, register, refresh or logout endpoints.
3. It checks that an access token exists.
4. It starts one refresh request.
5. It updates Redux/localStorage with the new access token.
6. It retries the original failed API request with the new bearer token.

### Why `refreshPromise` is used

Imagine the dashboard fires three protected API requests at nearly the same time. All three could return `401`.

Without coordination, the frontend might send three refresh requests. But refresh-token rotation means the first refresh replaces the old refresh token; the other two may then try to use an already-rotated token.

The `refreshPromise` variable makes concurrent failed requests wait for the same refresh operation. Only one refresh request is sent, and all waiting requests reuse the new access token.

### If refresh also fails

If the refresh cookie is missing, expired, revoked, or invalid:
- The interceptor dispatches `setSessionExpired()`.
- Redux authentication state and persisted local auth values are cleared.
- `SessionExpiredModal` is displayed.
- The user can continue to the login page.
- The login page receives a clear message that the session expired and asks the user to sign in again.

A public login page does not call refresh just because the page is refreshed. The refresh flow is triggered by a protected request that fails with `401`.

---

## 7. CSRF protection

CSRF means **Cross-Site Request Forgery**. It is a risk when a browser automatically attaches cookies to a request. A malicious website may try to make a user's browser send an unwanted cookie-authenticated request.

This project protects the web refresh and logout endpoints with a signed double-submit CSRF token.

### How the CSRF flow works

1. Frontend calls `GET /api/users/csrf/`.
2. Backend generates a random nonce and timestamp.
3. Backend signs the timestamp and nonce using HMAC-SHA256 and `CSRF_SECRET_KEY`.
4. Backend returns the token in JSON and also sets a readable `csrf_token` cookie.
5. For refresh/logout, frontend sends the same value in the `X-CSRF-Token` header.
6. Browser automatically sends the cookie.
7. Backend checks that cookie and header exist and match.
8. Backend checks token age and verifies the HMAC signature.
9. If any check fails, the backend rejects the request with HTTP `403`.

Example:

```http
POST /api/users/token/refresh/
Content-Type: application/json
X-CSRF-Token: <same-value-as-csrf-cookie>
Cookie: refresh_token=<http-only-value>; csrf_token=<csrf-value>

{
  "platform": "web"
}
```

### Why two cookies have different HttpOnly settings

| Cookie | HttpOnly | Reason |
|---|---|---|
| `refresh_token` | `true` | JavaScript must not read the refresh credential |
| `csrf_token` | `false` | Frontend needs the token value to send it in a custom header |

The CSRF token is not the refresh token. It cannot be used as a login credential.

### CSRF implementation details

File: `fastapi_auth_project/app/utils/csrf.py`

- Uses Python `secrets` to generate a random nonce.
- Uses `hmac` and `hashlib.sha256` to sign the token.
- Uses `hmac.compare_digest()` for constant-time comparisons.
- Rejects missing, mismatched, expired or incorrectly signed tokens.
- Current maximum age is 3600 seconds (1 hour).

The backend validates CSRF for web-platform `/token/refresh/` and `/logout/`. The current bearer-token protected GET endpoint does not use cookie authentication and does not require this CSRF check.

### Required environment secret

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated value in `.env`:

```env
CSRF_SECRET_KEY=PASTE_THE_GENERATED_SECRET_HERE
```

Do not commit real secrets to Git. Use a different secret in production and keep it private.

---

## 8. Registration and email verification

### Registration flow

Frontend sends:

```http
POST /api/users/register/
Content-Type: application/json
```

```json
{
  "user_id": "alex_01",
  "email": "alex@example.com",
  "password": "StrongPassword123"
}
```

Backend:
1. Validates the username and email with Pydantic.
2. Checks whether username/email already exists.
3. Hashes the password with bcrypt.
4. Creates a user in PostgreSQL with `email_verified=false` and `is_active=false`.
5. Generates an email-verification token.
6. Stores the temporary token in Redis for 5 minutes.
7. Queues the verification email through Celery.

A user cannot log in until email verification succeeds.

### Verification link

The email contains a link similar to:

```text
http://localhost:8000/api/users/verify-email/?user_id=alex_01&token=<verification-token>
```

When opened:
- Backend finds the user.
- Checks the token in Redis.
- Marks `email_verified=true` and `is_active=true` in PostgreSQL.
- Deletes the used Redis verification token.
- Renders the success HTML page.

The link expires after 5 minutes. An invalid or expired link shows an error page.

---

## 9. Celery and background email processing

Celery is the background job system. It prevents slower work—especially email sending—from making normal API requests wait for SMTP.

### Components

- **FastAPI:** creates a task request.
- **Redis broker:** holds queued task messages.
- **Celery worker:** a separate process reads queued tasks and executes them.
- **SMTP:** sends the actual email.

The Celery app is configured in `app/celery_app.py`:

```python
celery_worker = Celery(
    "auth_project",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_tasks"],
)
```

Redis is used as both the task broker and result backend in this project.

### Example: queueing an email

The API does not directly send the email. It calls:

```python
send_email_task.delay(
    "Verify Your Email",
    "Please open the verification link...",
    [user.email],
)
```

`.delay()` sends a task message to the Celery broker. The API can then return its HTTP response without waiting for SMTP delivery.

The worker executes the task:

```python
@shared_task(name="app.tasks.email_tasks.send_email_task")
def send_email_task(subject, message, recipient_list):
    send_email(subject, message, recipient_list)
    return True
```

`send_email()` uses Python's SMTP email support and the configured Gmail SMTP credentials.

### Background jobs in this project

| Task | What it does |
|---|---|
| `send_email_task` | Sends a general email |
| `send_new_login_alert_task` | Builds a new-login security alert and queues email delivery |
| `send_forgot_password_email_task` | Sends the password-reset email |
| `send_password_changed_email_task` | Sends a password-changed notification |
| `send_logout_notification_task` | Publishes a logout event to a user's device room |
| `logout_all_devices_task` | Removes refresh sessions and schedules logout notifications for connected devices |

Some tasks enqueue another task. For example, `send_new_login_alert_task` prepares the message and queues `send_email_task`.

### Why a separate worker?

If SMTP takes 2–5 seconds, directly sending mail inside a registration request makes the user wait. With Celery, FastAPI queues the work and responds; the worker handles delivery separately.

A running FastAPI server does **not** mean Celery is running. Both processes must be started.

---

## 10. Socket.IO and remote logout

Socket.IO provides real-time communication between the backend and an already-open browser.

### Connection flow

1. The dashboard calls `/authenticated/`.
2. Backend returns the real `device_id` from the access token.
3. Frontend connects to `/ws/auth/` using Socket.IO and passes the access token in the Socket.IO `auth` object.
4. Backend validates the JWT and joins the connection to a room:

```text
user_<user UUID>_<device UUID>
```

5. The backend can emit `logout_notification` to that room.

### When remote logout is used

For example, after a password change:
- Backend increments the user's token version.
- Existing access tokens become invalid.
- Refresh sessions are removed by the background task.
- The worker schedules logout notifications for connected devices.
- The browser listens for `logout_notification`.
- On receiving a `LOGOUT` event, it disconnects the socket, clears local authentication and redirects to login with a message.

This gives the user a real-time sign-out experience instead of waiting for the next API call.

**Note:** Socket.IO is a notification channel. The actual authorization decision still belongs to the backend's JWT/token-version checks.

---

## 11. Password-management flows

### Forgot password

Request:

```http
POST /api/users/forgot-password/
Content-Type: application/json
```

```json
{
  "userId": "alex_01"
}
```

If the account exists:
1. Backend creates a random reset token.
2. Stores it in Redis for 5 minutes.
3. Queues an email with the reset link.
4. Returns a generic success message.

The response is intentionally generic so the endpoint does not reveal whether a username exists.

### Normal password reset

The reset page is opened from the email link. The frontend/page submits:

```http
POST /api/users/password-change/
Content-Type: application/json
```

```json
{
  "user_id": "USER_UUID",
  "token": "TOKEN_FROM_EMAIL",
  "new_password": "NewStrongPassword123",
  "confirm_password": "NewStrongPassword123"
}
```

Backend validates the UUID, Redis token and matching passwords, then:
- Hashes and saves the new password in PostgreSQL.
- Increments the user's Redis token version.
- Deletes the used reset token.
- Queues logout-all-devices processing.

### Secure password change after a new-login alert

A new-login alert email contains a short-lived secure link (3 minutes). The secure password-change endpoint also checks the current password.

Request:

```http
POST /api/users/secure-password-change/
Content-Type: application/json
```

```json
{
  "user_id": "USER_UUID",
  "token": "SECURE_TOKEN_FROM_ALERT_EMAIL",
  "current_password": "CurrentPassword123",
  "new_password": "NewStrongPassword123",
  "confirm_password": "NewStrongPassword123"
}
```

On success, the backend:
- Updates the bcrypt password hash.
- Increments token version.
- Deletes the one-time secure token.
- Queues a password-changed email.
- Queues logout of other sessions/devices.

---

## 12. API reference

All API routes are mounted under:

```text
/api/users
```

| Method | Endpoint | Purpose | Authentication / notes |
|---|---|---|---|
| GET | `/csrf/` | Get signed CSRF token | Public; sets `csrf_token` cookie |
| POST | `/register/` | Create account | Public; rate-limited |
| GET | `/verify-email/` | Verify email link | Public; query params `user_id`, `token` |
| POST | `/login/` | Login | Public; rate-limited |
| POST | `/token/refresh/` | Rotate refresh token | Web: refresh cookie + CSRF |
| POST | `/logout/` | End current session | Web: refresh cookie + CSRF |
| GET | `/authenticated/` | Get current user/device | Bearer access token |
| POST | `/forgot-password/` | Send reset email | Public |
| POST | `/password-change/` | Complete reset-link password change | Reset token |
| POST | `/secure-password-change/` | Secure password change | Current password + secure token |
| GET | `/password-change-template/{user_id}/{token}/` | Render reset HTML page | Link token |
| GET | `/secure-password-change-template/{user_id}/{token}/` | Render secure-change HTML page | Secure link token |

### Login example

```json
{
  "userId": "alex_01",
  "password": "StrongPassword123",
  "platform": "web"
}
```

For a web client, the refresh token is set as an HttpOnly cookie. The response returns the access token and user data.

### Refresh example

```json
{
  "platform": "web"
}
```

For web, the browser/Postman cookie jar sends the refresh cookie automatically. The request must also include `X-CSRF-Token`.

### Logout example

```json
{
  "platform": "web"
}
```

For web, the backend validates CSRF, revokes the refresh-token record in Redis and deletes the refresh and CSRF cookies.

---

## 13. Postman collection

The repository includes:

```text
postmanCollection.json
```

It is a Postman Collection v2.1 file.

### Import

1. Open Postman.
2. Click **Import**.
3. Select `postmanCollection.json`.
4. Open the imported collection.
5. Open its variables and set your test username, email and password.
6. Keep Postman's cookie jar enabled.

### Collection variables

| Variable | What to set |
|---|---|
| `baseUrl` | Defaults to `http://localhost:8000/api/users` |
| `userId` | Your test username |
| `email` | Your test email address |
| `password` | Your test password |
| `newPassword` | New password for reset/change |
| `userUuid` | User's internal UUID |
| `accessToken` | Saved automatically after login/refresh |
| `csrfToken` | Saved automatically after Get CSRF Token |
| `emailVerificationToken` | Token from verification email |
| `passwordResetToken` | Token from password-reset email |
| `securePasswordToken` | Token from new-login security email |

### Recommended testing order

1. **Get CSRF Token** — obtains token and saves `csrfToken`.
2. **Register** — creates an inactive account.
3. Open the verification email link, or use its token with Verify Email.
4. **Login (Web)** — saves the access token and sets refresh cookie.
5. **Authenticated User** — checks the bearer access token.
6. When testing refresh, first run **Get CSRF Token**, then **Refresh Token**.
7. **Logout** — first run Get CSRF Token, then Logout.

Password-management requests are in the separate **Password Management** folder.

The collection scripts save the `accessToken` after successful login and refresh, and save `csrfToken` after the CSRF request. Postman must retain the cookies for the web refresh/logout flow.

---

## 14. Environment configuration

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Never use the placeholder values in production.

### Environment variables

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Secret used to sign JWTs |
| `DEBUG` | Development/debug mode; affects secure cookie setting |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL |
| `REDIS_URL` | Redis connection URL; used by sessions and Celery |
| `EMAIL_HOST_USER` | SMTP account username |
| `EMAIL_HOST_PASSWORD` | SMTP password/app password |
| `EMAIL_FROM` | Sender address; if blank, config falls back to SMTP username |
| `EMAIL_PORT` | SMTP port; this code uses `SMTP_SSL`, so configure the SSL SMTP port supported by your provider (commonly 465) |
| `FRONTEND_URL` | Frontend base URL |
| `DOMAIN_URL` | Backend/public domain used in email links and allowed origins |
| `JWT_ALGORITHM` | JWT signing algorithm, normally `HS256` for this setup |
| `JWT_ISSUER` | Expected JWT issuer claim |
| `JWT_AUDIENCE` | Expected JWT audience claim |
| `ACCESS_TOKEN_LIFETIME` | Access token lifetime in minutes |
| `REFRESH_TOKEN_LIFETIME` | Refresh token lifetime in days |
| `POSTGRES_USER` | Docker PostgreSQL username |
| `POSTGRES_PASSWORD` | Docker PostgreSQL password |
| `POSTGRES_DB` | Docker PostgreSQL database name |
| `PGADMIN_EMAIL` | pgAdmin login email |
| `PGADMIN_PASSWORD` | pgAdmin login password |
| `PGADMIN_PORT` | Host port for pgAdmin |
| `CSRF_SECRET_KEY` | Secret used to sign CSRF tokens; at least 32 characters |

Example development configuration (replace all credentials/secrets with your own):

```env
DEBUG=true
SECRET_KEY=replace-with-a-long-random-jwt-secret
CSRF_SECRET_KEY=replace-with-a-different-random-secret-of-at-least-32-chars

DATABASE_URL=postgresql://postgres:postgres@localhost:5433/auth_db
REDIS_URL=redis://localhost:6382/0

EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_PORT=465

FRONTEND_URL=http://localhost:3000
DOMAIN_URL=http://localhost:8000

JWT_ALGORITHM=HS256
JWT_ISSUER=my-app
JWT_AUDIENCE=my-users
ACCESS_TOKEN_LIFETIME=15
REFRESH_TOKEN_LIFETIME=7

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=auth_db
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change-this-password
PGADMIN_PORT=5050
```

`DATABASE_URL` and `REDIS_URL` must match how you run the services. If the API itself runs inside Docker Compose, use service hostnames (`postgres` and `redis`) and their internal ports, for example:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@postgres:5432/auth_db
REDIS_URL=redis://redis:6379/0
```

---

## 15. Run locally (without Docker)

You need PostgreSQL and Redis running locally first.

### Backend

```bash
cd fastapi_auth_project

python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

Create/configure the root `.env` file according to your environment. The settings class reads `.env` from the working directory, so run commands from the repository root or ensure the environment variables are available to the process.

Run database migrations:

```bash
alembic upgrade head
```

Start FastAPI with Socket.IO support:

```bash
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

API base:

```text
http://localhost:8000/api/users
```

### Celery worker

Open another terminal, activate the same Python environment, and from `fastapi_auth_project` run:

```bash
celery -A app.celery_app.celery_worker worker --loglevel=info
```

Keep this process running to process queued emails and background logout tasks.

### Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:3000
```

Vite proxies `/api` and `/ws/auth` to `http://127.0.0.1:8000`. This is why the browser can use same-origin relative API paths.

---

## 16. Run with Docker Compose

The supplied `docker-compose.yml` defines these services:

| Service | Purpose | Default host port |
|---|---|---:|
| `postgres` | PostgreSQL database | 5433 |
| `pgadmin` | Database GUI | 5050 |
| `redis` | Redis | 6382 |
| `web` | FastAPI + Socket.IO | 8000 |
| `celery_worker` | Background task worker | No public port |
| `frontend` | Built frontend served by Nginx | 3000 |

First configure `.env` in the repository root. For containers, use `postgres:5432` and `redis:6379` in the connection URLs, not the host-mapped ports.

Build and start:

```bash
docker compose up --build -d
```

Check running services:

```bash
docker compose ps
```

Follow API logs:

```bash
docker compose logs -f web
```

Follow Celery logs:

```bash
docker compose logs -f celery_worker
```

Follow Redis logs:

```bash
docker compose logs -f redis
```

Stop services:

```bash
docker compose down
```

Stop and also remove persistent database/Redis volumes (this deletes stored data):

```bash
docker compose down -v
```

The Compose file uses named volumes for PostgreSQL, pgAdmin and Redis persistence. Do not use `down -v` unless you intentionally want to remove that data.

The production-style frontend container serves the Vite build through Nginx. Its Nginx configuration forwards `/api/` to the `web` service and upgrades `/ws/auth/` connections for Socket.IO.

---

## 17. Vite proxy, Nginx and cookies

In development, `frontend/vite.config.js` proxies:

```javascript
proxy: {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
  "/ws/auth": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    ws: true,
  },
}
```

The frontend calls `/api/users/...` rather than hardcoding the backend host in every component.

In the Docker/production frontend, Nginx does the equivalent reverse-proxy work.

This same-origin proxy approach is useful for browser cookies. The refresh cookie uses:
- `HttpOnly=true`
- `SameSite=Lax`
- `Path=/api/users/`
- `Secure=true` when `DEBUG` is false

For a real production deployment:
- Use HTTPS.
- Set `DEBUG=false`.
- Configure the real frontend/backend domain and CORS allowed origin.
- Keep `allow_credentials=True` when using credentialed cookies.
- Do not use wildcard CORS origins with credentialed cookies.
- Ensure reverse-proxy headers and cookie domain/path settings match the deployment.
- Keep `SECRET_KEY` and `CSRF_SECRET_KEY` private and stable across application restarts.

---

## 18. Rate limiting

`app/limiter.py` uses SlowAPI with the client IP as the key.

The current router applies:
- Registration: `3/minute`
- Login: `5/minute`

These limits help reduce rapid repeated attempts. They are not a replacement for monitoring, account lockout policy, CAPTCHA/risk controls or infrastructure-level abuse protection.

---

## 19. Useful debugging checklist

### Login succeeds but dashboard returns 401

- Check the access token is present in the login response.
- Check the frontend stores it in Redux/localStorage.
- Check the authenticated request contains `Authorization: Bearer ...`.
- Check backend and frontend use the same JWT secret, issuer, audience and algorithm.
- Check Redis is reachable because token-version validation reads Redis.

### Refresh returns 401

- Check the browser/Postman has the `refresh_token` cookie.
- Check cookie path is `/api/users/`.
- Check the cookie has not expired.
- Check the refresh JWT lifetime.
- Check Redis contains the corresponding user's refresh `jti`.
- Check the token version has not changed.

### Refresh/logout returns 403

- Run `GET /api/users/csrf/` again.
- Confirm the `csrf_token` cookie exists.
- Confirm `X-CSRF-Token` has exactly the same value.
- Confirm `CSRF_SECRET_KEY` is set and is at least 32 characters.
- Confirm frontend requests use `withCredentials: true`.

### Verification/reset email is not received

- Confirm the Celery worker is running.
- Inspect `celery_worker` logs.
- Check SMTP username and app password.
- This project uses `smtplib.SMTP_SSL`; use the correct SSL SMTP port for your provider.
- Check spam/junk folder.
- Confirm Redis is reachable and the temporary token has not expired.

### Socket.IO does not connect

- Confirm `/ws/auth/` is proxied to FastAPI.
- Confirm the access token is valid.
- Confirm `/authenticated/` returned a real `device_id`.
- Check Socket.IO allowed origins and browser console logs.

### Local login cookie is missing

- Confirm `withCredentials: true`.
- Confirm frontend uses the Vite proxy path.
- Confirm cookie path is `/api/users/`.
- In development, `DEBUG=true` makes the cookie non-Secure. In production, use HTTPS with `DEBUG=false`.

---

## 20. Security notes and production checklist

Before deploying publicly:

- Set `DEBUG=false`.
- Use HTTPS everywhere.
- Generate strong, independent `SECRET_KEY` and `CSRF_SECRET_KEY` values.
- Never commit `.env`, passwords, SMTP app passwords or signing secrets.
- Use a production database and Redis with authentication/network restrictions.
- Restrict CORS to the exact trusted frontend origin(s).
- Review cookie domain, path, `SameSite` and `Secure` attributes for the real domain.
- Use a proper SMTP provider and validate delivery/retry behavior.
- Run Celery workers as supervised services.
- Back up PostgreSQL and configure Redis persistence/backup according to the session recovery requirements.
- Add monitoring and structured logging; avoid printing tokens, passwords or sensitive values.
- Review rate limits and account-abuse controls.
- Keep dependencies updated and scan them for known vulnerabilities.
- Test email verification, password reset, refresh rotation, CSRF rejection, session expiry and remote logout in the production-like environment.

The current code is a working application implementation, but production readiness also depends on deployment configuration, secret management, monitoring, backups and operational testing.

---

## 21. End-to-end example: what happens when an access token expires?

Assume:
- Access token lifetime is 1 minute (for testing).
- Refresh token lifetime is 7 days.
- The user is on the dashboard.

Sequence:

1. The dashboard calls `/authenticated/` with the access token.
2. The access token expires, so FastAPI responds with `401`.
3. Axios response interceptor catches the `401`.
4. Axios gets a CSRF token from `/csrf/`.
5. Axios sends `/token/refresh/` with the refresh cookie and `X-CSRF-Token`.
6. FastAPI validates CSRF, JWT claims, token version and Redis refresh-session record.
7. FastAPI creates a new access token and refresh token.
8. Redis stores the new refresh `jti` metadata and removes the old `jti`.
9. FastAPI replaces the HttpOnly refresh cookie.
10. Axios saves the new access token in Redux/localStorage.
11. Axios retries the original `/authenticated/` request.
12. Dashboard continues without asking the user to log in again.

If the refresh token has also expired or has been revoked, refresh fails. The frontend clears local authentication and displays the **Your session has timed out** dialog. The user is then redirected to login with a session-expired message.

---

## 22. Final summary

This project combines several layers rather than relying on a single JWT check:

- **PostgreSQL** is the permanent source of truth for users and devices.
- **Redis** tracks refresh sessions, token versions and temporary verification/reset tokens.
- **JWT access tokens** authenticate protected API requests.
- **HttpOnly refresh cookies** keep the web refresh credential away from normal JavaScript access.
- **Refresh-token rotation** replaces a refresh token each time it is used.
- **CSRF protection** verifies cookie-authenticated refresh/logout requests.
- **Celery + Redis** handle email and other background work outside the API request cycle.
- **Socket.IO** informs active browser sessions when they are logged out remotely.
- **React + Redux + Axios** manage the user interface and automatic refresh/retry behavior.
- **Postman collection** provides a repeatable way to test the backend APIs.

The main idea is separation of responsibilities: permanent account data stays in PostgreSQL, short-lived/session state stays in Redis, background work runs in Celery, and the frontend handles presentation and token refresh coordination while the backend remains responsible for final authorization.
