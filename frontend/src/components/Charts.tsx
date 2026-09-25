export function BarChart({
  data,
  color = "#329d82",
}: {
  data: Record<string, number>;
  color?: string;
}) {
  const max = Math.max(...Object.values(data), 1);
  return (
    <div className="bar-chart">
      {Object.entries(data).map(([name, value]) => (
        <div className="bar-row" key={name}>
          <span title={name}>{name}</span>
          <div>
            <i
              style={{
                width: `${Math.max((value / max) * 100, 2)}%`,
                background: color,
              }}
            />
          </div>
          <b>{value}</b>
        </div>
      ))}
    </div>
  );
}
export function TrendChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).slice(-12),
    max = Math.max(...entries.map((e) => e[1]), 1);
  return (
    <div className="trend-chart" aria-label="Monthly signal volume">
      {entries.map(([label, value]) => (
        <div className="trend-column" key={label}>
          <b>{value}</b>
          <div style={{ height: `${(value / max) * 105 + 3}px` }} />
          <span>{label.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
