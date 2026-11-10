import { Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { LogOut, ShieldCheck } from "lucide-react";
import { logoutRequest } from "../app/api";
import { setLoading } from "../features/auth/authSlice";

export default function Navbar() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { user, isLoading } = useSelector((state) => state.auth);

  const handleLogout = async () => {
    dispatch(setLoading(true));
    await logoutRequest();
    dispatch(setLoading(false));
    navigate("/login", {
      replace: true,
      state: { message: "You have been logged out successfully." },
    });
  };

  return (
    <header className="app-navbar">
      <div className="app-navbar-inner">
        <Link to="/dashboard" className="brand">
          <span className="brand-icon"><ShieldCheck size={19} /></span>
          <span>Auth<span className="brand-accent">Flow</span></span>
        </Link>
        <div className="app-navbar-right">
          <span className="navbar-welcome">Welcome, {user?.userId || "User"}</span>
          <button
            type="button"
            className="logout-btn"
            onClick={handleLogout}
            disabled={isLoading}
          >
            <LogOut size={15} />
            {isLoading ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}
