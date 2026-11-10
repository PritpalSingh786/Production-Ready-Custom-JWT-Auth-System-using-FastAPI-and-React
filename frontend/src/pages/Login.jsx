import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  UserRound,
} from "lucide-react";
import AuthLayout from "../components/AuthLayout";
import { authAPI } from "../features/auth/authAPI";
import {
  clearMessages,
  loginSuccess,
  setError,
  setLoading,
} from "../features/auth/authSlice";
import { resetExpiryNotice } from "../app/api";

export default function Login() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoading, error, isAuthenticated, successMessage } = useSelector(
    (state) => state.auth
  );

  const [form, setForm] = useState({ userId: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    dispatch(clearMessages());
    if (location.state?.message) {
      // The message is shown from router state below.
    }
  }, [dispatch, location.key]);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const update = (event) => {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    dispatch(clearMessages());
    dispatch(setLoading(true));

    try {
      const data = await authAPI.login(form);

      // Login only stores the access token. The refresh token is an
      // HttpOnly cookie set by FastAPI; do not call refresh after login.
      dispatch(loginSuccess({ access: data.access, user: data.user }));
      resetExpiryNotice();
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.user_id ||
            detail?.email ||
            err.response?.data?.message ||
            "Login failed. Please check your username and password.";
      dispatch(setError(message));
    } finally {
      dispatch(setLoading(false));
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your secure workspace."
      footer={
        <>
          New to AuthFlow?{" "}
          <Link to="/register">
            Create an account <ArrowRight size={13} />
          </Link>
        </>
      }
    >
      {location.state?.message && (
        <div className="success-alert">{location.state.message}</div>
      )}
      {successMessage && <div className="success-alert">{successMessage}</div>}
      {error && <div className="error-alert">{error}</div>}

      <form onSubmit={submit} className="auth-form">
        <label htmlFor="userId">Username</label>
        <div className="input-wrap">
          <UserRound size={17} />
          <input
            id="userId"
            name="userId"
            value={form.userId}
            onChange={update}
            placeholder="Enter your username"
            autoComplete="username"
            required
          />
        </div>

        <div className="label-row">
          <label htmlFor="password">Password</label>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <div className="input-wrap">
          <LockKeyhole size={17} />
          <input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            value={form.password}
            onChange={update}
            placeholder="Enter your password"
            autoComplete="current-password"
            required
          />
          <button
            type="button"
            className="icon-btn"
            onClick={() => setShowPassword((value) => !value)}
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        </div>

        <button className="primary-btn" disabled={isLoading}>
          {isLoading ? "Signing in…" : "Sign in securely"} <ArrowRight size={17} />
        </button>
      </form>

      <div className="form-divider">
        <span /> <small>SECURE AUTHENTICATION</small> <span />
      </div>
      <div className="trust-line">
        Protected with JWT access tokens and HttpOnly refresh cookies.
      </div>
    </AuthLayout>
  );
}
