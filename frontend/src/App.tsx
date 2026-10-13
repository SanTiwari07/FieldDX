import { lazy, ReactNode, Suspense, useEffect, useRef, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, MapPin, MapPinned, RotateCcw } from "lucide-react";
import { api } from "./api";
import { useSession } from "./session";
import SignIn from "./pages/SignIn";
import { Spinner } from "./components/ui";

// each step of the flow loads when the officer reaches it; sign-in stays light
const Setup = lazy(() => import("./pages/Setup"));
const Home = lazy(() => import("./pages/Home"));
const Inbox = lazy(() => import("./pages/Inbox"));
const CasePage = lazy(() => import("./pages/Case"));
const Checklist = lazy(() => import("./pages/Checklist"));

const Loading = () => <main className="page"><div className="center-spin"><Spinner size={22} /></div></main>;

function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="currentColor" />
      <g fill="#fff">
        {[0, 1, 2].flatMap((r) =>
          [0, 1, 2].map((c) => (
            <rect key={`${r}${c}`} x={6 + c * 7} y={6 + r * 7} width="6" height="6" rx="1" opacity={r === 1 && c === 1 ? 1 : 0.45} />
          )),
        )}
      </g>
    </svg>
  );
}

function OfficerMenu() {
  const { me, set, signOut } = useSession();
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  if (!me) return null;
  const ready = me.area?.status === "ready";

  const changeArea = async () => {
    setOpen(false);
    set(await api.joinArea(null));
    nav("/setup");
  };
  const reset = async () => {
    setOpen(false);
    await api.reset();
    window.location.assign(loc.pathname.startsWith("/case") ? "/cases" : loc.pathname);
  };
  const out = async () => {
    setOpen(false);
    await signOut();
    nav("/signin", { replace: true });
  };

  return (
    <div className="menu" ref={box}>
      <button type="button" className="menu-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="avatar" aria-hidden>{me.officer.name.slice(0, 1).toUpperCase()}</span>
        <span className="menu-name">{me.officer.name}</span>
        <ChevronDown size={14} aria-hidden />
      </button>
      {open && (
        <div className="menu-pop" role="menu">
          <div className="menu-who"><strong>{me.officer.name}</strong><small>@{me.officer.username}</small></div>
          {!me.officer.demo && <button type="button" role="menuitem" onClick={changeArea}><MapPinned size={14} aria-hidden /> Change area</button>}
          {ready && <button type="button" role="menuitem" onClick={reset} title="Reopen closed cases and clear stored narratives in this area"><RotateCcw size={14} aria-hidden /> Reset closed cases</button>}
          <button type="button" role="menuitem" onClick={out}><LogOut size={14} aria-hidden /> Sign out</button>
        </div>
      )}
    </div>
  );
}

function AppBar() {
  const { me } = useSession();
  const area = me?.area;
  const ready = area?.status === "ready";
  return (
    <header className="appbar">
      <div className="appbar-inner">
        <Link to={me ? "/" : "/signin"} className="wordmark" aria-label="FieldDx home">
          <Mark />
          <span>FieldDx</span>
        </Link>
        {ready && (
          <nav className="appnav" aria-label="Main">
            <NavLink to="/" end>Today</NavLink>
            <NavLink to="/cases">Cases</NavLink>
          </nav>
        )}
        {!me && <span className="appbar-tag">Differential diagnosis for farm fields</span>}
        <span className="appbar-spacer" />
        {area && (
          <span className="area-chip" title={area.region}>
            <MapPin size={13} aria-hidden /> {area.name}{ready && area.fields ? <small>{area.fields} fields</small> : <small>{area.status === "ready" ? "" : "setting up"}</small>}
          </span>
        )}
        <OfficerMenu />
      </div>
    </header>
  );
}

/** Signed in, with an area that is ready: otherwise send the officer to the step they are on. */
function Gate({ need, children }: { need: "session" | "area" | "ready"; children: ReactNode }) {
  const { me, loading } = useSession();
  const loc = useLocation();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/signin" replace state={{ from: loc.pathname }} />;
  if (need !== "session" && !me.area) return <Navigate to="/setup" replace />;
  if (need === "ready" && me.area?.status !== "ready") return <Navigate to="/" replace />;
  return <Suspense fallback={<Loading />}>{children}</Suspense>;
}

function SignInRoute() {
  const { me, loading } = useSession();
  if (loading) return null;
  if (me) return <Navigate to={me.area ? "/" : "/setup"} replace />;
  return <SignIn />;
}

export default function App() {
  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <AppBar />
      <div id="main">
        <Routes>
          <Route path="/signin" element={<SignInRoute />} />
          <Route path="/setup" element={<Gate need="session"><Setup /></Gate>} />
          <Route path="/" element={<Gate need="area"><Home /></Gate>} />
          <Route path="/cases" element={<Gate need="ready"><Inbox /></Gate>} />
          <Route path="/case/:id" element={<Gate need="ready"><CasePage /></Gate>} />
          <Route path="/case/:id/check" element={<Gate need="ready"><Checklist /></Gate>} />
          <Route path="*" element={<main className="page"><p>Page not found. <Link to="/">Back to today</Link></p></main>} />
        </Routes>
      </div>
    </>
  );
}
