import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { Eye, EyeOff, ArrowRight, UserRound, LockKeyhole } from 'lucide-react';
import AuthLayout from '../components/AuthLayout';
import api, { resetExpiryNotice } from '../app/api';
import { setCredentials, setUser } from '../features/auth/authSlice';
export default function Login() {
 const [form,setForm]=useState({userId:'',password:''}); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
 const dispatch=useDispatch(), navigate=useNavigate(), location=useLocation();
 const update=e=>setForm({...form,[e.target.name]:e.target.value});
 const submit=async e=>{e.preventDefault();setError('');setBusy(true);try{const {data}=await api.post('/login/',{...form,platform:'web'});dispatch(setCredentials({access:data.access,user:data.user}));dispatch(setUser(data.user));sessionStorage.setItem('authflow-had-session','1');resetExpiryNotice();navigate('/',{replace:true});}catch(err){const d=err.response?.data?.detail;setError(typeof d==='string'?d:(d?.user_id||d?.email||'Unable to sign in. Please check your details.'));}finally{setBusy(false);}};
 return <AuthLayout title="Welcome back" subtitle="Sign in to continue to your secure workspace." footer={<>New to AuthFlow? <Link to="/register">Create an account <ArrowRight size={13}/></Link></>}>
 {location.state?.message && <div className="success-alert">{location.state.message}</div>}{error&&<div className="error-alert">{error}</div>}
 <form onSubmit={submit} className="auth-form"><label htmlFor="userId">Username</label><div className="input-wrap"><UserRound size={17}/><input id="userId" name="userId" value={form.userId} onChange={update} placeholder="Enter your username" autoComplete="username" required/></div><div className="label-row"><label htmlFor="password">Password</label><Link to="/forgot-password">Forgot password?</Link></div><div className="input-wrap"><LockKeyhole size={17}/><input id="password" name="password" type={show?'text':'password'} value={form.password} onChange={update} placeholder="Enter your password" autoComplete="current-password" required/><button type="button" className="icon-btn" onClick={()=>setShow(!show)} aria-label={show?'Hide password':'Show password'}>{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div><button className="primary-btn" disabled={busy}>{busy?'Signing in…':'Sign in securely'} <ArrowRight size={17}/></button></form>
 <div className="form-divider"><span/> <small>SECURE AUTHENTICATION</small> <span/></div><div className="trust-line">Protected with JWT access tokens and HttpOnly refresh cookies.</div>
 </AuthLayout>;
}
