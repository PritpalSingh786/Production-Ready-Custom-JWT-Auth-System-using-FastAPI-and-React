UPDATED AUTHFLOW FRONTEND

This is the Vite frontend adapted to the FastAPI backend in the supplied project.

Run:
  cd frontend
  npm install
  npm run dev

Frontend: http://localhost:3000
Backend expected: http://127.0.0.1:8000

API requests use /api/users through the Vite proxy.
Socket.IO uses /ws/auth/ through the Vite websocket proxy.

Authentication behaviour:
- Successful login does NOT call /token/refresh/.
- Access token is stored in localStorage; refresh token remains in the backend's HttpOnly cookie.
- Dashboard calls /authenticated/ after login and after a protected-page reload.
- If that request returns 401, the Axios interceptor calls /token/refresh/ once and retries.
- If refresh is rejected, the session-expired dialog is shown.
- Socket.IO connects only after /authenticated/ returns the backend's real device_id.
- Remote logout is listened for on the "logout_notification" event.

IMPORTANT BACKEND CHECK:
In app/routers/users.py, the login route currently sets the refresh cookie with max_age=120.
That means the browser cookie expires after 120 seconds regardless of a longer JWT refresh-token lifetime.
Set max_age to the refresh-token lifetime in seconds (or omit max_age and use expires consistently)
if you expect the browser cookie to live longer than two minutes. Keep cookie path="/api/users/".
