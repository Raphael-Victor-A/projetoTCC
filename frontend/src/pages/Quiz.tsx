import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../api/client";
import type { QuizAnswerResult, QuizOut, QuizResult } from "../api/client";
import QuestionCard from "../components/QuestionCard";
import AiFeedback from "../components/AiFeedback";
import { ProgressBar, StepperDots } from "../components/Progress";
import { LoadingCard } from "../components/Loading";
import {
  ArrowRightIcon,
  BookIcon,
  CheckIcon,
  HelpCircleIcon,
  LightbulbIcon,
  TrophyIcon,
} from "../components/Icons";
import HintSheet from "../components/HintSheet";
import PauseButton from "../components/PauseButton";

/**
 * Questionario completo.
 *
 * Todas as questoes chegam na resposta de `POST /quiz/start` — uma unica
 * chamada de IA no backend. Navegar entre elas e trocar de indice em memoria:
 * nao ha espera entre uma questao e a proxima.
 */
export default function Quiz() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const moduleParam = params.get("module");
  const quizParam = params.get("id");
  const kind = (params.get("kind") as api.QuizKind | null) ?? "reforco";

  const [quiz, setQuiz] = useState<QuizOut | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [answer, setAnswer] = useState<QuizAnswerResult | null>(null);
  const [finalResult, setFinalResult] = useState<QuizResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = quizParam
        ? await api.getQuiz(Number(quizParam))
        : await api.startQuiz(moduleParam ? Number(moduleParam) : null, kind);
      setQuiz(data);
      setIndex(Math.min(data.current_index, Math.max(0, data.questions.length - 1)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel montar o questionario.");
    } finally {
      setLoading(false);
    }
  }, [moduleParam, quizParam, kind]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <LoadingCard
        title="Montando seu questionario"
        messages={[
          "Selecionando questoes do seu nivel...",
          "Cobrindo os conteudos em que voce precisa reforcar...",
          "Gerando todas as questoes de uma vez so...",
        ]}
      />
    );
  }

  if (error && !quiz) {
    return (
      <div className="card">
        <p className="error">{error}</p>
        <button onClick={load}>Tentar de novo</button>
      </div>
    );
  }

  if (!quiz) return null;

  if (finalResult) {
    const step = finalResult.next_step;
    const goNext = () => {
      if (step.kind === "lesson" && step.module_id) navigate(`/lesson?module=${step.module_id}`);
      else if (step.kind === "quiz" && step.module_id) navigate(`/quiz?module=${step.module_id}`);
      else navigate("/dashboard");
    };

    return (
      <div className="card text-center">
        <div className="hero-icon success">
          <TrophyIcon size={30} />
        </div>
        <h1>Questionario concluido</h1>
        <p className="subtitle">
          Voce acertou {finalResult.correct_count} de {finalResult.total} ({finalResult.accuracy}%).
        </p>
        <ProgressBar value={finalResult.accuracy} label="Aproveitamento" />
        <p className="next-step-message">{step.message}</p>
        <div className="button-row" style={{ marginTop: "1.5rem" }}>
          <button type="button" className="secondary" onClick={() => navigate("/dashboard")}>
            Ver minha trilha
          </button>
          <button onClick={goNext} style={{ flex: 1 }}>
            {step.kind === "lesson" ? (
              <>
                Ir para a mini aula <BookIcon size={18} />
              </>
            ) : step.kind === "quiz" ? (
              <>
                Proximo questionario <ArrowRightIcon size={18} />
              </>
            ) : (
              <>
                Continuar <ArrowRightIcon size={18} />
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  const question = quiz.questions[index];
  const isLast = index === quiz.questions.length - 1;

  async function handleAnswer() {
    if (!selected || !question) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.answerQuiz(quiz!.id, question.id, selected);
      setAnswer(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel enviar sua resposta.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleNext() {
    if (!isLast) {
      setIndex(index + 1);
      setSelected(null);
      setAnswer(null);
      setShowHelp(false);
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.finishQuiz(quiz!.id);
      setFinalResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel finalizar o questionario.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <div className="quiz-header">
        <div>
          <p className="quiz-kind">{quiz.kind === "reforco" ? "Reforco" : "Pratica"}</p>
          {quiz.module_title && <p className="quiz-module">{quiz.module_title}</p>}
        </div>
        <div className="quiz-header-actions">
          <span className="quiz-counter">
            {index + 1}/{quiz.questions.length}
          </span>
          <PauseButton message="As respostas que voce ja enviou ficam salvas. Quando voltar para este conteudo, voce continua de onde parou." />
        </div>
      </div>

      <StepperDots total={quiz.questions.length} current={index} />

      <QuestionCard
        question={question}
        selected={selected}
        onSelect={setSelected}
        locked={!!answer}
        correctAlternativeId={answer?.correct_alternative_id ?? null}
        showResult={!!answer}
      />

      {error && (
        <p className="error" role="alert" style={{ marginBottom: "1rem" }}>
          {error}
        </p>
      )}

      {answer && (
        <div className={answer.correct ? "result-box result-correct" : "result-box result-wrong"}>
          <div className="result-title">
            {answer.correct ? <CheckIcon /> : <LightbulbIcon />}
            {answer.correct ? "Isso mesmo! Muito bem." : "Quase! Vamos pensar juntos."}
          </div>
          {answer.correct && answer.explanation && (
            <p className="result-explanation">{answer.explanation}</p>
          )}
          {!answer.correct && answer.feedback_available && (
            <AiFeedback attemptId={answer.attempt_id} />
          )}
        </div>
      )}

      <div className="button-row" style={{ marginTop: "1.5rem" }}>
        {!answer ? (
          <>
            <button disabled={!selected || submitting} onClick={handleAnswer} style={{ flex: 1 }}>
              {submitting ? "Corrigindo..." : "Responder"}
            </button>
            <button type="button" className="help-fab" onClick={() => setShowHelp(true)}>
              <HelpCircleIcon size={18} /> Preciso de ajuda
            </button>
          </>
        ) : (
          <button disabled={submitting} onClick={handleNext} style={{ flex: 1 }}>
            {isLast ? "Finalizar questionario" : "Proxima questao"} <ArrowRightIcon size={18} />
          </button>
        )}
      </div>

      {showHelp && !answer && (
        <HintSheet
          key={question.id}
          questionId={question.id}
          quizId={quiz.id}
          onClose={() => setShowHelp(false)}
        />
      )}
    </div>
  );
}
