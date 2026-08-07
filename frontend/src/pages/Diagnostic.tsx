import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import type { DiagnosticOut, DiagnosticResult } from "../api/client";
import { useAuth } from "../context/AuthContext";
import QuestionCard from "../components/QuestionCard";
import { StepperDots } from "../components/Progress";
import { LoadingCard } from "../components/Loading";
import { ArrowRightIcon, CheckIcon, SparkleIcon, TargetIcon } from "../components/Icons";

const LEVEL_LABEL: Record<string, string> = {
  basico: "Basico",
  intermediario: "Intermediario",
  avancado: "Avancado",
};

export default function Diagnostic() {
  const [diagnostic, setDiagnostic] = useState<DiagnosticOut | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [step, setStep] = useState<"intro" | number>("intro");
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const { refresh } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getDiagnostic()
      .then(setDiagnostic)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <LoadingCard
        title="Montando seu diagnostico"
        messages={[
          "Sorteando perguntas de varias disciplinas...",
          "Equilibrando os niveis de dificuldade...",
          "Quase la!",
        ]}
      />
    );
  }
  if (error && !diagnostic) return <div className="card error">{error}</div>;
  if (!diagnostic) return null;

  const questions = diagnostic.questions;

  /**
   * Fim do diagnostico.
   *
   * Correcao do bug de primeiro acesso: so navegamos DEPOIS de `refresh()`,
   * que releva o `diagnostic_completed` atualizado do servidor. Antes, a
   * navegacao acontecia com o usuario ainda marcado como "sem diagnostico"
   * em memoria, e o guard de rota devolvia o aluno para este mesmo
   * questionario.
   */
  async function goToPlan() {
    await refresh();
    navigate("/dashboard", { replace: true });
  }

  if (step === "intro") {
    return (
      <div className="card text-center">
        <div className="hero-icon">
          <SparkleIcon size={30} />
        </div>
        <h1>Vamos te conhecer melhor</h1>
        <p className="subtitle">
          Sao {questions.length} perguntas de disciplinas diferentes, do mais simples ao mais
          desafiador. Nao existe nota: e assim que eu monto a sua trilha de estudos.
        </p>
        <button onClick={() => setStep(0)}>
          Comecar <ArrowRightIcon size={18} />
        </button>
      </div>
    );
  }

  if (result) {
    return (
      <div className="card">
        <div className="text-center">
          <div className="hero-icon success">
            <CheckIcon size={30} />
          </div>
          <h1>Prontinho!</h1>
          <p className="subtitle">
            Voce acertou {result.correct_count} de {result.total}. Vou comecar no nivel:
          </p>
          <p className="level-highlight">
            {LEVEL_LABEL[result.assigned_level] ?? result.assigned_level}
          </p>
        </div>

        {result.focus_areas.length > 0 && (
          <>
            <p className="section-label">
              <TargetIcon size={16} /> Onde vamos focar primeiro
            </p>
            <div className="focus-list">
              {result.focus_areas.map((area) => (
                <div className="focus-item" key={area.module_id}>
                  <div>
                    <div className="focus-title">{area.module_title}</div>
                    <div className="focus-subject">{area.subject_name}</div>
                  </div>
                  <span className="focus-score">
                    {area.correct}/{area.total}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        {result.strengths.length > 0 && (
          <>
            <p className="section-label">Voce ja manda bem em</p>
            <div className="badges-row">
              {result.strengths.map((area) => (
                <span className="achievement-badge" key={area.module_id}>
                  <CheckIcon size={16} /> {area.module_title}
                </span>
              ))}
            </div>
          </>
        )}

        <button style={{ width: "100%", marginTop: "1.75rem" }} onClick={goToPlan}>
          Ver minha trilha <ArrowRightIcon size={18} />
        </button>
      </div>
    );
  }

  const index = step as number;
  const question = questions[index];
  const selected = answers[question.id] ?? null;
  const isLast = index === questions.length - 1;

  async function handleContinue() {
    if (!isLast) {
      setStep(index + 1);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = questions.map((q) => ({
        question_id: q.id,
        alternative_id: answers[q.id],
      }));
      const res = await api.submitDiagnostic(diagnostic!.session_id, payload);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <StepperDots total={questions.length} current={index} />
      <p className="stepper-label">
        Pergunta {index + 1} de {questions.length}
      </p>

      <QuestionCard
        question={question}
        selected={selected}
        onSelect={(id) => setAnswers((prev) => ({ ...prev, [question.id]: id }))}
      />

      {error && (
        <p className="error" role="alert" style={{ marginBottom: "1rem" }}>
          {error}
        </p>
      )}

      <div className="button-row">
        {index > 0 && (
          <button type="button" className="secondary" onClick={() => setStep(index - 1)}>
            Voltar
          </button>
        )}
        <button disabled={!selected || submitting} onClick={handleContinue} style={{ flex: 1 }}>
          {submitting ? "Montando sua trilha..." : isLast ? "Finalizar" : "Continuar"}
        </button>
      </div>
    </div>
  );
}
