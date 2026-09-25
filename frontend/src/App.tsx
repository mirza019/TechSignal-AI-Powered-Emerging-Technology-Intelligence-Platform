import { useEffect, useState, useRef, createContext, useContext } from "react";
import type { FormEvent } from "react";
import {
  NavLink,
  Routes,
  Route,
  Link,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  Radar,
  LayoutDashboard,
  Boxes,
  Radio,
  BookOpen,
  Building2,
  GraduationCap,
  Workflow,
  Files,
  Sparkles,
  Settings,
  Search,
  ArrowRight,
  LogOut,
  Menu,
  ShieldCheck,
  Activity,
  ChevronDown,
} from "lucide-react";
import { api, post, setToken } from "./api";
import type { User, Json } from "./types";
import { State } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import {
  Technologies,
  TechnologyProfile,
  RadarPage,
} from "./pages/Technologies";
import {
  SignalsPage,
  ResearchPage,
  OrganizationsPage,
  OrganizationProfile,
} from "./pages/Intelligence";
import {
  PipelinePage,
  ReportsPage,
  AskPage,
  SettingsPage,
  QualityPage,
} from "./pages/Operations";

const SessionContext = createContext<{
  user: User;
  settings: Json;
  refreshSettings: () => void;
}>({ user: {} as User, settings: {}, refreshSettings: () => {} });
export const useSession = () => useContext(SessionContext);
const nav = [
  [
    "WORKSPACE",
    [
      ["/", "Overview", LayoutDashboard],
      ["/radar", "Technology radar", Radar],
      ["/technologies", "Technologies", Boxes],
      ["/signals", "Signals", Radio],
    ],
  ],
  [
    "INTELLIGENCE",
    [
      ["/research", "Research", BookOpen],
      ["/startups", "Startups", Building2],
      ["/institutions", "Institutions", GraduationCap],
    ],
  ],
  [
    "TOOLS",
    [
      ["/pipeline", "Data pipeline", Workflow],
      ["/reports", "Reports & briefings", Files],
      ["/ask", "Ask intelligence AI", Sparkles],
    ],
  ],
] as const;

function Login({
  onLogin,
  authError,
}: {
  onLogin: (user: User) => void;
  authError: string;
}) {
  const [providers, setProviders] = useState<{
    microsoft: boolean;
    demo_available: boolean;
  } | null>(null);
  useEffect(() => {
    api<{ microsoft: boolean; demo_available: boolean }>("/auth/providers")
      .then((p) => {
        setProviders(p);
        if (p.demo_available) {
          setEmail("analyst@radar.local");
          setPassword("RadarDemo2026!");
        }
      })
      .catch(() =>
        setError(
          "Sign-in options could not be loaded. You can still use your local account.",
        ),
      );
  }, []);
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post("/auth/login", { email, password });
      setToken(result.access_token);
      onLogin(result.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <Radar size={28} />
          </span>
          <span>
            grid<span className="brand-light">radar</span>
          </span>
        </div>
        <div className="login-copy">
          <div className="eyebrow">TECHNOLOGY INTELLIGENCE, CONNECTED</div>
          <h1>
            A clearer view of
            <br />
            what comes next.
          </h1>
          <p>
            Connect emerging research, market signals and analyst insight to see
            the future of the grid.
          </p>
          <div className="login-rings">
            <i />
            <i />
            <i />
            <i />
            <span className="orbit-dot one" />
            <span className="orbit-dot two" />
            <span className="orbit-dot three" />
          </div>
        </div>
        <small>
          Portfolio horizon methodology — not Siemens Energy internal
          methodology.
        </small>
      </div>
      <div className="login-form-wrap">
        <form onSubmit={submit} className="login-form">
          <BadgeLabel />
          <h2>Welcome to Grid Radar</h2>
          <p>Your workspace for evidence-backed technology decisions.</p>
          <button
            type="button"
            className="button sso-button wide"
            disabled={!providers?.microsoft}
            onClick={() => {
              window.location.assign("/api/auth/sso/login");
            }}
          >
            <span className="microsoft-mark" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>{" "}
            Continue with Microsoft
          </button>
          {!providers?.microsoft && (
            <p className="sso-note">
              {providers
                ? "Microsoft SSO is ready to configure. Your administrator must connect an Entra tenant."
                : "Loading sign-in options…"}
            </p>
          )}
          <div className="login-divider">
            <span>or sign in with your workspace account</span>
          </div>
          <label>
            Email address
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <State error={error || authError} />
          <button className="button primary wide" disabled={busy}>
            {busy ? "Signing in…" : "Enter workspace"}
            <ArrowRight size={17} />
          </button>
          {providers?.demo_available && (
            <div className="demo-credentials">
              <strong>Explore the portfolio demo</strong>
              <p>
                Choose a role. All demo accounts use <code>RadarDemo2026!</code>
              </p>
              <div className="role-choices">
                {["Viewer", "Analyst", "Admin"].map((role) => (
                  <button
                    type="button"
                    key={role}
                    className={
                      email.startsWith(role.toLowerCase()) ? "selected" : ""
                    }
                    onClick={() => {
                      setEmail(`${role.toLowerCase()}@radar.local`);
                      setPassword("RadarDemo2026!");
                    }}
                  >
                    {role}
                  </button>
                ))}
              </div>
              <small>
                Sample records are synthetic and are not current market
                intelligence.
              </small>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
function BadgeLabel() {
  return (
    <span className="workspace-label">
      <span /> PORTFOLIO WORKSPACE
    </span>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [settings, setSettings] = useState<Json>({}),
    [menu, setMenu] = useState(false),
    [search, setSearch] = useState("");
  const initialized = useRef(false);
  const [authError, setAuthError] = useState("");
  const navigate = useNavigate(),
    location = useLocation();
  function refreshSettings() {
    api("/settings")
      .then(setSettings)
      .catch(() => {});
  }
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("sso_code");
    const failure = params.get("sso_error");
    if (code || failure)
      window.history.replaceState({}, "", window.location.pathname);
    if (failure)
      setAuthError(
        "Microsoft sign-in could not be completed. Please try again or contact your administrator.",
      );
    if (code) {
      post("/auth/sso/exchange", { code })
        .then((result) => {
          setToken(result.access_token);
          setUser(result.user);
          navigate("/", { replace: true });
        })
        .catch((e) => setAuthError((e as Error).message))
        .finally(() => setReady(true));
      return;
    }
    if (!sessionStorage.getItem("radar-token")) {
      setReady(true);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setToken(""))
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (user) refreshSettings();
  }, [user]);
  useEffect(() => {
    const handler = () => {
      setToken("");
      setUser(null);
    };
    window.addEventListener("radar-unauthorized", handler);
    return () => window.removeEventListener("radar-unauthorized", handler);
  }, []);
  useEffect(() => {
    setMenu(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  function signOut() {
    setToken("");
    setUser(null);
    setSettings({});
    setMenu(false);
    setAuthError("");
    navigate("/", { replace: true });
  }
  if (!ready) return <State loading />;
  if (!user) return <Login onLogin={setUser} authError={authError} />;
  return (
    <SessionContext.Provider value={{ user, settings, refreshSettings }}>
      <div className="app-shell">
        <aside className={`sidebar ${menu ? "open" : ""}`}>
          <Link to="/" className="brand">
            <span className="brand-icon">
              <Radar size={25} />
            </span>
            <span>
              grid<span className="brand-light">radar</span>
              <small>TECHNOLOGY INTELLIGENCE</small>
            </span>
          </Link>
          <div className="workspace-switch">
            <span className="workspace-logo">G</span>
            <div>
              Grid technologies<small>Portfolio workspace</small>
            </div>
            <ChevronDown size={14} />
          </div>
          <nav aria-label="Main navigation" tabIndex={0}>
            {nav.map(([heading, links]) => (
              <div className="nav-section" key={heading}>
                <div className="nav-label">{heading}</div>
                {links.map(([path, label, Icon]) => (
                  <NavLink key={path} to={path} end={path === "/"}>
                    <Icon size={18} />
                    {label}
                    {path === "/ask" && <span className="ai-mini">AI</span>}
                  </NavLink>
                ))}
              </div>
            ))}

            <NavLink to="/quality">
              <ShieldCheck size={17} /> Data quality
            </NavLink>
            <NavLink to="/settings">
              <Settings size={17} /> Settings
            </NavLink>
          </nav>
          <div className="sidebar-bottom">
            <div className="source-health">
              <span /> Evidence-first intelligence
              <small>
                {settings.is_demo
                  ? "Synthetic demo environment"
                  : "Public evidence environment"}
              </small>
            </div>
            <div className="user-card">
              <span className="avatar">
                {user.name
                  .split(" ")
                  .map((s) => s[0])
                  .join("")}
              </span>
              <span>
                {user.name}
                <small>{user.role}</small>
              </span>
            </div>
            <button className="button signout-button wide" onClick={signOut}>
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </aside>
        {menu && (
          <button
            className="nav-scrim"
            aria-label="Close navigation"
            onClick={() => setMenu(false)}
          />
        )}
        <div className="main-shell">
          <header className="topbar">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenu(!menu)}
              aria-label="Toggle navigation"
            >
              <Menu size={22} />
            </button>
            <div className="breadcrumb">
              Workspace <span>/</span>{" "}
              <strong>
                {location.pathname === "/"
                  ? "Overview"
                  : location.pathname.split("/")[1].replaceAll("-", " ")}
              </strong>
            </div>
            <form
              className="top-search"
              onSubmit={(e) => {
                e.preventDefault();
                navigate(`/technologies?q=${encodeURIComponent(search)}`);
              }}
            >
              <Search size={16} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search workspace"
                placeholder="Search intelligence…"
              />
              <kbd>↵</kbd>
            </form>
            <span className="environment-pill">
              <span />
              {settings.is_demo ? "Demo workspace" : "Live evidence"}
            </span>
            <button
              className="icon-button topbar-signout"
              onClick={signOut}
              aria-label="Sign out of workspace"
              title="Sign out"
            >
              <LogOut size={18} />
            </button>
          </header>
          <main>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/radar" element={<RadarPage />} />
              <Route path="/technologies" element={<Technologies />} />
              <Route path="/technologies/:id" element={<TechnologyProfile />} />
              <Route path="/signals" element={<SignalsPage />} />
              <Route path="/research" element={<ResearchPage />} />
              <Route
                path="/startups"
                element={<OrganizationsPage kind="startups" />}
              />
              <Route
                path="/institutions"
                element={<OrganizationsPage kind="institutions" />}
              />
              <Route
                path="/organizations/:id"
                element={<OrganizationProfile />}
              />
              <Route path="/pipeline" element={<PipelinePage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/ask" element={<AskPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/quality" element={<QualityPage />} />
              <Route
                path="*"
                element={
                  <div className="empty">
                    Page not found. <Link to="/">Return to overview</Link>
                  </div>
                }
              />
            </Routes>
          </main>
          <footer className="app-footer">
            <span>
              <Activity size={13} /> Portfolio horizon methodology — not Siemens
              Energy internal methodology.
            </span>
            <span>
              {settings.is_demo
                ? "All sample intelligence is synthetic."
                : "AI interpretation requires analyst review."}
            </span>
          </footer>
        </div>
      </div>
    </SessionContext.Provider>
  );
}
