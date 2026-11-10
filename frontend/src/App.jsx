import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { ShieldCheck, LogOut, LayoutDashboard, UserRound, Clock3 } from 'lucide-react';
import api, { logoutRequest, resetExpiryNotice } from './app/api';
import { setCredentials, setUser, setInitialized, setSessionExpired, clearSession } from './features/auth/authSlice';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import SessionExpiredModal from './components/SessionExpiredModal';

function Protected({ children }) {
  const { accessToken, initialized } = useSelector(s => s.auth);
  if (!initialized) return <div className="screen-loader"><span className="loader"/>Checking your session…</div>;
  return accessToken ? children : <Navigate to="/login" replace />;
}
function Shell({ children }) {
  const user = useSelector(s => s.auth.user);
  const navigate = useNavigate();
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-icon"><ShieldCheck size={21}/></span><span>Auth<span className="brand-accent">Flow</span></span></div><div className="nav-label">WORKSPACE</div><div className="nav-item active"><LayoutDashboard size={17}/> Overview</div><div className="nav-item"><UserRound size={17}/> Account</div><div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={17}/><span>Protected session<br/><small>JWT authentication</small></span></div><button className="logout-link" onClick={async()=>{await logoutRequest();navigate('/login',{replace:true});}}><LogOut size={17}/> Sign out</button></div></aside><main className="main-area"><header className="topbar"><div><span className="eyebrow">ACCOUNT CENTER</span><div className="topbar-title">Your workspace</div></div><div className="avatar-wrap"><div className="avatar">{(user?.userId || 'U').slice(0,1).toUpperCase()}</div><div><strong>{user?.userId || 'Account'}</strong><small>{user?.email || ''}</small></div></div></header>{children}</main></div>;
}
export default function App() {
  const dispatch = useDispatch();
  const { sessionExpired, initialized } = useSelector(s => s.auth);
  const location = useLocation();
  const navigate = useNavigate();
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const hadSession = sessionStorage.getItem('authflow-had-session') === '1';
      try {
        const { data } = await api.post('/token/refresh/', { platform: 'web' });
        if (!active) return;
        dispatch(setCredentials({ access: data.access }));
        sessionStorage.setItem('authflow-had-session', '1');
        try { const me = await api.get('/authenticated/'); if (active) dispatch(setUser(me.data.user)); } catch { /* access refresh may be valid; API interceptor handles retries */ }
      } catch {
        if (active) {
          dispatch(clearSession());
          if (hadSession) dispatch(setSessionExpired());
        }
      } finally { if (active) { dispatch(setInitialized()); setBooting(false); } }
    })();
    return () => { active = false; };
  }, [dispatch]);

  const closeExpired = async () => {
    await logoutRequest();
    sessionStorage.removeItem('authflow-had-session');
    resetExpiryNotice();
    navigate('/login', { replace: true, state: { message: 'Your session has expired. Please sign in again.' } });
  };
  useEffect(() => { if (location.pathname === '/login' && location.state?.message) window.history.replaceState({}, document.title); }, [location]);
  if (booting && !initialized) return <div className="screen-loader"><span className="loader"/>Securing your session…</div>;
  return <>
    <Routes>
      <Route path="/login" element={<Login/>}/>
      <Route path="/register" element={<Register/>}/>
      <Route path="/forgot-password" element={<ForgotPassword/>}/>
      <Route path="/" element={<Protected><Shell><Dashboard/></Shell></Protected>}/>
      <Route path="*" element={<Navigate to="/" replace/>}/>
    </Routes>
    {sessionExpired && <SessionExpiredModal onContinue={closeExpired}/>}
  </>;
}
