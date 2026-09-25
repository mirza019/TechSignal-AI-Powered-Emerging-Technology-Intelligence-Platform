import { useEffect, useRef } from "react";
import type { Technology } from "../types";
import { HORIZON_COLORS } from "../types";

export default function Radar({
  technologies,
  onSelect,
  height = 470,
}: {
  technologies: Technology[];
  onSelect: (id: string) => void;
  height?: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;
    import("plotly.js-dist-min").then(({ default: Plotly }) => {
      if (disposed || !container.current) return;
      const element = container.current;
      const positions = technologies.map((t) => {
        const hash = [...t.id].reduce(
          (a, c) => (a * 31 + c.charCodeAt(0)) >>> 0,
          0,
        );
        return {
          t,
          angle: ((hash % 360) * Math.PI) / 180,
          r: Number(t.horizon.slice(1)) - 0.42 + (hash % 17) / 100,
        };
      });
      const traces = ["H4", "H3", "H2", "H1"].map((h) => {
        const points = positions.filter((p) => p.t.horizon === h);
        return {
          type: "scatter" as const,
          mode: "markers" as const,
          name: h,
          x: points.map((p) => Math.cos(p.angle) * p.r),
          y: points.map((p) => Math.sin(p.angle) * p.r),
          customdata: points.map((p) => p.t.id),
          text: points.map(
            (p) =>
              `${p.t.name}<br>${p.t.domain} · ${p.t.horizon}<br>Signal ${p.t.score?.dimensions.signal ?? "—"} · Confidence ${Math.round(p.t.confidence * 100)}%<br>Research ${p.t.score?.dimensions.research ?? "—"} · Commercial ${p.t.score?.dimensions.commercial ?? "—"}<br>${p.t.approved ? "Analyst-approved" : "Awaiting review"}<br>Reviewed: ${p.t.last_reviewed?.slice(0, 10) || "Never"}`,
          ),
          hovertemplate: "%{text}<extra></extra>",
          marker: {
            color: HORIZON_COLORS[h],
            size: points.map(
              (p) => 12 + (p.t.score?.dimensions.signal ?? 40) / 15,
            ),
            line: { color: "#fff", width: 2 },
            opacity: 0.95,
          },
        };
      });
      const circles = [4, 3, 2, 1].map((r, i) => ({
        type: "circle" as const,
        x0: -r,
        x1: r,
        y0: -r,
        y1: r,
        fillcolor: ["#f6f4ef", "#f3f0f7", "#edf3f8", "#e9f4ee"][i],
        line: { color: "#d7e1df", width: 1 },
        layer: "below" as const,
      }));
      Plotly.newPlot(
        element,
        traces,
        {
          height,
          autosize: true,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          margin: { l: 14, r: 14, t: 10, b: 10 },
          xaxis: { visible: false, range: [-4.6, 4.6], fixedrange: true },
          yaxis: {
            visible: false,
            range: [-4.5, 4.5],
            scaleanchor: "x",
            scaleratio: 1,
            fixedrange: true,
          },
          showlegend: false,
          shapes: [
            ...circles,
            {
              type: "line",
              x0: -4,
              x1: 4,
              y0: 0,
              y1: 0,
              line: { color: "#d8e2dd", width: 1, dash: "dot" },
              layer: "below",
            },
            {
              type: "line",
              x0: 0,
              x1: 0,
              y0: -4,
              y1: 4,
              line: { color: "#d8e2dd", width: 1, dash: "dot" },
              layer: "below",
            },
          ],
          annotations: [1, 2, 3, 4].map((r) => ({
            x: 0.25,
            y: r - 0.2,
            text: `H${r}`,
            showarrow: false,
            font: { size: 10, color: "#6c827a" },
          })),
          hoverlabel: {
            bgcolor: "#173e38",
            font: { color: "#fff", size: 12 },
            bordercolor: "#173e38",
          },
        },
        { displayModeBar: false, responsive: true, scrollZoom: false },
      ).then(() => {
        if (disposed) return;
        (
          element as unknown as {
            on: (event: string, fn: (event: any) => void) => void;
          }
        ).on("plotly_click", (event) => {
          const id = event.points?.[0]?.customdata;
          if (id) onSelect(String(id));
        });
      });
      const observer = new ResizeObserver(() => {
        if (!disposed) Plotly.Plots.resize(element);
      });
      observer.observe(element);
      cleanup = () => {
        observer.disconnect();
        Plotly.purge(element);
      };
    });
    return () => {
      disposed = true;
      cleanup?.();
    };
  }, [technologies, onSelect, height]);
  return (
    <div
      ref={container}
      className="radar-plot"
      role="img"
      aria-label="Interactive technology radar. Technologies are grouped into H1 through H4 maturity rings. Use the technology list for keyboard navigation."
      style={{ minHeight: height }}
    />
  );
}
