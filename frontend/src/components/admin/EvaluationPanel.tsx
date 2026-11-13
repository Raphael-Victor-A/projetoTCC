import { useEffect, useState } from "react";
import * as api from "../../api/client";
import type { Confusion, Evaluation, LatencyStats } from "../../api/client";

const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;

const secs = (ms: number) => (ms ? `${(ms / 1000).toFixed(1)}s` : "—");

function Tile({ value, label, sub }: { value: string | number; label: string; sub?: string }) {
  return (
    <div className="stat-tile">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {sub && <span className="eval-tile-sub">{sub}</span>}
    </div>
  );
}

function LatencyRow({ name, l }: { name: string; l: LatencyStats }) {
  return (
    <tr>
      <th scope="row">{name}</th>
      <td>{l.n}</td>
      <td>{secs(l.avg_ms)}</td>
      <td>{secs(l.p50_ms)}</td>
      <td>{secs(l.p95_ms)}</td>
    </tr>
  );
}

function ConfusionRow({ name, c }: { name: string; c: Confusion }) {
  return (
    <tr>
      <th scope="row">{name}</th>
      <td>
        {c.reviewed} / {c.reviewable}
      </td>
      <td>{c.tp}</td>
      <td>{c.fp}</td>
      <td>{c.fn}</td>
      <td>{c.tn}</td>
      <td>{pct(c.precision)}</td>
      <td>{pct(c.escape_rate, 1)}</td>
      <td>{pct(c.recall_estimate)}</td>
    </tr>
  );
}

function DailyChart({ daily }: { daily: Evaluation["daily"] }) {
  const max = Math.max(1, ...daily.map((d) => d.feedback + d.hints));
  const total = daily.reduce((s, d) => s + d.feedback + d.hints, 0);
  const [hover, setHover] = useState<number | null>(null);
  const fmt = (iso: string) => {
    const [, m, d] = iso.split("-");
    return `${d}/${m}`;
  };

  return (
    <figure className="eval-chart" aria-label="Textos gerados pela IA por dia">
      <div className="eval-chart-plot" onMouseLeave={() => setHover(null)}>
        {daily.map((d, i) => {
          const v = d.feedback + d.hints;
          return (
            <div
              key={d.date}
              className={`eval-bar-slot${hover === i ? " is-hover" : ""}`}
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              tabIndex={0}
            >
              {v > 0 && <div className="eval-bar" style={{ height: `${(v / max) * 100}%` }} />}
              {hover === i && (
                <div className="eval-tip" role="tooltip">
                  <strong>{fmt(d.date)}</strong>
                  <span>{d.feedback} feedbacks</span>
                  <span>{d.hints} dicas</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="eval-chart-axis">
        <span>{fmt(daily[0].date)}</span>
        <span>{fmt(daily[daily.length - 1].date)}</span>
      </div>
      <figcaption className="hint">
        {total} textos (feedbacks + dicas) nos ultimos 14 dias. Passe o mouse em uma barra para ver o dia.
      </figcaption>
    </figure>
  );
}

export default function EvaluationPanel() {
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function load() {
    setLoading(true);
    api
      .getEvaluation()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  if (error) return <div className="card error">{error}</div>;
  if (!data) return <p className="hint">Carregando metricas...</p>;

  const { feedback: fb, hints: h, content: c, leak_review: lr, question_review: qr } = data;
  const since = data.since ? new Date(data.since).toLocaleDateString("pt-BR") : null;

  return (
    <div className="eval-panel">
      <div className="eval-head">
        <p className="hint">
          Dados do uso real{since ? ` desde ${since}` : ""}. Contas de admin nao entram nas metricas.
          Nada aqui faz chamadas novas a IA.
        </p>
        <button type="button" className="secondary" onClick={load} disabled={loading}>
          {loading ? "Atualizando..." : "Atualizar"}
        </button>
      </div>

      <section className="eval-section">
        <h3>Filtro anti-vazamento</h3>
        <p className="hint">
          Quantas vezes a IA escreveu algo que entregava a resposta e o filtro trocou o texto por um de reserva antes
          de chegar ao aluno. Vale para o feedback socratico e para todas as dicas.
        </p>
        <div className="stat-grid">
          <Tile value={fb.filter_scope} label="Feedbacks socraticos gerados" />
          <Tile value={fb.filtered} label="Feedbacks barrados" sub={pct(fb.filtered_rate, 1)} />
          <Tile value={h.filter_scope} label="Dicas geradas" />
          <Tile value={h.filtered} label="Dicas barradas" sub={pct(h.filtered_rate, 1)} />
        </div>
      </section>

      <section className="eval-section">
        <h3>Tempo de resposta da IA</h3>
        <div className="eval-table-wrap">
          <table className="eval-table">
            <thead>
              <tr>
                <th scope="col">Tipo</th>
                <th scope="col">Chamadas</th>
                <th scope="col">Media</th>
                <th scope="col">Mediana</th>
                <th scope="col">P95</th>
              </tr>
            </thead>
            <tbody>
              <LatencyRow name="Feedback apos erro" l={fb.latency} />
              <LatencyRow name="Dica" l={h.latency} />
            </tbody>
          </table>
        </div>
        <p className="hint">
          P95: 95% das respostas chegaram em ate esse tempo. No feedback de explicacao direta o texto aparece aos
          poucos (streaming), entao o aluno comeca a ler antes desse tempo total.
        </p>
      </section>

      <section className="eval-section">
        <h3>Disponibilidade e economia de chamadas</h3>
        <div className="stat-grid">
          <Tile
            value={fb.unavailable + h.unavailable}
            label="Vezes que a IA ficou indisponivel"
            sub="o aluno recebeu um texto de reserva"
          />
          <Tile value={h.reused} label="Dicas reaproveitadas" sub="sem nova chamada a IA" />
          <Tile
            value={c.lesson_calls_saved}
            label="Mini aulas reaproveitadas"
            sub={`${c.lessons_generated} geradas, ${c.lesson_views} abertas`}
          />
          <Tile
            value={c.generated_questions}
            label="Questoes geradas pela IA"
            sub={`+ ${c.bank_questions} do banco fixo`}
          />
        </div>
      </section>

      <section className="eval-section">
        <h3>Uso por dia</h3>
        <DailyChart daily={data.daily} />
      </section>

      <section className="eval-section">
        <h3>Resultado da revisao manual</h3>
        <p className="hint">
          Calculado a partir das marcacoes da aba "Revisao manual". VP = barrado e vazava; FP = barrado sem vazar;
          FN = liberado mas vazava (chegou ao aluno); VN = liberado e nao vazava.
        </p>
        <div className="eval-table-wrap">
          <table className="eval-table">
            <thead>
              <tr>
                <th scope="col">Canal</th>
                <th scope="col">Revisados</th>
                <th scope="col">VP</th>
                <th scope="col">FP</th>
                <th scope="col">FN</th>
                <th scope="col">VN</th>
                <th scope="col">Precisao</th>
                <th scope="col">Escape</th>
                <th scope="col">Revocacao*</th>
              </tr>
            </thead>
            <tbody>
              <ConfusionRow name="Feedback" c={lr.feedback} />
              <ConfusionRow name="Dicas" c={lr.hint} />
              <ConfusionRow name="Total" c={lr.total} />
            </tbody>
          </table>
        </div>
        <ul className="eval-notes">
          <li>
            <strong>Precisao:</strong> dos textos que o filtro barrou, quantos realmente entregavam a resposta.
          </li>
          <li>
            <strong>Escape:</strong> dos textos que o filtro liberou, quantos entregavam a resposta mesmo assim.
            {lr.total.leaks_reaching_students_estimate !== null && (
              <>
                {" "}
                Projetado no total: cerca de {lr.total.leaks_reaching_students_estimate.toFixed(1)} de{" "}
                {lr.total.passed_total} textos liberados.
              </>
            )}
          </li>
          <li>
            <strong>*Revocacao (estimada):</strong> de todos os textos que vazavam, quantos o filtro pegou. Como os
            barrados sao poucos, revise amostras dos dois grupos; a estimativa projeta cada taxa no total do grupo.
          </li>
        </ul>

        <div className="stat-grid">
          <Tile value={`${qr.reviewed} / ${qr.generated_total}`} label="Questoes geradas revisadas" />
          <Tile value={qr.correct} label="Gabarito correto" />
          <Tile value={qr.wrong} label="Gabarito errado" sub={`${pct(qr.wrong_rate, 1)} das revisadas`} />
          <Tile value={qr.ambiguous} label="Ambiguas" />
          <Tile value={c.retired_questions} label="Questoes fora de circulacao" />
        </div>
      </section>
    </div>
  );
}
