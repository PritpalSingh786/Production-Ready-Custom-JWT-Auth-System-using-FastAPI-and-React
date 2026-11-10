import { createSlice } from "@reduxjs/toolkit";

const readStoredAuth = () => {
  try {
    const accessToken = localStorage.getItem("access_token");
    const storedUser = localStorage.getItem("auth_user");
    const user = storedUser ? JSON.parse(storedUser) : null;

    return {
      accessToken: accessToken || null,
      user,
      deviceId: localStorage.getItem("device_id") || null,
      platform: "web",
      isAuthenticated: Boolean(accessToken),
      isLoading: false,
      error: null,
      successMessage: null,
      sessionExpired: false,
      webSocket: null,
    };
  } catch {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_user");
    localStorage.removeItem("device_id");
    return {
      accessToken: null,
      user: null,
      deviceId: null,
      platform: "web",
      isAuthenticated: false,
      isLoading: false,
      error: null,
      successMessage: null,
      sessionExpired: false,
      webSocket: null,
    };
  }
};

const initialState = readStoredAuth();

const clearStoredAuth = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("auth_user");
  localStorage.removeItem("device_id");
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setLoading(state, action) {
      state.isLoading = action.payload;
    },
    setError(state, action) {
      state.error = action.payload;
      state.successMessage = null;
    },
    setSuccess(state, action) {
      state.successMessage = action.payload;
      state.error = null;
    },
    clearMessages(state) {
      state.error = null;
      state.successMessage = null;
    },
    registerSuccess(state, action) {
      state.successMessage = action.payload.message;
      state.isLoading = false;
      state.error = null;
    },
    loginSuccess(state, action) {
      const { access, user } = action.payload;
      state.accessToken = access;
      state.user = user;
      state.deviceId = null;
      state.platform = "web";
      state.isAuthenticated = Boolean(access);
      state.isLoading = false;
      state.error = null;
      state.successMessage = null;
      state.sessionExpired = false;
      localStorage.setItem("access_token", access);
      localStorage.setItem("auth_user", JSON.stringify(user));
      localStorage.removeItem("device_id");
    },
    setCredentials(state, action) {
      const { access, user } = action.payload;
      if (access) {
        state.accessToken = access;
        state.isAuthenticated = true;
        localStorage.setItem("access_token", access);
      }
      if (user) {
        state.user = user;
        localStorage.setItem("auth_user", JSON.stringify(user));
      }
      state.sessionExpired = false;
    },
    setUser(state, action) {
      state.user = action.payload;
      if (action.payload) {
        localStorage.setItem("auth_user", JSON.stringify(action.payload));
      }
    },
    setDeviceId(state, action) {
      state.deviceId = action.payload || null;
      if (action.payload) {
        localStorage.setItem("device_id", action.payload);
      } else {
        localStorage.removeItem("device_id");
      }
    },
    updateTokens(state, action) {
      state.accessToken = action.payload.access;
      state.isAuthenticated = Boolean(action.payload.access);
      localStorage.setItem("access_token", action.payload.access);
    },
    setWebSocket(state, action) {
      state.webSocket = action.payload;
    },
    setSessionExpired(state) {
      state.sessionExpired = true;
      state.accessToken = null;
      state.user = null;
      state.deviceId = null;
      state.isAuthenticated = false;
      state.webSocket = null;
      clearStoredAuth();
    },
    logoutSuccess(state) {
      state.accessToken = null;
      state.user = null;
      state.deviceId = null;
      state.platform = "web";
      state.isAuthenticated = false;
      state.isLoading = false;
      state.error = null;
      state.successMessage = null;
      state.sessionExpired = false;
      state.webSocket = null;
      clearStoredAuth();
    },
    clearSession(state) {
      state.accessToken = null;
      state.user = null;
      state.deviceId = null;
      state.isAuthenticated = false;
      state.sessionExpired = false;
      state.webSocket = null;
      clearStoredAuth();
    },
    setInitialized() {
      // Kept for compatibility with the previous app structure.
    },
    setErrorMessage(state, action) {
      state.error = action.payload;
    },
  },
});

export const {
  setLoading,
  setError,
  setSuccess,
  clearMessages,
  registerSuccess,
  loginSuccess,
  setCredentials,
  setUser,
  setDeviceId,
  updateTokens,
  setWebSocket,
  setSessionExpired,
  logoutSuccess,
  clearSession,
  setInitialized,
  setErrorMessage,
} = authSlice.actions;

export default authSlice.reducer;
