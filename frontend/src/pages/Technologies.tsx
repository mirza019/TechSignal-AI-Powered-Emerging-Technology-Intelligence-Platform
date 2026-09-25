import { useState, useCallback, useEffect } from "react";
import type { FormEvent } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  Plus,
  ArrowUpRight,
  CheckCircle2,
  Sparkles,
  FileText,
  Pencil,
  ArrowLeft,
  History,
} from "lucide-react";
import { useApi } from "../hooks";
import { api, post, put } from "../api";
import { useSession } from "../App";
import type { Technology, Json, Evidence } from "../types";
import { pct, date } from "../types";
import {
  PageHeading,
  Panel,
  State,
  Badge,
  HorizonBadge,
  SearchBox,
  Meter,
  Empty,
  Modal,
  EvidenceList,
} from "../components/ui";
import Radar from "../components/Radar";
import { BarChart, TrendChart } from "../components/Charts";

export function TechnologyEditor({
  technology,
  onClose,
  onSaved,
}: {
  technology?: Technology;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { settings } = useSession(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const body = {
        name: f.get("name"),
        domain: f.get("domain"),
        description: f.get("description"),
        keywords: String(f.get("keywords"))
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        analyst_notes: f.get("notes"),
        archived: f.get("archived") === "on",
      };
      if (technology) await put(`/technologies/${technology.id}`, body);
      else await post("/technologies", body);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={technology ? "Edit technology" : "Add technology"}
      onClose={onClose}
    >
      <form onSubmit={save} className="form-grid">
        <label>
          Technology name
          <input
            name="name"
            required
            minLength={3}
            defaultValue={technology?.name}
          />
        </label>
        <label>
          Domain
          <select name="domain" defaultValue={technology?.domain}>
            {settings.domains?.map((d: Json) => (
              <option key={d.name}>{d.name}</option>
            ))}
          </select>
        </label>
        <label>
          Description
          <textarea
            name="description"
            rows={3}
            defaultValue={technology?.description}
          />
        </label>
        <label>
          Search keywords & synonyms
          <small>Separate terms with commas. Used in source queries.</small>
          <input
            name="keywords"
            defaultValue={technology?.keywords.join(", ")}
          />
        </label>
        <label>
          Analyst notes
          <textarea
            name="notes"
            rows={3}
            defaultValue={technology?.analyst_notes}
          />
        </label>
        {technology && (
          <label className="checkbox">
            <input
              name="archived"
              type="checkbox"
              defaultChecked={technology.archived}
            />{" "}
            Archive this technology
          </label>
        )}
        <State error={error} />
        <button className="button primary" disabled={busy}>
          {busy ? "Saving…" : "Save technology"}
        </button>
      </form>
    </Modal>
  );
}

export function Technologies() {
  const { data, error, loading, refresh } =
      useApi<Technology[]>("/technologies"),
    { user, settings } = useSession(),
    [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || ""),
    [domain, setDomain] = useState(""),
    [horizon, setHorizon] = useState(""),
    [pending, setPending] = useState(params.get("review") === "pending"),
    [editor, setEditor] = useState(false);
  useEffect(() => { const incoming = params.get("q"); if (incoming !== null) setSearch(incoming) }, [params]);
  const filtered = (data || []).filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) &&
      (!domain || t.domain === domain) &&
      (!horizon || t.horizon === horizon) &&
      (!pending || !t.approved),
  );
  return (
    <>
      <PageHeading
        eyebrow="TECHNOLOGY PORTFOLIO"
        title="Monitored technologies"
        description="Explore assessments, momentum and the evidence behind every placement."
        actions={
          user.role !== "Viewer" && (
            <button className="button primary" onClick={() => setEditor(true)}>
              <Plus size={16} /> Add technology
            </button>
          )
        }
      />
      <div className="toolbar">
        <SearchBox
          value={search}
          onChange={(v) => {
            setSearch(v);
            if (params.has("q")) {
              params.delete("q");
              setParams(params);
            }
          }}
        />
        <select
          aria-label="Domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        >
          <option value="">All domains</option>
          {settings.domains?.map((d: Json) => (
            <option key={d.name}>{d.name}</option>
          ))}
        </select>
        <select
          aria-label="Horizon"
          value={horizon}
          onChange={(e) => setHorizon(e.target.value)}
        >
          <option value="">All horizons</option>
          {["H1", "H2", "H3", "H4"].map((h) => (
            <option key={h}>{h}</option>
          ))}
        </select>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={pending}
            onChange={(e) => setPending(e.target.checked)}
          />{" "}
          Awaiting review
        </label>
        <span className="toolbar-count">{filtered.length} technologies</span>
      </div>
      <State error={error} loading={loading} />
      <div className="technology-grid">
        {filtered.map((t) => (
          <Link
            className="technology-card"
            to={`/technologies/${t.id}`}
            key={t.id}
          >
            <div className="card-top">
              <HorizonBadge value={t.horizon} />
              <span>{t.domain}</span>
              <ArrowUpRight size={17} />
            </div>
            <h2>{t.name}</h2>
            <p>{t.description}</p>
            <div className="card-metrics">
              <div>
                <small>Research momentum</small>
                <Meter value={t.score?.dimensions.research || 0} />
              </div>
              <div>
                <small>Commercial momentum</small>
                <Meter
                  value={t.score?.dimensions.commercial || 0}
                  color="#89a4ce"
                />
              </div>
            </div>
            <div className="card-bottom">
              <Badge tone={t.approved ? "green" : "amber"}>
                {t.approved ? "Analyst-approved" : "Awaiting review"}
              </Badge>
              <span>
                {t.evidence_count} sources · {pct(t.confidence)}
              </span>
            </div>
          </Link>
        ))}
      </div>
      {!loading && !filtered.length && (
        <Empty>No technologies match these filters.</Empty>
      )}
      {editor && (
        <TechnologyEditor onClose={() => setEditor(false)} onSaved={refresh} />
      )}
    </>
  );
}

export function RadarPage() {
  const { data, error, loading } = useApi<Json>("/radar"),
    navigate = useNavigate();
  const [search, setSearch] = useState(""),
    [domain, setDomain] = useState(""),
    [confidence, setConfidence] = useState(0),
    [maturity, setMaturity] = useState(0),
    [signal, setSignal] = useState(0),
    [history, setHistory] = useState(false);
  const select = useCallback(
    (id: string) => navigate(`/technologies/${id}`),
    [navigate],
  );
  const filtered = (data?.technologies || []).filter(
    (t: Technology) =>
      t.name.toLowerCase().includes(search.toLowerCase()) &&
      (!domain || t.domain === domain) &&
      t.confidence * 100 >= confidence &&
      t.maturity >= maturity &&
      (t.score?.dimensions.signal || 0) >= signal,
  );
  return (
    <>
      <PageHeading
        eyebrow="PORTFOLIO HORIZONS"
        title="Technology radar"
        description="Place the present. Explore the possible. Review every horizon against evidence."
        actions={
          <button className="button" onClick={() => setHistory(!history)}>
            <History size={16} />
            {history ? "Hide history" : "Placement history"}
          </button>
        }
      />
      <State error={error} loading={loading} />
      <div className="toolbar">
        <SearchBox value={search} onChange={setSearch} />
        <select
          aria-label="Domain filter"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        >
          <option value="">All domains</option>
          {[
            ...new Set<string>(
              (data?.technologies || []).map((t: Technology) => t.domain),
            ),
          ].map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        {[
          ["Confidence", confidence, setConfidence],
          ["Maturity", maturity, setMaturity],
          ["Signal", signal, setSignal],
        ].map(([label, value, setter]) => (
          <label className="range-filter" key={label as string}>
            {label as string} ≥ {value as number}
            <input
              type="range"
              min="0"
              max="100"
              value={value as number}
              onChange={(e) =>
                (setter as (n: number) => void)(Number(e.target.value))
              }
            />
          </label>
        ))}
      </div>
      <div className="radar-page-grid">
        <Panel
          title="Grid technology landscape"
          subtitle={`${filtered.length} technologies · Click a point to inspect its evidence`}
        >
          <Radar technologies={filtered} onSelect={select} height={580} />
          <div className="methodology-note">{data?.methodology}</div>
        </Panel>
        <Panel title="Horizon guide" subtitle="Editable portfolio definitions">
          <div className="horizon-guide">
            {data?.horizons.map((h: Json) => (
              <div key={h.id}>
                <HorizonBadge value={h.id} />
                <h3>{h.name}</h3>
                <small>{h.years}</small>
                <p>{h.description}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel
        title="Radar technologies"
        subtitle="Keyboard-accessible list of every visible radar point"
      >
        <div className="radar-list">
          {filtered.map((t: Technology) => (
            <Link key={t.id} to={`/technologies/${t.id}`}>
              <HorizonBadge value={t.horizon} />
              <span>
                {t.name}
                <small>{t.domain}</small>
              </span>
              <Badge tone={t.approved ? "green" : "amber"}>
                {t.approved ? "Approved" : "Pending"}
              </Badge>
              {t.latest_analysis?.output.suggested_horizon && (
                <Badge>
                  AI suggests {t.latest_analysis.output.suggested_horizon}
                </Badge>
              )}
            </Link>
          ))}
        </div>
      </Panel>
      {history && (
        <Panel title="Placement history">
          {data?.history.map((h: Json) => (
            <div className="history-item" key={h.id}>
              <strong>
                {
                  data.technologies.find(
                    (t: Technology) => t.id === h.technology_id,
                  )?.name
                }
              </strong>
              <span>
                {h.old_horizon} → {h.new_horizon}
              </span>
              <p>{h.reason}</p>
              <small>{date(h.created_at)}</small>
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}

function ReviewDialog({
  technology,
  onClose,
  onSaved,
}: {
  technology: Technology;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      await post(`/technologies/${technology.id}/review`, {
        horizon: f.get("horizon"),
        maturity: Number(f.get("maturity")),
        confidence: Number(f.get("confidence")) / 100,
        notes: f.get("notes"),
        evidence_ids: f.getAll("evidence"),
        analysis_id: technology.latest_analysis?.output.suggested_horizon
          ? technology.latest_analysis.id
          : null,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Review & approve assessment" onClose={onClose}>
      <form className="form-grid" onSubmit={save}>
        <p>
          Your decision is recorded in assessment history and the audit log. AI
          suggestions never update the radar automatically.
        </p>
        <div className="form-row">
          <label>
            Horizon
            <select name="horizon" defaultValue={technology.horizon}>
              {["H1", "H2", "H3", "H4"].map((h) => (
                <option key={h}>{h}</option>
              ))}
            </select>
          </label>
          <label>
            Maturity / 100
            <input
              name="maturity"
              type="number"
              min={0}
              max={100}
              defaultValue={technology.maturity}
              required
            />
          </label>
          <label>
            Confidence %
            <input
              name="confidence"
              type="number"
              min={0}
              max={100}
              defaultValue={Math.round(technology.confidence * 100)}
              required
            />
          </label>
        </div>
        <label>
          Decision & rationale
          <textarea
            name="notes"
            minLength={10}
            required
            rows={3}
            placeholder="Explain the evidence behind this assessment…"
          />
        </label>
        <fieldset>
          <legend>Select supporting evidence</legend>
          {technology.evidence?.map((e) => (
            <label className="checkbox" key={e.id}>
              <input type="checkbox" name="evidence" value={e.id} />
              {e.title}
            </label>
          ))}
        </fieldset>
        <State error={error} />
        <button className="button primary" disabled={busy}>
          <CheckCircle2 size={16} />
          {busy ? "Saving…" : "Approve assessment"}
        </button>
      </form>
    </Modal>
  );
}

export function TechnologyProfile() {
  const { id } = useParams(),
    {
      data: t,
      error,
      loading,
      refresh,
    } = useApi<Technology>(`/technologies/${id}`),
    { user } = useSession(),
    navigate = useNavigate();
  const [tab, setTab] = useState("Overview"),
    [busy, setBusy] = useState(""),
    [actionError, setActionError] = useState(""),
    [review, setReview] = useState(false),
    [edit, setEdit] = useState(false);
  async function action(kind: string) {
    if (!t) return;
    setBusy(kind);
    setActionError("");
    try {
      if (kind === "analyze") {
        await post("/ai/technology-analysis", { technology_id: t.id });
        refresh();
      } else {
        await post("/reports/generate", {
          kind: "Technology Opportunity Report",
          technology_id: t.id,
        });
        navigate("/reports");
      }
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  if (!t) return <State error={error} loading={loading} />;
  const evidence = t.evidence || [],
    analysis = t.latest_analysis?.output;
  const counts = (type?: string) =>
    evidence
      .filter((e) => !type || e.source_type === type)
      .reduce((a: Record<string, number>, e) => {
        const key = e.published_at.slice(0, 7);
        a[key] = (a[key] || 0) + 1;
        return a;
      }, {});
  return (
    <>
      <Link className="back-link" to="/technologies">
        <ArrowLeft size={14} /> Technology portfolio
      </Link>
      <PageHeading
        eyebrow={t.domain.toUpperCase()}
        title={t.name}
        description={t.description}
        actions={
          user.role !== "Viewer" && (
            <>
              <button className="button" onClick={() => setEdit(true)}>
                <Pencil size={15} /> Edit
              </button>
              <button
                className="button primary"
                onClick={() => setReview(true)}
              >
                <CheckCircle2 size={16} /> Review assessment
              </button>
            </>
          )
        }
      />
      <div className="profile-status">
        <HorizonBadge value={t.horizon} />
        <Badge tone={t.approved ? "green" : "amber"}>
          {t.approved ? "Analyst-approved" : "Awaiting review"}
        </Badge>
        {t.is_demo && <Badge>Sample technology assessment</Badge>}
        <span>Last reviewed {date(t.last_reviewed)}</span>
      </div>
      <div className="profile-kpis">
        {[
          ["Signal strength", t.score?.dimensions.signal || 0],
          ["Research momentum", t.score?.dimensions.research || 0],
          ["Commercial momentum", t.score?.dimensions.commercial || 0],
          ["Evidence confidence", Math.round(t.confidence * 100)],
        ].map(([name, value]) => (
          <div key={name}>
            <small>{name}</small>
            <strong>
              {value}
              <span>/ 100</span>
            </strong>
            <Meter value={Number(value)} />
          </div>
        ))}
      </div>
      <div className="tabs">
        {[
          "Overview",
          "Research & organizations",
          "Evidence",
          "Assessment history",
        ].map((name) => (
          <button
            key={name}
            className={tab === name ? "active" : ""}
            onClick={() => setTab(name)}
          >
            {name}
            {name === "Evidence" && <span>{evidence.length}</span>}
          </button>
        ))}
      </div>
      <State error={actionError} />
      {tab === "Overview" && (
        <>
          <div className="profile-grid">
            <Panel
              title="Intelligence summary"
              subtitle={
                t.latest_analysis
                  ? `${t.latest_analysis.model} · ${t.latest_analysis.approval_status} review`
                  : "Grounded synthesis with explicit source references"
              }
              action={
                user.role !== "Viewer" && (
                  <button
                    className="button small"
                    disabled={!!busy}
                    onClick={() => action("analyze")}
                  >
                    <Sparkles size={14} />
                    {busy === "analyze" ? "Analyzing…" : "Generate analysis"}
                  </button>
                )
              }
            >
              {analysis ? (
                <div className="prose">
                  <Badge tone="purple">
                    {t.latest_analysis?.model ===
                    "deterministic-evidence-summary"
                      ? "Deterministic fallback"
                      : "AI-generated interpretation"}
                  </Badge>
                  <p>{analysis.executive_summary || analysis.interpretation}</p>
                  {analysis.research_momentum && (
                    <>
                      <h3>Research & commercial momentum</h3>
                      <p>{analysis.research_momentum}</p>
                      <p>{analysis.commercial_momentum}</p>
                    </>
                  )}
                  {["opportunities", "risks", "uncertainties"].map((key) => (
                    <div key={key}>
                      <h3>{key}</h3>
                      <ul>
                        {(analysis[key] || []).map((x: string) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  <h3>
                    Suggested horizon:{" "}
                    {analysis.suggested_horizon || "Not assessed"}
                  </h3>
                  <p>{analysis.monitoring_recommendation}</p>
                  <small>
                    {t.latest_analysis?.evidence_ids.length} validated evidence
                    references · {date(t.latest_analysis?.created_at)}
                  </small>
                </div>
              ) : (
                <Empty>
                  No analysis generated yet. Generate an evidence-grounded
                  summary to support your review.
                </Empty>
              )}
              <div className="panel-footnote">
                AI interpretation is a review aid. Citation validation does not
                verify claim truth.
              </div>
            </Panel>
            <div>
              <Panel title="Current assessment">
                <div className="prose">
                  <h3>
                    <HorizonBadge value={t.horizon} /> Analyst placement
                  </h3>
                  <p>{t.analyst_notes || "No analyst notes yet."}</p>
                  <p>
                    Maturity: {t.maturity}/100
                    <br />
                    Confidence: {pct(t.confidence)}
                  </p>
                </div>
                {user.role !== "Viewer" && (
                  <button
                    className="button wide"
                    disabled={!!busy}
                    onClick={() => action("report")}
                  >
                    <FileText size={16} /> Create opportunity profile
                  </button>
                )}
              </Panel>
              <Panel title="Related technologies">
                {t.related?.length ? (
                  t.related.map((r) => (
                    <Link
                      className="related-link"
                      key={r.id}
                      to={`/technologies/${r.id}`}
                    >
                      {r.name}
                      <ArrowUpRight size={14} />
                    </Link>
                  ))
                ) : (
                  <Empty>No other technologies in this domain.</Empty>
                )}
              </Panel>
            </div>
          </div>
          <Panel
            title="Score explainability"
            subtitle="Every score preserves the metrics, weights and formula used to calculate it"
          >
            <div className="prose">
              <p>{t.score?.formula || "No score calculated yet."}</p>
              <div className="metric-grid">
                {Object.entries(t.score?.metrics || {}).map(([k, v]) => (
                  <div key={k}>
                    <small>{k.replaceAll("_", " ")}</small>
                    <strong>
                      {v === null
                        ? "Not measured"
                        : typeof v === "boolean"
                          ? v
                            ? "Yes"
                            : "No"
                          : typeof v === "number"
                            ? Math.round(v * 100) / 100
                            : String(v)}
                    </strong>
                  </div>
                ))}
              </div>
              <p>
                Weights:{" "}
                {Object.entries(t.score?.weights || {})
                  .map(([k, v]) => `${k} ${pct(v)}`)
                  .join(" · ")}
              </p>
            </div>
          </Panel>
        </>
      )}
      {tab === "Research & organizations" && (
        <>
          <div className="two-columns">
            <Panel
              title="Research publication trend"
              subtitle="Publication records by month"
            >
              <TrendChart data={counts("paper")} />
            </Panel>
            <Panel
              title="News signal trend"
              subtitle="Dated market-signal metadata"
            >
              <TrendChart data={counts("news")} />
            </Panel>
            <Panel title="Source distribution">
              <BarChart
                data={evidence.reduce((a: Record<string, number>, e) => {
                  a[e.source_type] = (a[e.source_type] || 0) + 1;
                  return a;
                }, {})}
              />
            </Panel>
            <Panel
              title="Citation totals by publication year"
              subtitle="Current citation snapshots; not historical citation growth"
            >
              <BarChart
                data={evidence
                  .filter((e) => e.source_type === "paper")
                  .reduce((a: Record<string, number>, e) => {
                    const y = e.published_at.slice(0, 4);
                    a[y] = (a[y] || 0) + (e.metadata_json.citation_count || 0);
                    return a;
                  }, {})}
              />
            </Panel>
          </div>
          <Panel title="Startup & institution landscape">
            <div className="organization-grid">
              {t.organizations?.map((o) => (
                <Link
                  className="organization-card"
                  key={o.id}
                  to={`/organizations/${o.id}`}
                >
                  <Badge>{o.kind}</Badge>
                  <h3>{o.name}</h3>
                  <p>
                    {o.country} · {o.publication_count} publications
                  </p>
                  <small>
                    {o.is_demo
                      ? "Fictional sample organization"
                      : "Public source records"}
                  </small>
                </Link>
              ))}
            </div>
          </Panel>
          <Panel title="Patent signals">
            <Empty>
              No patent evidence collected. EPO OPS is an optional future
              adapter; no patent activity is inferred.
            </Empty>
          </Panel>
        </>
      )}
      {tab === "Evidence" && (
        <Panel
          title="Evidence library"
          subtitle="Open the primary record to verify its claims"
        >
          <EvidenceList records={evidence} />
        </Panel>
      )}
      {tab === "Assessment history" && (
        <Panel
          title="Analyst assessment history"
          subtitle="A permanent record of decisions and the sources that supported them"
        >
          {t.history?.map((h) => (
            <article className="history-item" key={h.id}>
              <HorizonBadge value={h.horizon} />
              <strong>{date(h.created_at)}</strong>
              <p>{h.notes}</p>
              <small>
                {h.evidence_ids.length} evidence references · Actor {h.actor_id}
              </small>
              <details>
                <summary>Evidence IDs</summary>
                {h.evidence_ids.map((eid: string) => (
                  <div key={eid}>{eid}</div>
                ))}
              </details>
            </article>
          ))}
        </Panel>
      )}
      {review && (
        <ReviewDialog
          technology={t}
          onClose={() => setReview(false)}
          onSaved={refresh}
        />
      )}{" "}
      {edit && (
        <TechnologyEditor
          technology={t}
          onClose={() => setEdit(false)}
          onSaved={refresh}
        />
      )}
    </>
  );
}
