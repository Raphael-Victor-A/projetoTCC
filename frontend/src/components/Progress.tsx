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

/**
 * Barra de etapas.
 *
 * Com `results`, cada etapa respondida mostra o resultado: verde = acertou,
 * vermelho = errou. Sem `results` (ex.: diagnostico, onde o aluno nao ve a
 * correcao), as etapas passadas ficam so marcadas como "respondida", numa cor
 * neutra que nao sugere acerto.
 */
export function StepperDots({
  total,
  current,
  results,
}: {
  total: number;
  current: number;
  results?: (boolean | null | undefined)[];
}) {
  return (
    <div className="stepper" aria-label={`Etapa ${current + 1} de ${total}`}>
      {Array.from({ length: total }).map((_, i) => {
        const result = results?.[i];
        let state = "";
        let label = `Questao ${i + 1}`;
        if (result === true) {
          state = "correct";
          label += ": acertou";
        } else if (result === false) {
          state = "wrong";
          label += ": errou";
        } else if (i === current) {
          state = "current";
          label += ": atual";
        } else if (i < current) {
          state = "done";
          label += ": respondida";
        }
        return <div key={i} className={`stepper-dot ${state}`} title={label} aria-label={label} />;
      })}
    </div>
  );
}
