import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "./api";
import { BigButton } from "./components";
import { CONNECTION, T, timeAgo } from "./lv";
import { History } from "./pages/History";
import { Home } from "./pages/Home";
import { MapPage } from "./pages/MapPage";
import { Settings } from "./pages/Settings";
import { useRobot } from "./useRobot";

type Tab = "home" | "map" | "history" | "settings";
const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "home", label: T.nav.home, icon: "⌂" },
  { id: "map", label: T.nav.map, icon: "▦" },
  { id: "history", label: T.nav.history, icon: "☰" },
  { id: "settings", label: T.nav.settings, icon: "⚙" },
];

function Login({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/api/login", { password });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās pieslēgties.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login">
      <h1>{T.loginTitle}</h1>
      <form onSubmit={(e) => void submit(e)}>
        <label className="field">
          {T.password}
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
        </label>
        {error && <p className="feedback feedback-error">{error}</p>}
        <button type="submit" className="big-button big-primary" disabled={busy || !password}>
          {T.login}
        </button>
      </form>
      <p className="help">Paroli iestatīja tas, kurš uzstādīja šo lietotni.</p>
    </main>
  );
}

export function App() {
  const [auth, setAuth] = useState<{ authenticated: boolean; auth_required: boolean } | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("home");
  const { status, link, refresh } = useRobot(Boolean(auth?.authenticated));

  const checkSession = useCallback(async () => {
    try {
      setAuth(await api.get("/api/session"));
      setAuthError(null);
    } catch (err) {
      setAuthError(err instanceof ApiError ? err.message : T.noConnectionServer);
    }
  }, []);

  useEffect(() => {
    void checkSession();
    const onLoggedOut = () => setAuth((a) => (a ? { ...a, authenticated: false } : a));
    window.addEventListener("deebot:logged-out", onLoggedOut);
    return () => window.removeEventListener("deebot:logged-out", onLoggedOut);
  }, [checkSession]);

  if (!auth) {
    return (
      <main className="center-screen">
        {authError ? (
          <>
            <p className="feedback feedback-error">{authError}</p>
            <BigButton label="Mēģināt vēlreiz" onClick={() => void checkSession()} />
          </>
        ) : (
          <p>{T.loading}</p>
        )}
      </main>
    );
  }
  if (!auth.authenticated) return <Login onDone={() => void checkSession()} />;

  const logout = async () => {
    await api.post("/api/logout").catch(() => undefined);
    setAuth({ ...auth, authenticated: false });
  };

  const robot = status?.robot;
  const linkText =
    link === "live" && robot?.backend_connected
      ? CONNECTION.live
      : link === "connecting"
        ? CONNECTION.connecting
        : CONNECTION.offline;

  return (
    <div className="app">
      <header className="topbar">
        <h1>{robot?.robot_name ?? T.appName}</h1>
        <span
          className={`link link-${link === "live" && robot?.backend_connected ? "live" : link}`}
          role="status"
          aria-label={`Savienojums: ${linkText}`}
        >
          ● {linkText}
        </span>
      </header>

      {robot?.demo && <div className="banner banner-demo">{T.demoBanner}</div>}
      {link === "offline" && (
        <div className="banner banner-error">
          {T.noConnectionServer}. Rādītie dati var būt novecojuši.
        </div>
      )}
      {status?.freshness.stale && link !== "offline" && (
        <div className="banner banner-warn" data-testid="stale-banner">
          <strong>{robot && !robot.robot_available ? T.noConnectionRobot : T.staleTitle}.</strong>{" "}
          {status.freshness.reason} Pēdējā ziņa: {timeAgo(robot?.last_update ?? null)}.
        </div>
      )}

      <main className="content">
        {!status ? (
          <div className="center-screen">
            <p>{T.loading}</p>
            <BigButton label="Atjaunot" variant="secondary" onClick={() => void refresh()} />
          </div>
        ) : tab === "home" ? (
          <Home status={status} onChooseRooms={() => setTab("map")} />
        ) : tab === "map" ? (
          <MapPage status={status} />
        ) : tab === "history" ? (
          <History />
        ) : (
          <Settings status={status} onLogout={() => void logout()} authRequired={auth.auth_required} />
        )}
      </main>

      <nav className="tabbar" aria-label="Galvenā izvēlne">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "active" : ""}
            aria-current={tab === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            <span className="tab-icon" aria-hidden="true">{t.icon}</span>
            <span className="tab-label">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
