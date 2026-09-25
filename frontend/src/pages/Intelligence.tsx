import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Building2,
  GraduationCap,
  ArrowUpRight,
  Plus,
  Pencil,
  FileText,
  ArrowLeft,
} from "lucide-react";
import { useApi } from "../hooks";
import { post, put } from "../api";
import { useSession } from "../App";
import type { Json, Technology, Evidence } from "../types";
import { date } from "../types";
import {
  PageHeading,
  Panel,
  State,
  Badge,
  SearchBox,
  Empty,
  EvidenceList,
  Modal,
} from "../components/ui";
import { BarChart } from "../components/Charts";

export function SignalsPage() {
  const { data, error, loading } = useApi<Json[]>("/signals"),
    technologies = useApi<Technology[]>("/technologies"),
    [level, setLevel] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="EARLY INDICATORS"
        title="Signal intelligence"
        description="Quantitative signals first. Analyst interpretation next."
      />
      <div className="toolbar">
        <select
          aria-label="Signal level"
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        >
          <option value="">All signal levels</option>
          {["Strong", "Emerging", "Weak"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span>Historical signals are retained for traceability.</span>
      </div>
      <State error={error} loading={loading} />
      <div className="signal-feed">
        {data
          ?.filter((s) => !level || s.level === level)
          .map((s) => (
            <Link
              className="signal-feed-item"
              key={s.id}
              to={`/technologies/${s.technology_id}`}
            >
              <div className="signal-indicator" />
              <div>
                <div className="evidence-top">
                  <Badge
                    tone={
                      s.level === "Strong"
                        ? "green"
                        : s.level === "Emerging"
                          ? "purple"
                          : "amber"
                    }
                  >
                    {s.level} signal
                  </Badge>
                  {s.is_demo && <Badge>Sample</Badge>}
                  <small>{date(s.created_at)}</small>
                </div>
                <h3>
                  {technologies.data?.find((t) => t.id === s.technology_id)
                    ?.name || "Technology"}
                </h3>
                <p>{s.rule}</p>
                <small>
                  {s.evidence_ids.length} evidence references · Rule-based
                  detection
                </small>
              </div>
              <ArrowUpRight size={18} />
            </Link>
          ))}
      </div>
      {data?.length === 0 && (
        <Empty>
          No signals yet. Run the ingestion pipeline to calculate activity.
        </Empty>
      )}
    </>
  );
}
export function ResearchPage() {
  const { data, error, loading } = useApi<Evidence[]>("/papers"),
    [search, setSearch] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="RESEARCH INTELLIGENCE"
        title="Research library"
        description="Trace publications, authors, institutions and the research behind emerging technologies."
      />
      <div className="toolbar">
        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search research papers…"
        />
        <span className="toolbar-count">
          {data?.length || 0} papers collected
        </span>
      </div>
      <State error={error} loading={loading} />
      <Panel
        title="Academic evidence"
        subtitle="Metadata and abstracts only. Each record links back to its source."
      >
        <EvidenceList
          records={(data || []).filter((e) =>
            e.title.toLowerCase().includes(search.toLowerCase()),
          )}
        />
      </Panel>
    </>
  );
}

function StartupEditor({
  organization,
  onClose,
  onSaved,
}: {
  organization?: Json;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { data: technologies } = useApi<Technology[]>("/technologies"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    const tech = technologies?.find((t) => t.id === f.get("technology_id"));
    try {
      const body = {
        name: f.get("name"),
        website: f.get("website"),
        country: f.get("country"),
        city: f.get("city"),
        description: f.get("description"),
        technology_id: tech?.id || null,
        domains: tech ? [tech.domain] : [],
        analyst_notes: f.get("notes"),
        founded_year: f.get("founded_year")
          ? Number(f.get("founded_year"))
          : null,
        development_stage: f.get("development_stage"),
        public_funding_signal: f.get("public_funding_signal"),
        research_partners: String(f.get("research_partners"))
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        source_urls: String(f.get("source_urls"))
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        confidence: Number(f.get("confidence")) / 100,
      };
      if (organization) await put(`/startups/${organization.id}`, body);
      else await post("/startups", body);
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
      title={organization ? "Edit startup" : "Add startup"}
      onClose={onClose}
    >
      <form className="form-grid" onSubmit={save}>
        <label>
          Company name
          <input name="name" required defaultValue={organization?.name} />
        </label>
        <label>
          Public website
          <input
            type="url"
            name="website"
            defaultValue={organization?.website}
          />
        </label>
        <div className="form-row">
          <label>
            Country
            <input name="country" defaultValue={organization?.country} />
          </label>
          <label>
            City
            <input name="city" defaultValue={organization?.city} />
          </label>
          <label>
            Founded
            <input
              name="founded_year"
              type="number"
              min="1800"
              max="2100"
              defaultValue={organization?.founded_year}
            />
          </label>
        </div>
        <label>
          Primary technology
          <select
            name="technology_id"
            defaultValue={organization?.technology_id}
          >
            <option value="">Not mapped</option>
            {technologies?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Description
          <textarea
            name="description"
            rows={3}
            defaultValue={organization?.description}
          />
        </label>
        <div className="form-row">
          <label>
            Development stage
            <input
              name="development_stage"
              defaultValue={organization?.development_stage || "Unknown"}
            />
          </label>
          <label>
            Confidence %
            <input
              name="confidence"
              type="number"
              min="0"
              max="100"
              defaultValue={Math.round((organization?.confidence || 0.3) * 100)}
            />
          </label>
        </div>
        <label>
          Public funding signal
          <input
            name="public_funding_signal"
            defaultValue={organization?.public_funding_signal || "Not verified"}
          />
        </label>
        <label>
          Research partners (comma separated)
          <input
            name="research_partners"
            defaultValue={organization?.research_partners?.join(", ")}
          />
        </label>
        <label>
          Source URLs (one per line)
          <textarea
            name="source_urls"
            defaultValue={organization?.source_urls?.join("\n")}
          />
        </label>
        <label>
          Analyst notes
          <textarea name="notes" defaultValue={organization?.analyst_notes} />
        </label>
        <State error={error} />
        <button className="button primary" disabled={busy}>
          {busy ? "Saving…" : "Save startup"}
        </button>
      </form>
    </Modal>
  );
}

export function OrganizationsPage({
  kind,
}: {
  kind: "startups" | "institutions";
}) {
  const { data, error, loading, refresh } = useApi<Json[]>(`/${kind}`),
    { user } = useSession(),
    [search, setSearch] = useState(""),
    [editor, setEditor] = useState(false);
  const institutional = kind === "institutions";
  const Icon = institutional ? GraduationCap : Building2;
  return (
    <>
      <PageHeading
        eyebrow="ORGANIZATION INTELLIGENCE"
        title={institutional ? "Research institutions" : "Startup landscape"}
        description={
          institutional
            ? "Discover the institutions contributing evidence to your technology portfolio."
            : "Connect emerging companies to technologies, signals and public evidence."
        }
        actions={
          !institutional &&
          user.role !== "Viewer" && (
            <button className="button primary" onClick={() => setEditor(true)}>
              <Plus size={16} /> Add startup
            </button>
          )
        }
      />
      <div className="toolbar">
        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder={`Search ${kind}…`}
        />
        <span className="toolbar-count">{data?.length || 0} organizations</span>
      </div>
      {institutional && (
        <div className="notice">
          Ranked by collected relevant publication count. This measures database
          coverage, not overall institutional quality. AI does not determine
          these rankings.
        </div>
      )}
      <State error={error} loading={loading} />
      <div className="organization-grid">
        {data
          ?.filter((o) => o.name.toLowerCase().includes(search.toLowerCase()))
          .map((o, i) => (
            <Link
              className="organization-card"
              key={o.id}
              to={`/organizations/${o.id}`}
            >
              <div className="organization-top">
                <span className="organization-icon">
                  <Icon size={23} />
                </span>
                {institutional ? (
                  <span className="rank">#{i + 1}</span>
                ) : (
                  <ArrowUpRight size={17} />
                )}
              </div>
              <h2>{o.name}</h2>
              <small>
                {o.country}
                {o.city ? ` · ${o.city}` : ""}
              </small>
              <p>{o.description}</p>
              <div className="tag-list">
                {o.domains.map((d: string) => (
                  <Badge key={d}>{d}</Badge>
                ))}
              </div>
              <div className="card-bottom">
                <Badge tone={institutional ? "green" : "purple"}>
                  {institutional
                    ? `${o.publication_count} publications`
                    : o.development_stage}
                </Badge>
                {o.is_demo && <small>Fictional sample</small>}
              </div>
            </Link>
          ))}
      </div>
      {editor && (
        <StartupEditor onClose={() => setEditor(false)} onSaved={refresh} />
      )}
    </>
  );
}

export function OrganizationProfile() {
  const { id } = useParams(),
    { data: o, error, loading, refresh } = useApi<Json>(`/organizations/${id}`),
    { user } = useSession(),
    navigate = useNavigate(),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState(""),
    [editor, setEditor] = useState(false);
  async function briefing() {
    setBusy(true);
    try {
      await post("/reports/generate", {
        kind:
          o?.kind === "startup"
            ? "Startup Briefing"
            : "Research Institution Briefing",
        organization_id: id,
      });
      navigate("/reports");
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!o) return <State error={error} loading={loading} />;
  return (
    <>
      <Link
        className="back-link"
        to={o.kind === "startup" ? "/startups" : "/institutions"}
      >
        <ArrowLeft size={14} /> Organization landscape
      </Link>
      <PageHeading
        eyebrow={o.kind.toUpperCase()}
        title={o.name}
        description={`${o.country}${o.city ? ` · ${o.city}` : ""}`}
        actions={
          user.role !== "Viewer" && (
            <>
              {o.kind === "startup" && (
                <button className="button" onClick={() => setEditor(true)}>
                  <Pencil size={15} /> Edit
                </button>
              )}
              <button
                className="button primary"
                disabled={busy}
                onClick={briefing}
              >
                <FileText size={16} />
                {busy
                  ? "Generating…"
                  : o.kind === "startup"
                    ? "Generate Startup Briefing"
                    : "Generate Institution Briefing"}
              </button>
            </>
          )
        }
      />
      <State error={actionError} />
      <div className="profile-grid">
        <Panel title="Organization overview">
          <div className="prose">
            {o.is_demo && (
              <Badge tone="amber">Fictional sample organization</Badge>
            )}
            <p>{o.description}</p>
            {o.website && (
              <a href={o.website} target="_blank" rel="noreferrer">
                Visit public website ↗
              </a>
            )}
            <h3>Technology focus</h3>
            <div className="tag-list">
              {o.domains.map((d: string) => (
                <Badge key={d}>{d}</Badge>
              ))}
            </div>
            {o.technologies.map((t: Technology) => (
              <Link
                key={t.id}
                className="related-link"
                to={`/technologies/${t.id}`}
              >
                {t.name}
                <ArrowUpRight size={14} />
              </Link>
            ))}
            <h3>Research partners</h3>
            <p>
              {o.research_partners?.join(", ") ||
                "No verified research partnership recorded."}
            </p>
            <h3>Patents</h3>
            <p>
              {o.patents_found?.join(", ") || "No patent evidence collected."}
            </p>
            <h3>Analyst notes</h3>
            <p>{o.analyst_notes || "No analyst notes yet."}</p>
          </div>
        </Panel>
        <Panel
          title={
            o.kind === "institution" ? "Research activity" : "Public activity"
          }
        >
          <div className="prose">
            <h3>{o.publication_count} collected publications</h3>
            <p>
              {o.recent_publications} in the last 365 days ·{" "}
              {o.prior_publications} in the preceding 365 days.
            </p>
            <p>
              Growth: {Math.round(o.publication_momentum * 100)}%
              {o.baseline_zero
                ? " (zero prior baseline; interpret cautiously)"
                : ""}
              .
            </p>
            {o.kind === "startup" && (
              <>
                <h3>{o.development_stage}</h3>
                <p>
                  Founded {o.founded_year || "unknown"} · Latest activity{" "}
                  {date(o.latest_signal_date)}
                </p>
                <p>{o.public_funding_signal}</p>
              </>
            )}
            <h3>Top relevant researchers</h3>
            <BarChart
              data={Object.fromEntries(
                o.top_researchers.map((a: Json) => [
                  a.name,
                  a.publication_count,
                ]),
              )}
            />
          </div>
        </Panel>
      </div>
      <Panel
        title="Supporting public evidence"
        subtitle="Relationships and activity are shown only where a record exists."
      >
        <EvidenceList records={o.evidence} />
      </Panel>
      {editor && (
        <StartupEditor
          organization={o}
          onClose={() => setEditor(false)}
          onSaved={refresh}
        />
      )}
    </>
  );
}
