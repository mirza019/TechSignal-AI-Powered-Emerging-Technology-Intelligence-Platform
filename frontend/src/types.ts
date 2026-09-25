export type Json = Record<string, any>;
export type User = {
  id: string;
  email: string;
  name: string;
  role: "Admin" | "Analyst" | "Viewer";
};
export type Evidence = {
  id: string;
  title: string;
  source_type: string;
  url: string;
  published_at: string;
  content: string;
  provider: string;
  is_demo: boolean;
  metadata_json: Json;
  technology_id: string;
};
export type Technology = {
  id: string;
  name: string;
  domain: string;
  description: string;
  horizon: string;
  maturity: number;
  confidence: number;
  approved: boolean;
  is_demo: boolean;
  archived: boolean;
  last_reviewed: string;
  analyst_notes: string;
  keywords: string[];
  evidence_count: number;
  score: {
    dimensions: Record<string, number>;
    metrics: Json;
    weights: Record<string, number>;
    formula: string;
    created_at: string;
  } | null;
  latest_analysis: Json | null;
  evidence?: Evidence[];
  history?: Json[];
  radar_history?: Json[];
  organizations?: Json[];
  related?: Technology[];
};
export const HORIZON_COLORS: Record<string, string> = {
  H1: "#288f76",
  H2: "#699ad1",
  H3: "#b192d1",
  H4: "#c4a56b",
};
export const date = (value: string) =>
  value
    ? new Date(value).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Not reviewed";
export const pct = (value: number) => `${Math.round(value * 100)}%`;
