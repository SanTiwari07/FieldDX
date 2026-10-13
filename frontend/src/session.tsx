import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, Me, SESSION_EVENT } from "./api";

interface SessionValue {
  me: Me | null;
  loading: boolean;
  set: (me: Me | null) => void;
  refresh: () => Promise<Me | null>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<SessionValue | null>(null);

/** Who is signed in and which area they work in. Everything after sign-in hangs off this. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const m = await api.me();
      setMe(m);
      return m;
    } catch {
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // a 401 or 409 while signed in means the session or the area changed under us: re-read it once
  const signedIn = useRef(false);
  signedIn.current = me !== null;
  useEffect(() => {
    const on = () => { if (signedIn.current) void refresh(); };
    window.addEventListener(SESSION_EVENT, on);
    return () => window.removeEventListener(SESSION_EVENT, on);
  }, [refresh]);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setMe(null);
  }, []);

  return <Ctx.Provider value={{ me, loading, set: setMe, refresh, signOut }}>{children}</Ctx.Provider>;
}

export function useSession(): SessionValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession outside SessionProvider");
  return v;
}
