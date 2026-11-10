import axios from "axios";
import { store } from "./store";
import {
  updateTokens,
  setSessionExpired,
  logoutSuccess,
} from "../features/auth/authSlice";

const api = axios.create({
  // Vite proxies this path to FastAPI in development.
  // Keep it same-origin so the HttpOnly refresh cookie is included.
  baseURL: "/api/users",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Separate client avoids running the normal auth interceptors for GET /csrf/.
const csrfClient = axios.create({
  baseURL: "/api/users",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

let refreshPromise = null;
let csrfPromise = null;
let expiryNotified = false;

const isAuthEndpoint = (url = "") =>
  /\/(login|register|token\/refresh|logout)\//.test(url);

const isCsrfProtectedEndpoint = (url = "") =>
  /\/(token\/refresh|logout)\//.test(url);

// Fetch a fresh signed token each time a protected cookie-auth request starts.
// Concurrent calls share one request so multiple 401s don't create a token race.
async function getCsrfToken() {
  if (!csrfPromise) {
    csrfPromise = csrfClient
      .get("/csrf/")
      .then(({ data }) => {
        if (!data?.csrf_token) {
          throw new Error("CSRF endpoint did not return csrf_token");
        }
        return data.csrf_token;
      })
      .finally(() => {
        csrfPromise = null;
      });
  }

  return csrfPromise;
}

api.interceptors.request.use(
  async (config) => {
    const token = store.getState().auth.accessToken;
    config.headers = config.headers || {};

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (isCsrfProtectedEndpoint(config.url)) {
      config.headers["X-CSRF-Token"] = await getCsrfToken();
    }

    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    // Never refresh for login/register/refresh/logout endpoints.
    if (
      status !== 401 ||
      !original ||
      original._retry ||
      isAuthEndpoint(original.url)
    ) {
      return Promise.reject(error);
    }

    // No access token means there is no authenticated request to refresh.
    if (!store.getState().auth.accessToken) {
      return Promise.reject(error);
    }

    original._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = (async () => {
          const csrf = await getCsrfToken();

          // Use bare axios so the refresh request does not recursively enter
          // this instance's request/response interceptors.
          const { data } = await axios.post(
            "/api/users/token/refresh/",
            { platform: "web" },
            {
              withCredentials: true,
              headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
              },
            }
          );

          if (!data?.access) {
            throw new Error("Refresh API did not return an access token");
          }

          store.dispatch(updateTokens({ access: data.access }));
          expiryNotified = false;
          return data.access;
        })().finally(() => {
          refreshPromise = null;
        });
      }

      const newAccess = await refreshPromise;
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${newAccess}`;

      return api(original);
    } catch (refreshError) {
      console.error(
        "Refresh token failed:",
        refreshError.response?.data || refreshError.message
      );

      if (!expiryNotified) {
        expiryNotified = true;
        store.dispatch(setSessionExpired());
      }

      return Promise.reject(refreshError);
    }
  }
);

export async function logoutRequest() {
  try {
    // Request interceptor fetches CSRF token and attaches X-CSRF-Token.
    await api.post("/logout/", { platform: "web" });
  } catch (error) {
    // Always clear local state even if the server-side logout request fails.
    console.warn(
      "Logout request failed:",
      error.response?.data || error.message
    );
  }

  expiryNotified = false;
  store.dispatch(logoutSuccess());
}

export function resetExpiryNotice() {
  expiryNotified = false;
}

export default api;