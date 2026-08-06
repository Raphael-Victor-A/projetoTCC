import { useCallback, useEffect, useState } from "react";
import * as api from "../api/client";
import type { QuestionOut, AnswerResult, ProgressOut } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { CheckIcon, HelpCircleIcon, LightbulbIcon, SparkleIcon } from "../components/Icons";

export default function Exercise() {
  const [question, setQuestion] = useState<QuestionOut | null>(null);
  const [progress, setProgress] = useState<ProgressOut | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const { refresh } = useAuth();

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelected(null);
    try {
      const [q, p] = await Promise.all([api.getNextExercise(), api.getProgress()]);
      setQuestion(q);
      setProgress(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a atividade.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNext();
  }, [loadNext]);

  async function handleContinue() {
    if (!question) return;

    if (result) {
      loadNext();
      return;
    }

    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitExercise(question.id, selected);
      setResult(res);
      const p = await api.getProgress();
      setProgress(p);
      if (res.level_changed) await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel enviar sua resposta.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="card">Preparando sua atividade...</div>;
  if (error && !question) return <div className="card error">{error}</div>;
  if (!question) return null;

  const filledDots = progress ? progress.window_count : 0;

  return (
    <div className="card">
      <div className="stepper" aria-label="Seu progresso nesta etapa">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className={`stepper-dot ${i < filledDots ? "done" : ""}`} />
        ))}
      </div>

      <p className="question-statement">{question.statement}</p>

      <div className="alternatives" role="radiogroup" aria-label="Alternativas">
        {question.alternatives.map((alt) => {
          let extraClass = "";
          if (result) {
            if (alt.id === result.correct_alternative_id) extraClass = "correct-reveal";
            else if (alt.id === selected && !result.correct) extraClass = "wrong-reveal";
          }
          return (
            <label
              key={alt.id}
              className={`alternative ${selected === alt.id ? "selected" : ""} ${result ? "disabled" : ""} ${extraClass}`}
            >
              <input
                type="radio"
                name="alt"
                disabled={!!result}
                checked={selected === alt.id}
                onChange={() => setSelected(alt.id)}
              />
              {alt.text}
            </label>
          );
        })}
      </div>

      {error && (
        <p className="error" role="alert" style={{ marginBottom: "1rem" }}>
          {error}
        </p>
      )}

      {result && (
        <div className={result.correct ? "result-box result-correct" : "result-box result-wrong"}>
          <div className="result-title">
            {result.correct ? <CheckIcon /> : <LightbulbIcon />}
            {result.correct ? "Isso mesmo! Muito bem." : "Quase! Vamos pensar juntos."}
          </div>

          {result.feedback && (
            <div className="feedback-box">
              <div className="feedback-icon">
                <SparkleIcon size={18} />
              </div>
              <p className="feedback-text">{result.feedback.content}</p>
            </div>
          )}

          {result.level_changed && (
            <div className="level-change-banner">
              <SparkleIcon size={18} /> Voce subiu de nivel!
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.5rem", flexWrap: "wrap" }}>
        <button disabled={(!result && !selected) || submitting} onClick={handleContinue} style={{ flex: 1 }}>
          {submitting ? "Um momento..." : "Continuar"}
        </button>
        <button type="button" className="help-fab" onClick={() => setShowHelp(true)}>
          <HelpCircleIcon size={18} /> Preciso de ajuda
        </button>
      </div>

      {showHelp && (
        <div className="help-overlay" onClick={() => setShowHelp(false)}>
          <div className="help-sheet" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>Sem pressa!</h3>
            <p>Leia a pergunta com calma e escolha a alternativa que fizer mais sentido pra voce.</p>
            <p>Se errar, tudo bem! Eu vou te dar uma dica pra pensar de outro jeito, sem so entregar a resposta.</p>
            <button onClick={() => setShowHelp(false)}>Entendi</button>
          </div>
        </div>
      )}
    </div>
  );
}
