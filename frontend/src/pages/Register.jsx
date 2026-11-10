import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  UserRound,
  Mail,
  LockKeyhole,
  Eye,
  EyeOff,
} from "lucide-react";
import AuthLayout from "../components/AuthLayout";
import { authAPI } from "../features/auth/authAPI";

export default function Register() {
  const [form, setForm] = useState({ user_id: "", email: "", password: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const update = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await authAPI.register(form);
      setSuccess(data.message || "Account created. Please verify your email.");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : detail?.user_id ||
            detail?.email ||
            "Registration failed. Please review your details."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="A few details and your secure workspace is ready."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login">Sign in <ArrowRight size={13} /></Link>
        </>
      }
    >
      {error && <div className="error-alert">{error}</div>}
      {success && (
        <div className="success-alert">
          {success}{" "}
          <button type="button" className="text-action" onClick={() => navigate("/login")}>
            Go to sign in
          </button>
        </div>
      )}

      <form onSubmit={submit} className="auth-form">
        <label htmlFor="user_id">Username</label>
        <div className="input-wrap">
          <UserRound size={17} />
          <input
            id="user_id"
            name="user_id"
            value={form.user_id}
            onChange={update}
            placeholder="4+ characters, letters or numbers"
            minLength={4}
            maxLength={150}
            autoComplete="username"
            required
          />
        </div>

        <label htmlFor="email">Email address</label>
        <div className="input-wrap">
          <Mail size={17} />
          <input
            id="email"
            name="email"
            type="email"
            value={form.email}
            onChange={update}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
        </div>

        <label htmlFor="password">Password</label>
        <div className="input-wrap">
          <LockKeyhole size={17} />
          <input
            id="password"
            name="password"
            type={show ? "text" : "password"}
            value={form.password}
            onChange={update}
            placeholder="At least 6 characters"
            minLength={6}
            autoComplete="new-password"
            required
          />
          <button type="button" className="icon-btn" onClick={() => setShow((v) => !v)}>
            {show ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        </div>

        <button className="primary-btn" disabled={busy || !!success}>
          {busy ? "Creating account…" : "Create account"} <ArrowRight size={17} />
        </button>
      </form>
      <div className="trust-line centered">
        An email verification link will be sent to your inbox.
      </div>
    </AuthLayout>
  );
}
