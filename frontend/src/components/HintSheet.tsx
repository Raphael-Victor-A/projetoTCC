import { useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import type { HintsOut } from "../api/client";
import Markdown from "./Markdown";
import { LightbulbIcon } from "./Icons";

/**
 * Janela do botao "Preciso de ajuda": o tutor da uma dica sobre a questao
 * atual, como um professor durante a prova — orienta sem entregar a resposta.
 *
 * As dicas sao graduais (cada uma mais concreta) e limitadas por questao; o
 * servidor controla a contagem, entao reabrir a janela ou recarregar a pagina
 * mostra as mesmas dicas em vez de gerar novas.
 */
export default function HintSheet({
  questionId,
  quizId,
  onClose,
}: {
  questionId: number;
  quizId?: number | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<HintsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Evita pedir a primeira dica duas vezes (StrictMode monta o efeito 2x em dev).
  const started = useRef(false);

  async function askNext() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.requestHint(questionId, quizId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao consegui buscar uma dica agora.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const current = await api.getHints(questionId);
        if (current.hints.length > 0) {
          setData(current);
          setLoading(false);
        } else {
          // Abriu a ajuda pela primeira vez nesta questao: ja traz a dica 1.
          await askNext();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nao consegui buscar uma dica agora.");
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const hints = data?.hints ?? [];
  const remaining = data?.remaining ?? 0;

  return (
    <div className="help-overlay" onClick={onClose}>
      <div
        className="help-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hint-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="hint-title" className="hint-title">
          <LightbulbIcon size={20} /> Uma dica do tutor
        </h3>

        <div className="hint-list" aria-live="polite">
          {hints.map((h) => (
            <div key={h.number} className="hint-item">
              <span className="hint-number">
                Dica {h.number} de {data?.max_hints}
              </span>
              <div className="feedback-text">
                <Markdown text={h.content} />
              </div>
            </div>
          ))}

          {loading && (
            <div className="hint-item hint-loading">
              <p className="feedback-placeholder">Pensando numa dica pra voce...</p>
            </div>
          )}
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {!loading && data && remaining === 0 && !data.degraded && (
          <p className="hint-done">
            Voce ja usou todas as dicas desta questao. Agora e com voce: confia no seu raciocinio!
          </p>
        )}

        <div className="button-row" style={{ marginTop: "1.25rem" }}>
          <button type="button" onClick={onClose} style={{ flex: 1 }}>
            Voltar para a questao
          </button>
          {!loading && remaining > 0 && (
            <button type="button" className="secondary" onClick={askNext}>
              {hints.length === 0 || error ? "Tentar de novo" : "Quero outra dica"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
