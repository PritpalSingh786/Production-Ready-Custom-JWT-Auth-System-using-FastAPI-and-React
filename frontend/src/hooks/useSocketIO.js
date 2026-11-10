import { useEffect, useState } from "react";
import { io } from "socket.io-client";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { logoutSuccess, setWebSocket } from "../features/auth/authSlice";

export default function useSocketIO(enabled = true) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { accessToken, deviceId, isAuthenticated } = useSelector(
    (state) => state.auth
  );
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!enabled || !isAuthenticated || !accessToken || !deviceId) {
      setIsConnected(false);
      return undefined;
    }

    // Connect to the same host; Vite proxies /ws/auth/ to FastAPI.
    const socket = io(window.location.origin, {
      path: "/ws/auth/",
      auth: { token: accessToken },
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: 8,
      timeout: 10000,
    });

    const onConnect = () => {
      console.info("Socket.IO connected:", socket.id);
      setIsConnected(true);
    };

    const onConnectError = (error) => {
      console.error("Socket.IO connection error:", error.message);
      setIsConnected(false);
    };

    const onDisconnect = () => {
      setIsConnected(false);
    };

    const onRemoteLogout = (data) => {
      if (data?.type !== "LOGOUT") return;

      socket.disconnect();
      dispatch(logoutSuccess());
      navigate("/login", {
        replace: true,
        state: {
          message:
            data.message ||
            "Your session was ended because your account was signed out elsewhere.",
        },
      });
    };

    socket.on("connect", onConnect);
    socket.on("connect_error", onConnectError);
    socket.on("disconnect", onDisconnect);
    socket.on("logout_notification", onRemoteLogout);

    dispatch(setWebSocket(socket));

    return () => {
      socket.off("connect", onConnect);
      socket.off("connect_error", onConnectError);
      socket.off("disconnect", onDisconnect);
      socket.off("logout_notification", onRemoteLogout);
      socket.disconnect();
      dispatch(setWebSocket(null));
      setIsConnected(false);
    };
  }, [enabled, isAuthenticated, accessToken, deviceId, dispatch, navigate]);

  return { isConnected };
}
