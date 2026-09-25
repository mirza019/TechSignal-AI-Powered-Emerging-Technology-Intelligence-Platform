import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Play,
  RefreshCw,
  CheckCircle2,
  Circle,
  AlertCircle,
  Clock3,
  Download,
  Plus,
  Sparkles,
  ArrowUp,
  FileText,
  ShieldCheck,
  Save,
} from "lucide-react";
import { useApi } from "../hooks";
import { api, post, put, download } from "../api";
import { useSession } from "../App";
import type { Json, Technology } from "../types";
import { date } from "../types";
import {
  PageHeading,
  Panel,
  State,
  Badge,
  Empty,
  Modal,
  EvidenceList,
  HorizonBadge,
} from "../components/ui";

export function PipelinePage() {
  const {
      data: runs,
      error,
      loading,
      refresh,
    } = useApi<Json[]>("/pipeline/runs"),
    { data: technologies } = useApi<Technology[]>("/technologies"),
    { user, settings } = useSession(),
    [selected, setSelected] = useState(""),
    [detail, setDetail] = useState<Json | null>(null),
    [provider, setProvider] = useState("demo"),
    [technology, setTechnology] = useState(""),
    [limit, setLimit] = useState(10),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState("");
  useEffect(() => {
    if (runs?.length && !selected) setSelected(runs[0].id);
  }, [runs, selected]);
  useEffect(() => {
    if (selected)
      api(`/pipeline/runs/${selected}`)
        .then(setDetail)
        .catch((e) => setActionError(e.message));
  }, [selected, runs]);
  useEffect(() => {
    if (!runs?.some((r) => ["Pending", "Running"].includes(r.status))) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [runs, refresh]);
  useEffect(
    () => setProvider(settings.is_demo ? "demo" : "openalex"),
    [settings.is_demo],
  );
  async function run(retry = false) {
    setBusy(true);
    setActionError("");
    try {
      const result = await post(
        retry ? `/pipeline/runs/${selected}/retry` : "/pipeline/run",
        retry ? {} : { provider, technology_id: technology || null, limit },
      );
      setSelected(result.id);
      refresh();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="DATA OPERATIONS"
        title="Intelligence pipeline"
        description="From public sources to validated, traceable technology intelligence."
        actions={
          <button className="button" onClick={refresh}>
            <RefreshCw size={15} /> Refresh
          </button>
        }
      />
      <div className="notice">
        <ShieldCheck size={17} /> Staged ingestion → quality gate → atomic
        merge. Failed runs preserve the previous valid database state.
      </div>
      {user.role === "Admin" && (
        <div className="toolbar">
          <select
            aria-label="Provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            {(settings.is_demo ? ["demo"] : ["openalex", "gdelt", "web"]).map(
              (p) => (
                <option key={p}>{p}</option>
              ),
            )}
          </select>
          <select
            aria-label="Technology for ingestion"
            value={technology}
            onChange={(e) => setTechnology(e.target.value)}
          >
            <option value="">All technologies</option>
            {technologies?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <label className="inline-label">
            Limit per technology
            <input
              aria-label="Record limit"
              type="number"
              value={limit}
              min={1}
              max={100}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </label>
          <button
            className="button primary"
            disabled={busy}
            onClick={() => run()}
          >
            <Play size={15} />
            {busy ? "Starting…" : "Run pipeline"}
          </button>
        </div>
      )}
      <State error={error || actionError} loading={loading} />
      <div className="pipeline-grid">
        <Panel
          title="Pipeline runs"
          subtitle={`${settings.scheduler_enabled ? "Scheduled jobs enabled" : "Scheduler disabled"} · UTC`}
        >
          <div className="run-list">
            {runs?.map((r) => (
              <button
                className={selected === r.id ? "active" : ""}
                key={r.id}
                onClick={() => setSelected(r.id)}
              >
                <div>
                  <strong>{r.provider} ingestion</strong>
                  <Badge
                    tone={
                      r.status === "Successful"
                        ? "green"
                        : r.status === "Failed"
                          ? "red"
                          : "amber"
                    }
                  >
                    {r.status}
                  </Badge>
                </div>
                <small>
                  {date(r.created_at)} · {r.id.slice(0, 8)} · Retry{" "}
                  {r.retry_count}
                </small>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title="Run execution"
          subtitle={
            detail
              ? `${detail.id} · ${detail.provider}`
              : "Select a pipeline run"
          }
          action={
            detail?.status === "Failed" &&
            user.role === "Admin" && (
              <button
                className="button small"
                disabled={busy}
                onClick={() => run(true)}
              >
                <RefreshCw size={14} /> Retry failed run
              </button>
            )
          }
        >
          {detail?.error && <div className="error">{detail.error}</div>}
          <div className="pipeline-steps">
            {detail?.steps.map((step: Json) => {
              const Icon =
                step.status === "Successful"
                  ? CheckCircle2
                  : step.status === "Failed"
                    ? AlertCircle
                    : step.status === "Running"
                      ? Clock3
                      : Circle;
              return (
                <div
                  className={`pipeline-step ${step.status.toLowerCase()}`}
                  key={step.id}
                >
                  <span className="step-icon">
                    <Icon size={20} />
                  </span>
                  <div>
                    <div className="step-title">
                      <h3>{step.name}</h3>
                      <Badge
                        tone={
                          step.status === "Successful"
                            ? "green"
                            : step.status === "Failed"
                              ? "red"
                              : ""
                        }
                      >
                        {step.status}
                      </Badge>
                    </div>
                    <p>
                      {step.processed} processed · {step.inserted} inserted ·{" "}
                      {step.updated} matched / updated · {step.rejected}{" "}
                      rejected
                    </p>
                    <small>
                      {step.started_at
                        ? new Date(step.started_at).toLocaleTimeString()
                        : "Not started"}{" "}
                      →{" "}
                      {step.ended_at
                        ? new Date(step.ended_at).toLocaleTimeString()
                        : "—"}{" "}
                      · Retry {step.retry_count}
                    </small>
                    {step.error && <div className="step-log">{step.error}</div>}
                  </div>
                </div>
              );
            })}
          </div>
          {!detail && <Empty>No run selected.</Empty>}
        </Panel>
      </div>
    </>
  );
}

export function ReportsPage() {
  const { data, error, loading, refresh } = useApi<Json[]>("/reports"),
    { data: technologies } = useApi<Technology[]>("/technologies"),
    { data: startups } = useApi<Json[]>("/startups"),
    { data: institutions } = useApi<Json[]>("/institutions"),
    { user } = useSession(),
    [modal, setModal] = useState(false),
    [kind, setKind] = useState("Weekly Technology Intelligence Report"),
    [subject, setSubject] = useState(""),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState(""),
    [preview, setPreview] = useState<Json | null>(null);
  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      await post("/reports/generate", {
        kind,
        technology_id:
          kind === "Technology Opportunity Report" ? subject : null,
        organization_id: kind.includes("Briefing") ? subject : null,
      });
      setModal(false);
      refresh();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function exportFile(id: string, format: "pdf" | "md") {
    try {
      await download(id, format);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }
  const subjects =
    kind === "Technology Opportunity Report"
      ? technologies
      : kind === "Startup Briefing"
        ? startups
        : institutions;
  return (
    <>
      <PageHeading
        eyebrow="DECISION SUPPORT"
        title="Reports & briefings"
        description="Turn traceable intelligence into a focused conversation or opportunity profile."
        actions={
          user.role !== "Viewer" && (
            <button className="button primary" onClick={() => setModal(true)}>
              <Plus size={16} /> Generate report
            </button>
          )
        }
      />
      <State error={error || actionError} loading={loading} />
      {data?.length ? (
        <div className="report-grid">
          {data.map((r) => (
            <article className="report-card" key={r.id}>
              <span className="report-icon">
                <FileText size={25} />
              </span>
              <Badge>{r.kind}</Badge>
              <h2>{r.title.split(" · ")[1] || r.title}</h2>
              <p>
                {r.evidence_ids.length} source references · {date(r.created_at)}
              </p>
              {r.is_demo && (
                <small>Synthetic demo evidence · Pending analyst review</small>
              )}
              <div className="report-actions">
                <button className="button small" onClick={() => setPreview(r)}>
                  Read report
                </button>
                <button
                  className="button small"
                  onClick={() => exportFile(r.id, "pdf")}
                >
                  <Download size={14} /> PDF
                </button>
                <button
                  className="button small"
                  onClick={() => exportFile(r.id, "md")}
                >
                  MD
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        !loading && (
          <Empty>
            No reports yet. Generate a weekly briefing or open a technology
            profile to create an opportunity report.
          </Empty>
        )
      )}
      {modal && (
        <Modal
          title="Generate evidence-backed report"
          onClose={() => setModal(false)}
        >
          <form className="form-grid" onSubmit={generate}>
            <label>
              Report type
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setSubject("");
                }}
              >
                {[
                  "Weekly Technology Intelligence Report",
                  "Monthly Technology Radar Update",
                  "Technology Opportunity Report",
                  "Startup Briefing",
                  "Research Institution Briefing",
                ].map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </label>
            {(kind.includes("Briefing") ||
              kind === "Technology Opportunity Report") && (
              <label>
                Subject
                <select
                  required
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                >
                  <option value="">Select a subject</option>
                  {subjects?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <p>
              Uses a bounded evidence bundle. With no Gemini key, a clearly
              labelled deterministic briefing is generated.
            </p>
            <State error={actionError} />
            <button className="button primary" disabled={busy}>
              <Sparkles size={15} />
              {busy ? "Generating…" : "Generate report"}
            </button>
          </form>
        </Modal>
      )}
      {preview && (
        <Modal title={preview.title} onClose={() => setPreview(null)}>
          <article className="markdown-preview">
            {preview.markdown
              .split("\n\n")
              .map((line: string, i: number) =>
                line.startsWith("#") ? (
                  <h3 key={i}>{line.replace(/^#+ /, "")}</h3>
                ) : (
                  <p key={i}>{line}</p>
                ),
              )}
          </article>
        </Modal>
      )}
    </>
  );
}

export function AskPage() {
  const [query, setQuery] = useState(""),
    [messages, setMessages] = useState<Json[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [technology, setTechnology] = useState(""),
    { data: technologies } = useApi<Technology[]>("/technologies"),
    { settings } = useSession();
  async function ask(text = query) {
    if (text.trim().length < 3) return;
    setBusy(true);
    setError("");
    setQuery("");
    setMessages((m) => [...m, { role: "user", text }]);
    try {
      const result = await post("/ai/query", {
        query: text,
        technology_id: technology || null,
      });
      setMessages((m) => [...m, { role: "assistant", ...result }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE-GROUNDED ASSISTANT"
        title="Ask technology intelligence"
        description="Explore your collected evidence. Keep facts, interpretation and uncertainty separate."
      />
      <div className="ask-layout">
        <Panel
          title="Intelligence conversation"
          action={
            <Badge tone={settings.providers?.gemini ? "purple" : "amber"}>
              {settings.providers?.gemini
                ? "Gemini connected"
                : "Evidence retrieval mode"}
            </Badge>
          }
        >
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="chat-welcome">
                <span className="ask-icon">
                  <Sparkles size={30} />
                </span>
                <h2>
                  Start with a question.
                  <br />
                  Follow the evidence.
                </h2>
                <p>
                  Search across your technology portfolio with source references
                  attached to every response.
                </p>
                <div className="suggestions">
                  {[
                    "Summarize developments in grid-forming converters.",
                    "Which institutions research solid-state transformers?",
                    "What evidence supports SF6-free switchgear?",
                    "Compare research and commercial activity.",
                  ].map((q) => (
                    <button key={q} onClick={() => ask(q)}>
                      {q}
                      <ArrowUp size={15} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`chat-message ${m.role}`}>
                  {m.role === "user" ? (
                    <p>{m.text}</p>
                  ) : (
                    <>
                      <Badge tone="purple">
                        {m.model === "deterministic-evidence-summary"
                          ? "Retrieved evidence · No LLM synthesis"
                          : "AI interpretation · Not analyst-approved"}
                      </Badge>
                      <h3>Facts from retrieved records</h3>
                      <ul>
                        {m.facts.map((f: string, j: number) => (
                          <li key={j}>{f}</li>
                        ))}
                      </ul>
                      <h3>Interpretation</h3>
                      <p>{m.interpretation}</p>
                      <h3>Uncertainties</h3>
                      <ul>
                        {m.uncertainties.map((f: string, j: number) => (
                          <li key={j}>{f}</li>
                        ))}
                      </ul>
                      <details>
                        <summary>
                          {m.sources.length} clickable evidence sources
                        </summary>
                        <EvidenceList records={m.sources} />
                      </details>
                    </>
                  )}
                </div>
              ))
            )}
            {busy && <State loading />}
            <State error={error} />
          </div>
          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <select
              aria-label="AI technology scope"
              value={technology}
              onChange={(e) => setTechnology(e.target.value)}
            >
              <option value="">Entire portfolio</option>
              {technologies?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <div>
              <textarea
                aria-label="Ask a question"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask about technologies, research or signals…"
                rows={2}
                maxLength={2000}
              />
              <button
                className="button primary"
                disabled={busy || query.trim().length < 3}
                aria-label="Send question"
              >
                <ArrowUp size={20} />
              </button>
            </div>
            <small>
              Only relevant evidence enters the model context. Unsupported
              evidence IDs are rejected.
            </small>
          </form>
        </Panel>
      </div>
    </>
  );
}

export function SettingsPage() {
  const { settings, refreshSettings, user } = useSession(),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(""),
    [editing, setEditing] = useState<Json | null>(null),
    [busy, setBusy] = useState(false);
  async function saveHorizon(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      await put(`/settings/horizons/${editing.id}`, {
        name: f.get("name"),
        description: f.get("description"),
        years: f.get("years"),
        min_maturity: Number(f.get("min_maturity")),
        display_order: Number(f.get("display_order")),
        score_rules: JSON.parse(String(f.get("rules"))),
      });
      setEditing(null);
      refreshSettings();
      setSaved(
        "Portfolio methodology updated. Existing analyst placements are unchanged.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveWeights(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      await put(
        "/settings/weights",
        Object.fromEntries(
          Object.entries(settings.score_weights).map(([k]) => [
            k,
            Number(f.get(k)),
          ]),
        ),
      );
      refreshSettings();
      setSaved("Weights saved and scores recalculated.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE CONFIGURATION"
        title="Settings & methodology"
        description="Make the portfolio framework explicit, configurable and auditable."
      />
      <div className="notice">
        H1–H4 horizons, score weights and signal thresholds are configurable.
      </div>
      <State error={error} />
      {saved && <div className="success">{saved}</div>}
      <Panel
        title="Active dataset"
        subtitle="Synthetic and retrieved records remain separate. Changing the view never deletes data."
      >
        <div className="prose">
          <Badge tone={settings.is_demo ? "amber" : "green"}>
            {settings.is_demo
              ? "Synthetic demonstration"
              : "Retrieved public intelligence"}
          </Badge>
          {user.role === "Admin" && (
            <button
              className="button"
              style={{ marginLeft: 16 }}
              onClick={async () => {
                try {
                  await put("/settings/data-mode", {
                    is_demo: !settings.is_demo,
                  });
                  refreshSettings();
                  setSaved(
                    "Dataset switched. Open a page to explore its records.",
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Switch to {settings.is_demo ? "public evidence" : "sample data"}
            </button>
          )}
        </div>
      </Panel>
      <Panel
        title="H1–H4 portfolio horizons"
        subtitle="Suggested horizons use configurable maturity thresholds. Analyst approval remains required."
      >
        <div className="horizon-settings">
          {settings.horizons?.map((h: Json) => (
            <div key={h.id}>
              <HorizonBadge value={h.id} />
              <h3>{h.name}</h3>
              <small>
                {h.years} · Maturity ≥ {h.min_maturity}
              </small>
              <p>{h.description}</p>
              {user.role === "Admin" && (
                <button
                  className="button small"
                  onClick={() => {
                    setError("");
                    setEditing(h);
                  }}
                >
                  Edit definition
                </button>
              )}
            </div>
          ))}
        </div>
      </Panel>
      <div className="two-columns">
        <Panel
          title="Transparent score weights"
          subtitle="Weights must total 1.00"
        >
          <form className="form-grid" onSubmit={saveWeights}>
            {Object.entries(settings.score_weights || {}).map(
              ([key, value]) => (
                <label key={key} className="weight-input">
                  {key}
                  <input
                    type="number"
                    name={key}
                    min="0"
                    max="1"
                    step="0.01"
                    defaultValue={Number(value)}
                    disabled={user.role !== "Admin"}
                  />
                </label>
              ),
            )}
            {user.role === "Admin" && (
              <button className="button primary" disabled={busy}>
                <Save size={15} /> Save weights
              </button>
            )}
          </form>
        </Panel>
        <Panel
          title="Provider connections"
          subtitle="Credentials are environment variables and never returned to the browser."
        >
          <div className="provider-list">
            {Object.entries(settings.providers || {}).map(([key, value]) => (
              <div key={key}>
                <strong>{key.replaceAll("_", " ")}</strong>
                <Badge tone={value ? "green" : ""}>
                  {value
                    ? "Configured / enabled"
                    : key === "epo"
                      ? "Future adapter"
                      : "Not configured"}
                </Badge>
              </div>
            ))}
          </div>
          <p className="muted">
            OpenAlex may support requests without a key within provider limits.
            EPO is reserved for a later integration.
          </p>
          <p className="muted">{settings.embedding_model}</p>
          <p className="muted">
            Scheduler: {settings.scheduler_enabled ? "Enabled" : "Disabled"}.
            Configure through ENABLE_SCHEDULER.
          </p>
        </Panel>
      </div>
      {user.role === "Admin" && (
        <AdminSettings onSaved={setSaved} onError={setError} />
      )}
      <Panel title="Identity & access">
        <div className="prose">
          <p>
            Signed in as <strong>{user.name}</strong> · {user.email} ·{" "}
            {user.role}
          </p>
          <p>
            Viewers read intelligence and query evidence. Analysts manage
            technologies and approve assessments. Administrators additionally
            manage users, sources and methodology.
          </p>
        </div>
      </Panel>
      {editing && (
        <Modal
          title={`Configure ${editing.id}`}
          onClose={() => setEditing(null)}
        >
          <form className="form-grid" onSubmit={saveHorizon}>
            <label>
              Name
              <input name="name" defaultValue={editing.name} required />
            </label>
            <label>
              Description
              <textarea
                name="description"
                defaultValue={editing.description}
                minLength={10}
                required
              />
            </label>
            <div className="form-row">
              <label>
                Years
                <input name="years" defaultValue={editing.years} required />
              </label>
              <label>
                Minimum maturity
                <input
                  name="min_maturity"
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={editing.min_maturity}
                />
              </label>
              <label>
                Display order
                <input
                  name="display_order"
                  type="number"
                  min="1"
                  max="4"
                  defaultValue={editing.display_order}
                />
              </label>
            </div>
            <label>
              Score rule metadata (JSON)
              <textarea
                name="rules"
                defaultValue={JSON.stringify(editing.score_rules, null, 2)}
              />
            </label>
            <State error={error} />
            <button className="button primary" disabled={busy}>
              Save horizon
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function AdminSettings({
  onSaved,
  onError,
}: {
  onSaved: (s: string) => void;
  onError: (s: string) => void;
}) {
  const { data: users, refresh } = useApi<Json[]>("/users"),
    { data: technologies } = useApi<Technology[]>("/technologies"),
    { data: sources, refresh: refreshSources } = useApi<Json[]>("/sources"),
    { settings, refreshSettings } = useSession();
  async function createUser(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form);
    try {
      await post("/users", Object.fromEntries(f));
      form.reset();
      refresh();
      onSaved("User created.");
    } catch (e) {
      onError((e as Error).message);
    }
  }
  async function source(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await post("/sources", Object.fromEntries(f));
      refreshSources();
      onSaved("Approved source added.");
    } catch (e) {
      onError((e as Error).message);
    }
  }
  async function rules(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await put(
        "/settings/signal-rules",
        Object.fromEntries([...f].map(([k, v]) => [k, Number(v)])),
      );
      refreshSettings();
      onSaved("Signal rules updated. Next calculation uses these thresholds.");
    } catch (e) {
      onError((e as Error).message);
    }
  }
  return (
    <>
      <div className="two-columns">
        <Panel title="Manage local users">
          <div className="provider-list">
            {users?.map((u) => (
              <div key={u.id}>
                <span>{u.email}</span>
                <Badge>{u.role}</Badge>
              </div>
            ))}
          </div>
          <form className="form-grid" onSubmit={createUser}>
            <label>
              Name
              <input name="name" minLength={2} required />
            </label>
            <label>
              Email
              <input name="email" type="email" required />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={12}
                required
                autoComplete="new-password"
              />
            </label>
            <label>
              Role
              <select name="role">
                {["Viewer", "Analyst", "Admin"].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <button className="button">Create user</button>
          </form>
        </Panel>
        <Panel title="Quantitative signal rules">
          <form className="form-grid" onSubmit={rules}>
            {Object.entries(settings.signal_rules || {}).map(([k, v]) => (
              <label key={k}>
                {k.replaceAll("_", " ")}
                <input
                  name={k}
                  type="number"
                  step={k === "growth_threshold" ? "0.05" : "1"}
                  min="0"
                  defaultValue={Number(v)}
                />
              </label>
            ))}
            <button className="button">Save signal rules</button>
          </form>
        </Panel>
      </div>
      <Panel
        title="Approved public web sources"
        subtitle="Configure SCRAPER_ALLOWED_DOMAINS before adding a source. Robots checks remain mandatory."
      >
        <div className="provider-list">
          {sources?.map((s) => (
            <div key={s.id}>
              <span>{s.url}</span>
              <Badge>{s.enabled ? "Enabled" : "Disabled"}</Badge>
            </div>
          ))}
        </div>
        <form className="form-grid" onSubmit={source}>
          <label>
            Public page URL
            <input type="url" name="url" required />
          </label>
          <label>
            Technology
            <select name="technology_id" required>
              {technologies?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <button className="button">Add approved source</button>
        </form>
      </Panel>
    </>
  );
}

export function QualityPage() {
  const { data, error, loading } = useApi<Json>("/quality");
  if (!data) return <State error={error} loading={loading} />;
  return (
    <>
      <PageHeading
        eyebrow="TRUST & TRACEABILITY"
        title="Data quality"
        description="Inspect coverage, validation failures and the safeguards behind your evidence."
      />
      <div className="kpi-grid">
        {[
          ["Evidence records", data.total],
          ["Missing titles", data.missing_titles],
          ["Missing mappings", data.missing_technology],
          ["Embedded records", data.embedded],
        ].map(([label, value]) => (
          <section className="kpi-card" key={label}>
            <div>
              <span>{label}</span>
              <ShieldCheck size={18} />
            </div>
            <strong>{value}</strong>
          </section>
        ))}
      </div>
      <div className="two-columns">
        <Panel title="Validation policies">
          <div className="prose">
            <p>{data.duplicate_policy}</p>
            <p>{data.url_policy}</p>
            <p>
              Dates must be between 1900 and today. Evidence types and
              technology mappings are validated. AI citations must be drawn from
              the retrieved context.
            </p>
          </div>
        </Panel>
        <Panel title="Content coverage">
          <div className="prose">
            <h3>{data.missing_content} records without text fragments</h3>
            <p>
              News metadata may intentionally omit copyrighted article text. An
              absent abstract is not fabricated or filled with AI-generated
              content.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="Rejected staging records"
        subtitle="Invalid batches cannot modify production evidence"
      >
        {data.rejected.length ? (
          data.rejected.map((r: Json) => (
            <div className="error" key={r.id}>
              <strong>Run {r.run_id}</strong>
              <p>{r.error}</p>
            </div>
          ))
        ) : (
          <Empty>
            No rejected records. Validation failures will appear here.
          </Empty>
        )}
      </Panel>
    </>
  );
}
