/** Indicadores de progresso reutilizados pelo dashboard e pelos questionarios. */

export function ProgressBar({
  value,
  color = "var(--color-primary)",
  label,
}: {
  value: number;
  color?: string;
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="progress-wrapper">
      {label && (
        <div className="progress-label">
          <span>{label}</span>
          <span>{clamped}%</span>
        </div>
      )}
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Progresso"}
      >
        <div className="progress-fill" style={{ width: `${clamped}%`, background: color }} />
      </div>
    </div>
  );
}

export function ProgressRing({
  value,
  size = 72,
  color = "var(--color-primary)",
}: {
  value: number;
  size?: number;
  color?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const stroke = 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <svg width={size} height={size} className="progress-ring" role="img" aria-label={`${clamped}% concluido`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" className="progress-ring-text" dominantBaseline="central" textAnchor="middle">
        {clamped}%
      </text>
    </svg>
  );
}

export function StepperDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="stepper" aria-label={`Etapa ${current + 1} de ${total}`}>
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`stepper-dot ${i < current ? "done" : i === current ? "current" : ""}`}
        />
      ))}
    </div>
  );
}
