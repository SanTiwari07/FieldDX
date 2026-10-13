import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Compass, LocateFixed, MapPinned, Satellite, Stethoscope } from "lucide-react";
import { api } from "../api";
import { useSession } from "../session";
import { Spinner } from "../components/ui";

const FLOW = [
  { Icon: MapPinned, title: "Mark your area", text: "Pick the district you work in, then draw it, type its coordinates, or tap the fields on the Fields of the World map." },
  { Icon: Satellite, title: "FieldDx builds it from real data", text: "Field shapes, a year of Sentinel-2 passes with clouds masked, and the weather, for that area only." },
  { Icon: Stethoscope, title: "Each alert is investigated", text: "False alarms are thrown out with a reason. What is left is ranked, with the evidence for and against." },
  { Icon: LocateFixed, title: "One cheapest check per field", text: "Go, check, record what you found. The finding becomes evidence and the ranking updates." },
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

  return (
    <main className="signin">
      <section className="signin-card" aria-labelledby="signin-h">
        <div className="seg signin-tabs" role="tablist" aria-label="Sign in or create an account">
          <button type="button" role="tab" aria-selected={mode === "signin"} className={mode === "signin" ? "on" : ""} onClick={() => { setMode("signin"); setError(""); }}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "on" : ""} onClick={() => { setMode("register"); setError(""); }}>Create account</button>
        </div>
        <h1 id="signin-h">{mode === "signin" ? "Welcome back" : "Set up your FieldDx account"}</h1>
        <p className="lede">{mode === "signin" ? "Your area and your open cases are where you left them." : "Next you will mark the area you look after."}</p>
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
            {mode === "signin" ? "Sign in" : "Create account"} <ArrowRight size={15} aria-hidden />
          </button>
        </form>
        <div className="or"><span>or</span></div>
        <button type="button" className="btn btn-outline demo-btn" onClick={demo} disabled={!!busy}>
          {busy === "demo" ? <Spinner /> : <Compass size={16} aria-hidden />}
          <span>Explore the demo area <small>Niphad, Nashik · 150 real fields</small></span>
        </button>
      </section>

      <section className="signin-story" aria-labelledby="story-h">
        <div className="eyebrow">Differential diagnosis for farm fields</div>
        <h2 id="story-h">Satellites tell you <em>that</em> a field changed. FieldDx tells you what probably happened, what it definitely wasn't, and the one cheapest check that settles it.</h2>
        <ol className="flow-list">
          {FLOW.map(({ Icon, title, text }, i) => (
            <li key={title}>
              <span className="flow-num" aria-hidden>{i + 1}</span>
              <div>
                <strong><Icon size={15} aria-hidden /> {title}</strong>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
