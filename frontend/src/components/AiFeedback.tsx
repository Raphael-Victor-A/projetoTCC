import { useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import Markdown from "./Markdown";
import { TypingDots } from "./Loading";
import { SparkleIcon } from "./Icons";

/**
 * Feedback pedagogico do erro, exibido conforme e gerado.
 *
 * O texto comeca a aparecer no primeiro trecho recebido, entao o aluno nunca
 * encara um retangulo vazio esperando a IA terminar de escrever. O stream e
 * abortado no unmount para nao deixar requisicao pendurada ao trocar de
 * questao rapidamente.
 */
export default function AiFeedback({ attemptId }: { attemptId: number }) {
  const [text, setText] = useState("");
  const [streaming, setStreaming] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    setText("");
    setError(null);
    setStreaming(true);

    api
      .streamFeedback(
        attemptId,
        {
          onChunk: (piece) => setText((prev) => prev + piece),
          onError: (message) => setError(message),
          onDone: () => setStreaming(false),
        },
        controller.signal,
      )
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Nao foi possivel carregar o feedback.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setStreaming(false);
      });

    return () => controller.abort();
  }, [attemptId]);

  return (
    <div className="feedback-box">
      <div className="feedback-icon">
        <SparkleIcon size={18} />
      </div>
      <div className="feedback-text">
        {text ? <Markdown text={text} /> : null}
        {!text && streaming && (
          <p className="feedback-placeholder">
            Pensando em como te ajudar
            <TypingDots />
          </p>
        )}
        {streaming && text && <span className="stream-cursor" aria-hidden="true" />}
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
