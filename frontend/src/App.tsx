import { Link, Route, Routes, useLocation } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { api } from "./api";
import Inbox from "./pages/Inbox";
import CasePage from "./pages/Case";
import Checklist from "./pages/Checklist";

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

function AppBar() {
  const loc = useLocation();
  const reset = async () => {
    await api.reset();
    window.location.assign(loc.pathname.startsWith("/case") ? "/" : loc.pathname);
  };
  return (
    <header className="appbar">
      <div className="appbar-inner">
        <Link to="/" className="wordmark" aria-label="FieldDx, back to the inbox">
          <Mark />
          <span>FieldDx</span>
        </Link>
        <span className="appbar-tag">Differential diagnosis for farm fields</span>
        <span className="appbar-spacer" />
        <span className="appbar-meta">Niphad cluster · 12 plots</span>
        <button type="button" className="btn btn-ghost" onClick={reset} title="Clear closed cases and stored narratives so the demo starts clean">
          <RotateCcw size={14} aria-hidden /> Reset demo
        </button>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <AppBar />
      <div id="main">
        <Routes>
          <Route path="/" element={<Inbox />} />
          <Route path="/case/:id" element={<CasePage />} />
          <Route path="/case/:id/check" element={<Checklist />} />
          <Route path="*" element={<main className="page"><p>Page not found. <Link to="/">Back to the inbox</Link></p></main>} />
        </Routes>
      </div>
    </>
  );
}
