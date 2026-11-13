import { useCallback, useEffect, useState } from "react";
import * as api from "../../api/client";
import type { ReviewFlag, ReviewItem, ReviewKind } from "../../api/client";
import Markdown, { MathText } from "../Markdown";

const KINDS: { id: ReviewKind; label: string }[] = [
  { id: "feedback", label: "Feedback socratico" },
  { id: "hint", label: "Dicas" },
  { id: "question", label: "Gabaritos gerados" },
];

const LEAK_OPTIONS = [
  { verdict: "nao_vazou", label: "Nao entrega a resposta", tone: "ok" },
  { verdict: "vazou", label: "Entrega a resposta", tone: "bad" },
];

const QUESTION_OPTIONS = [
  { verdict: "correto", label: "Gabarito correto", tone: "ok" },
  { verdict: "ambiguo", label: "Ambigua / mal escrita", tone: "warn" },
  { verdict: "errado", label: "Gabarito errado", tone: "bad" },
];

const VERDICT_LABEL: Record<string, string> = {
  nao_vazou: "Nao entrega a resposta",
  vazou: "Entrega a resposta",
  correto: "Gabarito correto",
  ambiguo: "Ambigua",
  errado: "Gabarito errado",
};

const INTRO: Record<ReviewKind, string> = {
  feedback:
    "Feedbacks do modo de perguntas guiadas, depois que o aluno errou. Leia o texto ORIGINAL da IA e marque se ele entregava a resposta correta (dar o valor final, apontar a alternativa certa, fazer a conta toda).",
  hint: "Dicas pedidas antes de responder. Mesma pergunta: o texto original da IA entregava a resposta?",
  question:
    "Questoes criadas pela IA. Resolva e confira se o gabarito marcado esta certo. Marcar como errado tira a questao dos proximos questionarios (o historico dos alunos continua).",
};

function QuestionBlock({ item }: { item: ReviewItem }) {
  const q = item.question;
  return (
    <div className="review-question">
      <div className="review-meta">
        {q.module_title && <span className="badge">{q.module_title}</span>}
        {q.topic && q.topic !== q.module_title && <span className="badge">{q.topic}</span>}
        <span className="badge">Questao #{q.id}</span>
        {!q.active && <span className="badge badge-warning">Fora de circulacao</span>}
      </div>
      <div className="review-statement">
        <Markdown text={q.statement} />
      </div>
      <ol className="review-alts">
        {q.alternatives.map((a) => {
          const correct = a.id === q.correct_alternative_id;
          const chosen = a.id === item.chosen_alternative_id;
          return (
            <li key={a.id} className={`${correct ? "is-correct" : ""} ${chosen ? "is-chosen" : ""}`}>
              <span className="review-alt-id">{a.id})</span>
              <span className="review-alt-text">
                <MathText text={a.text} />
              </span>
              {correct && <span className="review-tag ok">gabarito</span>}
              {chosen && <span className="review-tag bad">aluno marcou</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ItemCard({
  item,
  blind,
  onSave,
  onUndo,
  busy,
}: {
  item: ReviewItem;
  blind: boolean;
  onSave: (verdict: string, note: string) => void;
  onUndo?: () => void;
  busy: boolean;
}) {
  const [note, setNote] = useState(item.note ?? "");
  const [showSolution, setShowSolution] = useState(false);
  const options = item.kind === "question" ? QUESTION_OPTIONS : LEAK_OPTIONS;

  useEffect(() => {
    setNote(item.note ?? "");
    setShowSolution(false);
  }, [item.kind, item.id, item.note]);

  return (
    <article className="review-card">
      <QuestionBlock item={item} />

      {item.kind === "question" ? (
        <div className="review-solution">
          <button type="button" className="link-button" onClick={() => setShowSolution((v) => !v)}>
            {showSolution ? "Esconder resolucao da IA" : "Ver resolucao da IA"}
          </button>
          {showSolution && (
            <div className="review-text">
              <Markdown text={item.question.explanation} />
            </div>
          )}
        </div>
      ) : (
        <div className="review-ai">
          <p className="section-label">
            {item.kind === "hint" ? `Dica ${item.hint_number} — texto original da IA` : "Texto original da IA"}
          </p>
          <div className="review-text">
            <Markdown text={item.ai_text ?? ""} />
          </div>
          {!blind && (
            <p className="review-filter">
              Filtro automatico:{" "}
              <strong className={item.filter_flagged ? "tone-bad" : "tone-ok"}>
                {item.filter_flagged ? "barrou (aluno viu o texto de reserva)" : "liberou (aluno viu este texto)"}
              </strong>
            </p>
          )}
        </div>
      )}

      <label className="review-note">
        Observacao (opcional)
        <input
          type="text"
          value={note}
          maxLength={300}
          placeholder="Ex.: da o valor final na segunda frase"
          onChange={(e) => setNote(e.target.value)}
        />
      </label>

      <div className="review-actions">
        {options.map((o) => (
          <button
            key={o.verdict}
            type="button"
            disabled={busy}
            className={`review-btn tone-${o.tone}${item.verdict === o.verdict ? " is-selected" : ""}`}
            onClick={() => onSave(o.verdict, note)}
          >
            {o.label}
          </button>
        ))}
        {onUndo && (
          <button type="button" className="link-button" disabled={busy} onClick={onUndo}>
            Desfazer marcacao
          </button>
        )}
      </div>
    </article>
  );
}

export default function ReviewPanel() {
  const [kind, setKind] = useState<ReviewKind>("feedback");
  const [status, setStatus] = useState<"pending" | "done">("pending");
  const [flag, setFlag] = useState<ReviewFlag>("all");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<string | null>(null);

  const pageSize = status === "pending" ? 1 : 10;
  const isLeak = kind !== "question";
  // Revisao cega: na fila de pendentes misturada, a decisao do filtro so
  // aparece depois de marcar, para nao influenciar quem revisa.
  const blind = status === "pending" && flag === "all";

  const load = useCallback(() => {
    setLoading(true);
    api
      .getReviewItems(kind, { status, flag: isLeak ? flag : "all", limit: pageSize, offset })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"))
      .finally(() => setLoading(false));
  }, [kind, status, flag, offset, pageSize, isLeak]);

  useEffect(load, [load]);

  function changeKind(k: ReviewKind) {
    setKind(k);
    setOffset(0);
    setLast(null);
  }

  async function save(item: ReviewItem, verdict: string, note: string) {
    setBusy(true);
    try {
      await api.saveReview(item.kind, item.id, verdict, note);
      if (item.kind !== "question" && status === "pending") {
        const leaked = verdict === "vazou";
        const agreed = leaked === !!item.filter_flagged;
        setLast(
          `Salvo. O filtro tinha ${item.filter_flagged ? "barrado" : "liberado"} esse texto — ${
            agreed ? "concordou com voce." : "discordou de voce."
          }`,
        );
      } else {
        setLast(status === "pending" ? "Salvo." : null);
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setBusy(false);
    }
  }

  async function undo(item: ReviewItem) {
    setBusy(true);
    try {
      await api.deleteReview(item.kind, item.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="review-panel">
      <div className="tabs review-kinds" role="tablist">
        {KINDS.map((k) => (
          <button
            key={k.id}
            type="button"
            role="tab"
            aria-selected={kind === k.id}
            className={`tab${kind === k.id ? " active" : ""}`}
            onClick={() => changeKind(k.id)}
          >
            {k.label}
          </button>
        ))}
      </div>

      <p className="hint">{INTRO[kind]}</p>

      <div className="review-filters">
        <label>
          Mostrar
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as "pending" | "done");
              setOffset(0);
              setLast(null);
            }}
          >
            <option value="pending">Pendentes</option>
            <option value="done">Ja revisados</option>
          </select>
        </label>
        {isLeak && (
          <label>
            Grupo
            <select
              value={flag}
              onChange={(e) => {
                setFlag(e.target.value as ReviewFlag);
                setOffset(0);
                setLast(null);
              }}
            >
              <option value="all">Todos (revisao cega)</option>
              <option value="flagged">So os barrados pelo filtro</option>
              <option value="passed">So os liberados pelo filtro</option>
            </select>
          </label>
        )}
        <span className="review-count">
          {total} {status === "pending" ? "pendente(s)" : "revisado(s)"}
        </span>
      </div>

      {last && <p className="review-last">{last}</p>}
      {error && <div className="card error">{error}</div>}

      {loading && items.length === 0 ? (
        <p className="hint">Carregando...</p>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <p>
            {status === "pending"
              ? "Nada pendente aqui. Quando os alunos usarem o sistema, os novos textos aparecem nesta fila."
              : "Nenhuma marcacao ainda."}
          </p>
        </div>
      ) : (
        <div className="review-list">
          {items.map((item) => (
            <div key={`${item.kind}-${item.id}`}>
              {status === "done" && item.verdict && (
                <p className="review-done-label">
                  Sua marcacao: <strong>{VERDICT_LABEL[item.verdict] ?? item.verdict}</strong>
                </p>
              )}
              <ItemCard
                item={item}
                blind={blind}
                busy={busy}
                onSave={(v, n) => save(item, v, n)}
                onUndo={status === "done" ? () => undo(item) : undefined}
              />
            </div>
          ))}
        </div>
      )}

      {status === "done" && total > pageSize && (
        <div className="review-pager">
          <button
            type="button"
            className="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - pageSize))}
          >
            Anteriores
          </button>
          <span>
            {offset + 1}–{Math.min(offset + pageSize, total)} de {total}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={offset + pageSize >= total}
            onClick={() => setOffset(offset + pageSize)}
          >
            Proximos
          </button>
        </div>
      )}
    </div>
  );
}
