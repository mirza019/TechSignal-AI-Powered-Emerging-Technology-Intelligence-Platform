import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import {
  ArrowUpRight,
  LoaderCircle,
  X,
  Search,
  ExternalLink,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { Evidence } from "../types";
import { date, HORIZON_COLORS } from "../types";
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function HorizonBadge({ value }: { value: string }) {
  return (
    <span
      className="horizon-badge"
      style={{
        color: HORIZON_COLORS[value],
        background: `${HORIZON_COLORS[value]}18`,
      }}
    >
      {value}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{actions}</div>
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function State({
  error,
  loading,
}: {
  error?: string;
  loading?: boolean;
}) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : loading ? (
    <div className="loading">
      <LoaderCircle className="spin" size={20} /> Loading intelligence…
    </div>
  ) : null;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function SearchBox({
  value,
  onChange,
  placeholder = "Search technologies…",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search-box">
      <Search size={16} />
      <input
        aria-label={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}
export function MoreLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <Link className="more-link" to={to}>
      {children}
      <ArrowUpRight size={15} />
    </Link>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const root = ref.current;
    root
      ?.querySelector<HTMLElement>("button, input, select, textarea")
      ?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab" && root) {
        const items = Array.from(
          root.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
          ),
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={ref}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-heading">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function EvidenceList({ records }: { records: Evidence[] }) {
  return (
    <div className="evidence-list">
      {records.length ? (
        records.map((e) => (
          <article className="evidence-item" key={e.id}>
            <div className="evidence-top">
              <Badge>{e.source_type}</Badge>
              {e.is_demo && <Badge tone="amber">Sample</Badge>}
              <small>{date(e.published_at)}</small>
            </div>
            <a href={e.url} target="_blank" rel="noreferrer">
              {e.title} <ExternalLink size={13} />
            </a>
            {e.content && <p>{e.content.slice(0, 240)}</p>}
            <div className="evidence-id">
              {e.provider} · Evidence {e.id}
            </div>
          </article>
        ))
      ) : (
        <Empty>
          No evidence in this data mode. Ingest or add sources to begin.
        </Empty>
      )}
    </div>
  );
}
export function Meter({
  value,
  color = "#319b83",
}: {
  value: number;
  color?: string;
}) {
  return (
    <div className="meter">
      <div className="meter-track">
        <span
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            background: color,
          }}
        />
      </div>
      <span>{Math.round(value)}</span>
    </div>
  );
}
