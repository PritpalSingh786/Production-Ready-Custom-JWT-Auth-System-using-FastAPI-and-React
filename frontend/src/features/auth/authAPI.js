import api from "../../app/api";

export const authAPI = {
  register: async (userData) => {
    const { data } = await api.post("/register/", userData);
    return data;
  },
  login: async (credentials) => {
    const { data } = await api.post("/login/", {
      userId: credentials.userId,
      password: credentials.password,
      platform: "web",
    });
    return data;
  },
  logout: async () => {
    const { data } = await api.post("/logout/", { platform: "web" });
    return data;
  },
  getAuthenticatedUser: async () => {
    const { data } = await api.get("/authenticated/");
    return data;
  },
  forgotPassword: async (userId) => {
    const { data } = await api.post("/forgot-password/", { userId });
    return data;
  },
};
