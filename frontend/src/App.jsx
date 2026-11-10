
import { useEffect } from "react";
import {
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { io } from "socket.io-client";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import Dashboard from "./pages/Dashboard";

import SessionExpiredModal from "./components/SessionExpiredModal";

import api, {
  logoutRequest,
  resetExpiryNotice,
} from "./app/api";

import {
  setCredentials,
  setInitialized,
  clearSession,
} from "./features/auth/authSlice";


function Protected({ children }) {
  const { accessToken, initialized } = useSelector(
    (state) => state.auth
  );

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  return children;
}


function Shell({ children }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logoutRequest();

    sessionStorage.removeItem("authflow-had-session");

    navigate("/login", { replace: true });
  };

  return (
    <>
      <button onClick={handleLogout}>
        Sign Out
      </button>

      {children}
    </>
  );
}


function App() {
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const {
    accessToken,
    sessionExpired,
    initialized,
  } = useSelector((state) => state.auth);


  // Bootstrap authentication session
  useEffect(() => {
    let active = true;

    const initializeAuth = async () => {
      try {
        // Refresh access token
        const refreshResponse = await api.post(
          "/token/refresh/",
          { platform: "web" }
        );

        const access = refreshResponse.data.access;

        if (!active) return;

        // Fetch authenticated user
        const userResponse = await api.get(
          "/authenticated/"
        );

        if (!active) return;

        // Handle both { user: {...} } and direct user response
        const userData =
          userResponse.data?.user || userResponse.data;

        // Store access token and actual user object
        dispatch(
          setCredentials({
            access,
            user: userData,
          })
        );

        resetExpiryNotice();

      } catch (error) {
        if (!active) return;

        console.error(
          "Authentication initialization failed:",
          error.response?.data || error.message
        );

        const hadSession =
          sessionStorage.getItem("authflow-had-session") === "1";

        dispatch(clearSession());

        if (hadSession) {
          sessionStorage.removeItem("authflow-had-session");

          navigate("/login", {
            replace: true,
            state: {
              message: "Your session has expired. Please login again.",
            },
          });
        }

      } finally {
        if (active) {
          dispatch(setInitialized());
        }
      }
    };

    initializeAuth();

    return () => {
      active = false;
    };

  }, [dispatch, navigate]);


  // Socket.IO: JWT authentication and remote logout
  useEffect(() => {
    if (!accessToken) return;

    const socket = io("/", {
      path: "/ws/auth/",
      auth: {
        token: accessToken,
      },
      transports: ["websocket"],
      reconnection: true,
    });


    socket.on("connect", () => {
      console.log("Socket connected:", socket.id);
    });


    socket.on("connect_error", (error) => {
      console.error(
        "Socket connection error:",
        error.message
      );
    });


    // Logout notification from another device
    socket.on("logout_notification", async (data) => {
      if (data?.type !== "LOGOUT") return;

      console.log("Remote logout:", data.message);

      socket.disconnect();

      sessionStorage.removeItem("authflow-had-session");

      resetExpiryNotice();

      await logoutRequest();

      navigate("/login", {
        replace: true,
        state: {
          message:
            data.message ||
            "Your password was changed. Please login again.",
        },
      });
    });


    return () => {
      socket.disconnect();
    };

  }, [accessToken, navigate]);


  // Session expired modal
  const closeExpired = async () => {
    await logoutRequest();

    sessionStorage.removeItem("authflow-had-session");

    resetExpiryNotice();

    navigate("/login", {
      replace: true,
      state: {
        message: "Your session has expired. Please login again.",
      },
    });
  };


  if (!initialized) {
    return <div>Loading...</div>;
  }


  return (
    <>
      <Routes>

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/register"
          element={<Register />}
        />

        <Route
          path="/forgot-password"
          element={<ForgotPassword />}
        />

        <Route
          path="/"
          element={
            <Protected>
              <Shell>
                <Dashboard />
              </Shell>
            </Protected>
          }
        />

        <Route
          path="*"
          element={
            <Navigate
              to={accessToken ? "/" : "/login"}
              replace
            />
          }
        />

      </Routes>


      {sessionExpired && (
        <SessionExpiredModal
          onClose={closeExpired}
        />
      )}

    </>
  );
}


export default App;
