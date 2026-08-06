import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import type { QuestionOut, DiagnosticResult } from "../api/client";
import { ArrowRightIcon, CheckIcon, SparkleIcon } from "../components/Icons";

const LEVEL_LABEL: Record<string, string> = {
  basico: "Basico",
  intermediario: "Intermediario",
  avancado: "Avancado",
};

export default function Diagnostic() {
  const [questions, setQuestions] = useState<QuestionOut[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [step, setStep] = useState<"intro" | number>("intro");
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getDiagnostic()
      .then(setQuestions)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card">Preparando suas perguntas...</div>;
  if (error) return <div className="card error">{error}</div>;

  if (step === "intro") {
    return (
      <div className="card text-center">
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "var(--color-primary-bg)",
            color: "var(--color-primary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
          }}
        >
          <SparkleIcon size={30} />
        </div>
        <h1>Vamos te conhecer melhor</h1>
        <p className="subtitle">
          Sao so {questions.length} perguntinhas rapidas. Nao existe nota, e so pra eu saber por onde comecar
          com voce.
        </p>
        <button onClick={() => setStep(0)}>Começar</button>
      </div>
    );
  }

  if (result) {
    return (
      <div className="card text-center">
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "var(--color-success-bg)",
            color: "var(--color-success)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
          }}
        >
          <CheckIcon size={30} />
        </div>
        <h1>Prontinho!</h1>
        <p className="subtitle">
          Voce acertou {result.correct_count} de {result.total}. Vou comecar te passando atividades do nivel:
        </p>
        <p style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--color-primary-dark)", marginBottom: "1.75rem" }}>
          {LEVEL_LABEL[result.assigned_level] ?? result.assigned_level}
        </p>
        <button onClick={() => navigate("/exercise")}>
          Vamos começar! <ArrowRightIcon size={18} />
        </button>
      </div>
    );
  }

  const index = step as number;
  const question = questions[index];
  const selected = answers[question.id];
  const isLast = index === questions.length - 1;

  async function handleContinue() {
    if (isLast) {
      setSubmitting(true);
      setError(null);
      try {
        const payload = questions.map((q) => ({ question_id: q.id, alternative_id: answers[q.id] }));
        const res = await api.submitDiagnostic(payload);
        setResult(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro inesperado");
      } finally {
        setSubmitting(false);
      }
    } else {
      setStep(index + 1);
    }
  }

  return (
    <div className="card">
      <div className="stepper" aria-label={`Pergunta ${index + 1} de ${questions.length}`}>
        {questions.map((q, i) => (
          <div key={q.id} className={`stepper-dot ${i < index ? "done" : i === index ? "current" : ""}`} />
        ))}
      </div>
      <p className="stepper-label">
        Pergunta {index + 1} de {questions.length}
      </p>

      <p className="question-statement">{question.statement}</p>

      <div className="alternatives" role="radiogroup" aria-label="Alternativas">
        {question.alternatives.map((alt) => (
          <label key={alt.id} className={`alternative ${selected === alt.id ? "selected" : ""}`}>
            <input
              type="radio"
              name={`q-${question.id}`}
              checked={selected === alt.id}
              onChange={() => setAnswers((prev) => ({ ...prev, [question.id]: alt.id }))}
            />
            {alt.text}
          </label>
        ))}
      </div>

      {error && (
        <p className="error" role="alert" style={{ marginBottom: "1rem" }}>
          {error}
        </p>
      )}

      <button disabled={!selected || submitting} onClick={handleContinue}>
        {submitting ? "Um momento..." : "Continuar"}
      </button>
    </div>
  );
}
