import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Compass } from "lucide-react";
import { api } from "../api";
import { useSession } from "../session";
import { Spinner } from "../components/ui";
import { Mark } from "../components/Mark";

// The demo area, Niphad in Nashik: the sign-in page opens on its real fields.
const NIPHAD: [number, number] = [20.08, 74.115];
const Z = 16, COLS = 6, ROWS = 4;

function tilesAround([lat, lon]: [number, number]) {
  const n = 2 ** Z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
  const out: string[] = [];
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS; c++)
      out.push(`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${Z}/${y - 2 + r}/${x - 3 + c}`);
  return out;
}

const STEPS = [
  ["Mark the land you look after", "Search your taluka, then draw around the farms or tap their fields."],
  ["FieldDx reads every clear pass", "Sentinel-2 imagery, field shapes and weather, for your land only."],
  ["Visit only where it matters", "Harvests and cloud are set aside. You get the few fields that need a call or a visit."],
];

export default function SignIn() {
  const { set } = useSession();
  const nav = useNavigate();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState<"" | "form" | "demo">("");
  const [error, setError] = useState("");

  const done = (m: Awaited<ReturnType<typeof api.me>>) => {
    set(m);
    nav(m.area ? "/" : "/setup", { replace: true });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("form");
    setError("");
    try {
      done(mode === "signin" ? await api.login({ username, pin }) : await api.register({ name, username, pin }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  };

  const demo = async () => {
    setBusy("demo");
    setError("");
    try {
      done(await api.demo());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  };

  const switchTo = (m: "signin" | "register") => { setMode(m); setError(""); };

  return (
    <main className="gate">
      <section className="gate-land" aria-labelledby="gate-h">
        <div className="gate-tiles" aria-hidden>
          {tilesAround(NIPHAD).map((src) => <img key={src} src={src} alt="" loading="eager" />)}
        </div>
        <div className="gate-shade" aria-hidden />
        <div className="gate-brand"><Mark size={28} /> FieldDx</div>
        <div className="gate-copy">
          <h1 id="gate-h">Know why a field changed before you drive out to it.</h1>
          <p>Satellites see a field lose its green. FieldDx works out the likely cause, rules out the rest, and names the one quick check that settles it.</p>
        </div>
        <ol className="gate-steps">
          {STEPS.map(([t, d], i) => (
            <li key={t}><span aria-hidden>{i + 1}</span><div><strong>{t}</strong><small>{d}</small></div></li>
          ))}
        </ol>
        <p className="gate-credit">Niphad, Nashik. Imagery © Esri, Maxar, Earthstar Geographics</p>
      </section>

      <section className="gate-panel" aria-label={mode === "signin" ? "Sign in" : "Create an account"}>
        <div className="gate-form">
          <h2>{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
          <p className="muted">{mode === "signin" ? "Your area and your open cases are where you left them." : "Next, you will mark the land you look after."}</p>

          {mode === "signin" && (
            <>
              <button type="button" className="gate-demo" onClick={demo} disabled={!!busy}>
                {busy === "demo" ? <Spinner size={18} /> : <Compass size={20} aria-hidden />}
                <span><strong>Try the demo area</strong><small>Niphad, Nashik. 150 real fields, no account needed.</small></span>
              </button>
              <div className="or"><span>or sign in</span></div>
            </>
          )}

          <form onSubmit={submit} className="signin-form">
            {mode === "register" && (
              <label className="field">
                <span className="caption">Your name</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required maxLength={60} />
              </label>
            )}
            <label className="field">
              <span className="caption">Username</span>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
                autoCapitalize="none" spellCheck={false} required maxLength={30} />
              {mode === "register" && <small className="muted">Letters, numbers, dots or dashes.</small>}
            </label>
            <label className="field">
              <span className="caption">PIN</span>
              <input className="input" type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
                autoComplete={mode === "signin" ? "current-password" : "new-password"} required minLength={4} maxLength={8} />
              {mode === "register" && <small className="muted">4 to 8 digits.</small>}
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={!!busy}>
              {busy === "form" ? <Spinner /> : null}
              {mode === "signin" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="gate-switch">
            {mode === "signin"
              ? <>New to FieldDx? <button type="button" className="linklike" onClick={() => switchTo("register")}>Create an account</button></>
              : <>Already have an account? <button type="button" className="linklike" onClick={() => switchTo("signin")}>Sign in</button></>}
          </p>
        </div>
      </section>
    </main>
  );
}
