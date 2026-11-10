
import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import {
  ShieldCheck,
  Mail,
  Fingerprint,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";

import api from "../app/api";

export default function Dashboard() {
  const user = useSelector((s) => s.auth.user);

  const [profile, setProfile] = useState(user || null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  // Keep profile synchronized with Redux user data
  useEffect(() => {
    setProfile(user?.user || user || null);
  }, [user]);

  // Verify authentication and refresh profile data
  const verify = async () => {
    setLoading(true);
    setNotice("");

    try {
      const { data } = await api.get("/authenticated/");

      const userData = data?.user || data;

      setProfile(userData);

      setNotice("Your access token is valid.");
    } catch (error) {
      console.error(
        "Session verification failed:",
        error.response?.data || error.message
      );

      setNotice("Could not verify your session right now.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-content">

      {/* Welcome Section */}
      <div className="welcome-row">
        <div>
          <div className="eyebrow">
            OVERVIEW <span className="live-dot" /> LIVE SESSION
          </div>

          <h1>
            Good to see you, {profile?.userId || "there"}.
          </h1>

          <p>
            Here’s the security status of your account.
          </p>
        </div>

        <div className="welcome-mark">
          <ShieldCheck size={30} />
        </div>
      </div>


      {/* Session Status */}
      <div className="status-banner">
        <div className="status-check">
          <CheckCircle2 size={20} />
        </div>

        <div>
          <strong>Your account session is active</strong>

          <p>
            You are authenticated and your protected workspace is ready.
          </p>
        </div>

        <span className="status-pill">
          SECURE
        </span>
      </div>


      {/* Account Details */}
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            ACCOUNT DETAILS
          </span>

          <h2>Your profile</h2>
        </div>

        <button
          className="secondary-btn"
          onClick={verify}
          disabled={loading}
        >
          <RefreshCw
            size={15}
            className={loading ? "spin" : ""}
          />

          {loading ? "Checking…" : "Verify session"}
        </button>
      </div>


      {/* Verification Notice */}
      {notice && (
        <div className="success-alert compact-alert">
          {notice}
        </div>
      )}


      {/* Profile Cards */}
      <div className="detail-grid">

        <article className="detail-card">
          <div className="detail-icon">
            <Fingerprint size={19} />
          </div>

          <span className="detail-label">
            USERNAME
          </span>

          <strong>
            {profile?.userId || "—"}
          </strong>

          <small>
            Your unique account identifier
          </small>
        </article>


        <article className="detail-card">
          <div className="detail-icon">
            <Mail size={19} />
          </div>

          <span className="detail-label">
            EMAIL ADDRESS
          </span>

          <strong>
            {profile?.email || "—"}
          </strong>

          <small>
            Registered email address
          </small>
        </article>


        <article className="detail-card">
          <div className="detail-icon">
            <ShieldCheck size={19} />
          </div>

          <span className="detail-label">
            AUTHENTICATION
          </span>

          <strong>
            JWT Protected
          </strong>

          <small>
            Short-lived access token
          </small>
        </article>

      </div>


      {/* Security Information */}
      <div className="security-panel">
        <div className="security-panel-icon">
          <ShieldCheck size={20} />
        </div>

        <div>
          <strong>
            Security is handled automatically
          </strong>

          <p>
            When your access token expires, the app attempts a secure refresh
            using your HttpOnly cookie. If your refresh session has expired,
            you’ll be asked to sign in again.
          </p>
        </div>
      </div>


      {/* Footer */}
      <div className="dashboard-bottom">
        AUTHFLOW <span>·</span> ACCOUNT SECURITY <span>·</span> SESSION
        PROTECTED
      </div>

    </div>
  );
}
