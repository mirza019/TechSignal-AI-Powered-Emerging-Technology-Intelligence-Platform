import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  ArrowRight,
  Radar as RadarIcon,
  Radio,
  BookOpen,
  Building2,
  GraduationCap,
  Clock3,
  Layers,
  FilePlus2,
  ChevronRight,
} from "lucide-react";
import { useApi } from "../hooks";
import { post } from "../api";
import { useSession } from "../App";
import type { Json, Technology } from "../types";
import { HORIZON_COLORS, pct } from "../types";
import {
  PageHeading,
  Panel,
  State,
  Badge,
  MoreLink,
  HorizonBadge,
  Meter,
} from "../components/ui";
import Radar from "../components/Radar";
import { TrendChart } from "../components/Charts";

export default function Dashboard() {
  const { data, error, loading } = useApi<Json>("/dashboard"),
    { user } = useSession(),
    navigate = useNavigate();
  const [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState("");
  const select = useCallback(
    (id: string) => navigate(`/technologies/${id}`),
    [navigate],
  );
  async function briefing() {
    setBusy(true);
    try {
      await post("/reports/generate", {});
      navigate("/reports");
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!data) return <State error={error} loading={loading} />;
  const technologies: Technology[] = data.technologies;
  const priority = [...technologies]
    .sort(
      (a, b) =>
        (b.score?.dimensions.signal || 0) - (a.score?.dimensions.signal || 0),
    )
    .slice(0, 5);
  const kpis = [
    [
      "Tracked technologies",
      data.kpis.technologies,
      RadarIcon,
      "Across 11 technology domains",
    ],
    [
      "Active signals",
      data.kpis.signals,
      Radio,
      `${data.kpis.emerging} emerging signals`,
    ],
    [
      "Research papers",
      data.kpis.papers,
      BookOpen,
      "Traceable research evidence",
    ],
    [
      "Startups tracked",
      data.kpis.startups,
      Building2,
      "Curated organization profiles",
    ],
  ] as const;
  return (
    <>
      <PageHeading
        eyebrow="YOUR INTELLIGENCE WORKSPACE"
        title="Executive overview"
        description="A connected view of the technologies shaping tomorrow’s grid."
        actions={
          <>
            <Link className="button" to="/radar">
              <RadarIcon size={16} /> Explore radar
            </Link>
            {user.role !== "Viewer" && (
              <button
                className="button primary"
                disabled={busy}
                onClick={briefing}
              >
                <FilePlus2 size={16} />
                {busy ? "Generating…" : "Generate briefing"}
              </button>
            )}
          </>
        }
      />
      <State error={actionError} />
      <div className="insight-banner">
        <span className="insight-icon">
          <Radio size={20} />
        </span>
        <div>
          <strong>Turn signals into a clearer direction.</strong>
          <p>
            {data.kpis.awaiting_review} technologies are awaiting analyst
            review. Explore the evidence behind your next decision.
          </p>
        </div>
        <Link to="/technologies?review=pending">
          Review technologies <ArrowRight size={17} />
        </Link>
      </div>
      <div className="kpi-grid">
        {kpis.map(([label, value, Icon, detail]) => (
          <section className="kpi-card" key={label}>
            <div>
              <span>{label}</span>
              <Icon size={18} />
            </div>
            <strong>{value.toString().padStart(2, "0")}</strong>
            <small>
              <span className="tiny-dot" />
              {detail}
            </small>
          </section>
        ))}
      </div>
      <div className="overview-grid">
        <Panel
          title="Technology radar"
          subtitle="Where technologies sit on your portfolio horizon"
          action={<MoreLink to="/radar">View full radar</MoreLink>}
          className="radar-panel"
        >
          <div className="radar-label">
            <span className="live-dot" /> {technologies.length} monitored
            technologies{" "}
            <Badge>{data.is_demo ? "Sample data" : "Public evidence"}</Badge>
          </div>
          <Radar technologies={technologies} onSelect={select} height={385} />
          <div className="radar-legend">
            {Object.entries(HORIZON_COLORS).map(([h, color], i) => (
              <span key={h}>
                <i style={{ background: color }} />
                <strong>{h}</strong>
                {["Near-term", "Emerging", "Longer-term", "Exploratory"][i]}
              </span>
            ))}
          </div>
        </Panel>
        <div className="overview-right">
          <Panel
            title="Portfolio horizons"
            subtitle="A balanced view of technology maturity"
          >
            <div className="horizon-summary">
              {Object.entries(HORIZON_COLORS).map(([h, color], i) => (
                <div className="horizon-summary-row" key={h}>
                  <HorizonBadge value={h} />
                  <div>
                    <strong>
                      {
                        ["Near-term", "Emerging", "Longer-term", "Exploratory"][
                          i
                        ]
                      }
                    </strong>
                    <span className="horizon-track">
                      <i
                        style={{
                          background: color,
                          width: `${((data.horizons[h] || 0) / technologies.length) * 100}%`,
                        }}
                      />
                    </span>
                  </div>
                  <b>{data.horizons[h] || 0}</b>
                </div>
              ))}
            </div>
            <div className="panel-footnote">
              <Layers size={14} /> Configurable portfolio methodology
            </div>
          </Panel>
          <Panel
            title="Analyst attention"
            action={<Clock3 size={17} />}
            className="attention-panel"
          >
            <div className="attention-number">
              {data.kpis.awaiting_review.toString().padStart(2, "0")}
              <div>
                technologies
                <br />
                <span>awaiting review</span>
              </div>
            </div>
            <Link to="/technologies?review=pending">
              Open review queue <ArrowRight size={16} />
            </Link>
          </Panel>
        </div>
      </div>
      <div className="momentum-grid">
        <Panel
          title="Technologies to watch"
          subtitle="Prioritized by transparent, evidence-based signal score"
          action={<MoreLink to="/technologies">All technologies</MoreLink>}
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Technology</th>
                  <th>Horizon</th>
                  <th>Research</th>
                  <th>Signal</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {priority.map((t) => (
                  <tr key={t.id} onClick={() => select(t.id)}>
                    <td>
                      <Link to={`/technologies/${t.id}`}>{t.name}</Link>
                      <small>{t.domain}</small>
                    </td>
                    <td>
                      <HorizonBadge value={t.horizon} />
                    </td>
                    <td>
                      <Meter value={t.score?.dimensions.research || 0} />
                    </td>
                    <td>
                      <Badge tone="green">
                        {t.score?.dimensions.signal || 0}
                      </Badge>
                    </td>
                    <td>
                      <ChevronRight size={16} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Signal activity" subtitle="Collected evidence by month">
          <TrendChart data={data.trend} />
          <div className="activity-stats">
            <div>
              <GraduationCap size={17} />
              <strong>{data.kpis.institutions}</strong>
              <span>Institutions tracked</span>
            </div>
            <div>
              <BookOpen size={17} />
              <strong>
                {Object.values(data.sources).reduce(
                  (a: number, v) => a + Number(v),
                  0,
                )}
              </strong>
              <span>Evidence records</span>
            </div>
          </div>
        </Panel>
      </div>
      <Panel
        title="Latest intelligence"
        subtitle="New signals to investigate, grounded in source records"
        action={<MoreLink to="/signals">Signal feed</MoreLink>}
      >
        <div className="signal-cards">
          {data.signals.slice(0, 3).map((signal: Json) => {
            const tech = technologies.find(
              (t) => t.id === signal.technology_id,
            );
            return (
              <Link
                className="signal-card"
                key={signal.id}
                to={`/technologies/${signal.technology_id}`}
              >
                <div>
                  <Badge tone={signal.level === "Strong" ? "green" : "purple"}>
                    {signal.level} signal
                  </Badge>
                  <ArrowUpRight size={17} />
                </div>
                <h3>{tech?.name}</h3>
                <p>{signal.rule}</p>
                <small>
                  {signal.evidence_ids.length} evidence records ·{" "}
                  {tech ? pct(tech.confidence) : "—"} confidence
                </small>
              </Link>
            );
          })}
        </div>
      </Panel>
    </>
  );
}
