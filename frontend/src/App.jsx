import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { useEffect } from "react";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import Dashboard from "./pages/Dashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import SessionExpiredModal from "./components/SessionExpiredModal";
import { logoutRequest, resetExpiryNotice } from "./app/api";

function AppRoutes() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionExpired, isAuthenticated } = useSelector((state) => state.auth);

  // A protected-page reload is validated by Dashboard's authenticated API.
  // The response interceptor refreshes only if that API returns 401.
  // Public routes (especially /login) never call the refresh endpoint here.

  useEffect(() => {
    if (location.pathname === "/login" && !isAuthenticated) {
      resetExpiryNotice();
    }
  }, [location.pathname, isAuthenticated]);

  const continueToLogin = async () => {
    await logoutRequest();
    resetExpiryNotice();
    navigate("/login", {
      replace: true,
      state: {
        message: "Your session has expired. Please log in again.",
      },
    });
  };

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>

      {sessionExpired && (
        <SessionExpiredModal onContinue={continueToLogin} />
      )}
    </>
  );
}

export default function App() {
  return <AppRoutes />;
}
