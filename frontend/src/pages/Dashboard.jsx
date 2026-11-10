import { useEffect, useRef, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  ShieldCheck,
  Mail,
  Fingerprint,
  RefreshCw,
  CheckCircle2,
  Radio,
} from "lucide-react";
import api from "../app/api";
import { setDeviceId, setUser } from "../features/auth/authSlice";
import Navbar from "../components/Navbar";
import LoadingSpinner from "../components/LoadingSpinner";
import useSocketIO from "../hooks/useSocketIO";

export default function Dashboard() {
  const dispatch = useDispatch();
  const { user, deviceId, accessToken } = useSelector((state) => state.auth);
  const [authData, setAuthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [notice, setNotice] = useState("");
  const requestPromise = useRef(null);

  // Socket.IO is opened only after /authenticated/ succeeds and returns device_id.
  const { isConnected } = useSocketIO(Boolean(authData && deviceId));

  const loadAuthenticatedUser = () => {
    setLoading(true);
    setAuthError("");
    setNotice("");
    requestPromise.current = api
      .get("/authenticated/")
      .then(({ data }) => {
        setAuthData(data);
        if (data.user) dispatch(setUser(data.user));
        if (data.device_id) dispatch(setDeviceId(data.device_id));
        setNotice("Your access token is valid.");
        return data;
      })
      .catch((error) => {
        console.error(
          "Authenticated API failed:",
          error.response?.data || error.message
        );
        setAuthError(
          error.response?.data?.detail || "Unable to authenticate user."
        );
        throw error;
      })
      .finally(() => setLoading(false));

    return requestPromise.current;
  };

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      return;
    }

    if (!requestPromise.current) {
      loadAuthenticatedUser().catch(() => {});
    }
    // Initial authenticated check on dashboard entry/reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const verify = async () => {
    try {
      await loadAuthenticatedUser();
    } catch {
      // The interceptor displays the session-expired dialog if refresh fails.
    }
  };

  if (loading) return <LoadingSpinner />;

  const currentUser = authData?.user || user;

  return (
    <>
      <Navbar />
      <main className="dashboard-content dashboard-shell">
        <div className="welcome-row">
          <div>
            <div className="eyebrow">
              OVERVIEW <span className="live-dot" /> LIVE SESSION
            </div>
            <h1>Good to see you, {currentUser?.userId || "there"}.</h1>
            <p>Here’s the security status of your account.</p>
          </div>
          <div className="welcome-mark"><ShieldCheck size={30} /></div>
        </div>

        {authError && <div className="error-alert">{authError}</div>}

        <div className="status-banner">
          <div className="status-check"><CheckCircle2 size={20} /></div>
          <div>
            <strong>Your account session is active</strong>
            <p>You are authenticated and your protected workspace is ready.</p>
          </div>
          <span className="status-pill">SECURE</span>
        </div>

        <div className="section-heading">
          <div>
            <span className="eyebrow">ACCOUNT DETAILS</span>
            <h2>Your profile</h2>
          </div>
          <button className="secondary-btn" onClick={verify} disabled={loading}>
            <RefreshCw size={15} className={loading ? "spin" : ""} />
            {loading ? "Checking…" : "Verify session"}
          </button>
        </div>

        {notice && <div className="success-alert compact-alert">{notice}</div>}

        <div className="detail-grid">
          <article className="detail-card">
            <div className="detail-icon"><Fingerprint size={19} /></div>
            <span className="detail-label">USERNAME</span>
            <strong>{currentUser?.userId || "—"}</strong>
            <small>Your unique account identifier</small>
          </article>
          <article className="detail-card">
            <div className="detail-icon"><Mail size={19} /></div>
            <span className="detail-label">EMAIL ADDRESS</span>
            <strong>{currentUser?.email || "—"}</strong>
            <small>Registered email address</small>
          </article>
          <article className="detail-card">
            <div className="detail-icon"><ShieldCheck size={19} /></div>
            <span className="detail-label">AUTHENTICATION</span>
            <strong>JWT Protected</strong>
            <small>Short-lived access token</small>
          </article>
        </div>

        <div className="security-panel">
          <div className="security-panel-icon"><ShieldCheck size={20} /></div>
          <div>
            <strong>Security is handled automatically</strong>
            <p>
              When your access token expires, the app attempts a secure refresh
              using your HttpOnly cookie. If your refresh session has expired,
              you’ll be asked to sign in again.
            </p>
          </div>
        </div>

        <div className="socket-status">
          <Radio size={17} />
          <span>Socket.IO:</span>
          <strong className={isConnected ? "socket-online" : "socket-offline"}>
            {isConnected ? "Connected · remote logout enabled" : "Connecting…"}
          </strong>
        </div>

        <div className="dashboard-bottom">
          AUTHFLOW <span>·</span> ACCOUNT SECURITY <span>·</span> SESSION PROTECTED
        </div>
      </main>
    </>
  );
}
