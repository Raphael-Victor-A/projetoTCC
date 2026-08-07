import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../api/client";
import type { LessonOut } from "../api/client";
import Markdown from "../components/Markdown";
import { LoadingCard, TypingDots } from "../components/Loading";
import { ArrowRightIcon, BookIcon, LayersIcon, RefreshIcon, SparkleIcon } from "../components/Icons";

/**
 * Mini aula entre questionarios.
 *
 * A aula estruturada vem do backend (gerada uma vez e reaproveitada). O botao
 * "explicar de outro jeito" abre um stream: o texto alternativo aparece
 * conforme e escrito, sem espera de bloco.
 */
export default function Lesson() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const moduleParam = params.get("module");
  const lessonParam = params.get("id");

  const [lesson, setLesson] = useState<LessonOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [advancing, setAdvancing] = useState(false);

  const [altText, setAltText] = useState("");
  const [altStreaming, setAltStreaming] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = lessonParam
        ? await api.getLesson(Number(lessonParam))
        : await api.getModuleLesson(Number(moduleParam));
      setLesson(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a mini aula.");
    } finally {
      setLoading(false);
    }
  }, [moduleParam, lessonParam]);

  useEffect(() => {
    load();
    return () => controllerRef.current?.abort();
  }, [load]);

  async function explainAgain() {
    if (!lesson?.module_id) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setAltText("");
    setAltStreaming(true);
    try {
      await api.streamModuleLesson(
        lesson.module_id,
        {
          onChunk: (piece) => setAltText((prev) => prev + piece),
          onError: (message) => setError(message),
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "Nao foi possivel gerar a explicacao.");
      }
    } finally {
      if (!controller.signal.aborted) setAltStreaming(false);
    }
  }

  async function finishLesson() {
    if (!lesson) return;
    setAdvancing(true);
    try {
      const step = await api.completeLesson(lesson.id);
      if (step.kind === "quiz" && step.module_id) navigate(`/quiz?module=${step.module_id}`);
      else if (step.kind === "lesson" && step.module_id) navigate(`/lesson?module=${step.module_id}`);
      else navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel concluir a mini aula.");
    } finally {
      setAdvancing(false);
    }
  }

  if (loading) {
    return (
      <LoadingCard
        title="Preparando sua mini aula"
        messages={[
          "Selecionando os conceitos essenciais...",
          "Escrevendo exemplos resolvidos...",
          "Organizando o resumo final...",
        ]}
      />
    );
  }

  if (error && !lesson) {
    return (
      <div className="card">
        <p className="error">{error}</p>
        <button onClick={load}>Tentar de novo</button>
      </div>
    );
  }

  if (!lesson) return null;

  return (
    <div className="card lesson">
      <p className="lesson-eyebrow">
        <BookIcon size={16} /> Mini aula
      </p>
      <h1>{lesson.title}</h1>
      <p className="subtitle">{lesson.intro}</p>

      {lesson.key_concepts.length > 0 && (
        <div className="concept-box">
          <p className="section-label">
            <LayersIcon size={16} /> Conceitos importantes
          </p>
          <ul className="concept-list">
            {lesson.key_concepts.map((concept, i) => (
              <li key={i}>{concept}</li>
            ))}
          </ul>
        </div>
      )}

      {lesson.sections.map((section, i) => (
        <section className="lesson-section" key={i}>
          <h2>{section.heading}</h2>
          <Markdown text={section.body} />
        </section>
      ))}

      {lesson.diagram && (
        <section className="lesson-section">
          <h2>Diagrama</h2>
          <pre className="diagram-box" aria-label="Diagrama do conteudo">
            {lesson.diagram}
          </pre>
        </section>
      )}

      {lesson.examples.length > 0 && (
        <section className="lesson-section">
          <h2>Exemplos resolvidos</h2>
          {lesson.examples.map((example, i) => (
            <div className="example-box" key={i}>
              <p className="example-title">{example.title}</p>
              <Markdown text={example.statement} />
              <p className="example-solution-label">Resolucao</p>
              <Markdown text={example.solution} />
            </div>
          ))}
        </section>
      )}

      {lesson.summary && (
        <div className="summary-box">
          <p className="section-label">Resumo</p>
          <Markdown text={lesson.summary} />
        </div>
      )}

      {(altText || altStreaming) && (
        <div className="alt-explanation">
          <p className="section-label">
            <SparkleIcon size={16} /> Explicando de outro jeito
          </p>
          {altText ? <Markdown text={altText} /> : <p>Escrevendo<TypingDots /></p>}
          {altStreaming && altText && <span className="stream-cursor" aria-hidden="true" />}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="button-row" style={{ marginTop: "1.75rem" }}>
        <button
          type="button"
          className="secondary"
          onClick={explainAgain}
          disabled={altStreaming || !lesson.module_id}
        >
          <RefreshIcon size={16} /> Explicar de outro jeito
        </button>
        <button onClick={finishLesson} disabled={advancing} style={{ flex: 1 }}>
          {advancing ? "Um momento..." : "Entendi, proximo questionario"} <ArrowRightIcon size={18} />
        </button>
      </div>
    </div>
  );
}
