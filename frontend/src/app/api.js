import axios from 'axios';
import { store } from './store';
import { setCredentials, setSessionExpired, clearSession } from '../features/auth/authSlice';

// Same-origin requests are routed by the frontend Nginx container to FastAPI.
const api = axios.create({ baseURL: '/api/users', withCredentials: true, headers: { 'Content-Type': 'application/json' } });
let refreshPromise = null;
let expiryNotified = false;

api.interceptors.request.use((config) => {
  const token = store.getState().auth.accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthEndpoint = /\/(login|register|token\/refresh|logout)\//.test(original?.url || '');
    if (status !== 401 || !original || original._retry || isAuthEndpoint) return Promise.reject(error);

    original._retry = true;
    try {
      if (!refreshPromise) {
        refreshPromise = axios.post('/api/users/token/refresh/', { platform: 'web' }, { withCredentials: true })
          .then(({ data }) => {
            store.dispatch(setCredentials({ access: data.access }));
            return data.access;
          })
          .finally(() => { refreshPromise = null; });
      }
      const newAccess = await refreshPromise;
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    } catch (refreshError) {
      if (!expiryNotified) {
        expiryNotified = true;
        store.dispatch(setSessionExpired());
      }
      return Promise.reject(refreshError);
    }
  }
);

export async function logoutRequest() {
  try { await api.post('/logout/', { platform: 'web' }); } catch { /* local logout must still complete */ }
  expiryNotified = false;
  store.dispatch(clearSession());
}
export function resetExpiryNotice() { expiryNotified = false; }
export default api;
