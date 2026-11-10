import { createSlice } from '@reduxjs/toolkit';
const authSlice = createSlice({
  name: 'auth',
  initialState: { accessToken: null, user: null, initialized: false, sessionExpired: false },
  reducers: {
    setCredentials(state, action) { state.accessToken = action.payload.access; state.user = action.payload.user ?? state.user; state.initialized = true; state.sessionExpired = false; },
    setUser(state, action) { state.user = action.payload; },
    setInitialized(state) { state.initialized = true; },
    setSessionExpired(state) { state.sessionExpired = true; state.accessToken = null; state.user = null; },
    clearSession(state) { state.accessToken = null; state.user = null; state.sessionExpired = false; state.initialized = true; }
  }
});
export const { setCredentials, setUser, setInitialized, setSessionExpired, clearSession } = authSlice.actions;
export default authSlice.reducer;
