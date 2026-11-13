import { useCallback, useEffect, useState } from "react";
import * as api from "../api/client";
import type { AnswerResult, ProgressOut, QuestionOut } from "../api/client";
import { useAuth } from "../context/AuthContext";
import QuestionCard from "../components/QuestionCard";
import AiFeedback from "../components/AiFeedback";
import { StepperDots } from "../components/Progress";
import { LoadingCard } from "../components/Loading";
import { CheckIcon, HelpCircleIcon, LightbulbIcon, SparkleIcon } from "../components/Icons";
import HintSheet from "../components/HintSheet";
import PauseButton from "../components/PauseButton";

/**
 * Exercicios avulsos (pratica livre, fora da trilha).
 *
 * A submissao devolve a correcao na hora — o feedback pedagogico chega
 * depois, em streaming, via <AiFeedback>. Antes, esta tela ficava parada ate
 * a IA terminar de escrever a explicacao inteira.
 */
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
    setShowHelp(false);
    try {
      // Questao e progresso sao independentes: buscados em paralelo.
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

  if (loading) {
    return (
      <LoadingCard
        title="Preparando sua atividade"
        messages={["Escolhendo a proxima questao...", "Ajustando ao seu nivel..."]}
      />
    );
  }
  if (error && !question) return <div className="card error">{error}</div>;
  if (!question) return null;

  const filledDots = progress ? progress.window_count : 0;

  return (
    <div className="card">
      <div className="activity-topbar">
        <span className="activity-label">Pratica livre</span>
        <PauseButton message="As respostas que voce ja enviou ficam salvas. Quando quiser continuar, e so abrir a Pratica livre de novo." />
      </div>

      <StepperDots total={5} current={filledDots} results={progress?.window_results} />

      <QuestionCard
        question={question}
        selected={selected}
        onSelect={setSelected}
        locked={!!result}
        correctAlternativeId={result?.correct_alternative_id ?? null}
        showResult={!!result}
      />

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

          {result.feedback_available && result.attempt_id && (
            <AiFeedback attemptId={result.attempt_id} />
          )}

          {result.level_changed && (
            <div className="level-change-banner">
              <SparkleIcon size={18} /> Voce subiu de nivel!
            </div>
          )}
        </div>
      )}

      <div className="button-row" style={{ marginTop: "1.5rem" }}>
        <button disabled={(!result && !selected) || submitting} onClick={handleContinue} style={{ flex: 1 }}>
          {submitting ? "Corrigindo..." : result ? "Proxima questao" : "Responder"}
        </button>
        {/* Depois de responder, quem ajuda e o feedback do erro; a dica e para antes. */}
        {!result && (
          <button type="button" className="help-fab" onClick={() => setShowHelp(true)}>
            <HelpCircleIcon size={18} /> Preciso de ajuda
          </button>
        )}
      </div>

      {showHelp && !result && (
        <HintSheet key={question.id} questionId={question.id} onClose={() => setShowHelp(false)} />
      )}
    </div>
  );
}
