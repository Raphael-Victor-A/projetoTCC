import { useEffect, useState } from "react";
import { SparkleIcon } from "./Icons";

/**
 * Feedback visual durante geracao de conteudo.
 *
 * Espera sem sinal de progresso e percebida como travamento. Estes
 * componentes existem para que o aluno sempre veja algo acontecendo: linhas
 * fantasma no lugar do conteudo que vem a caminho e uma mensagem que troca
 * ao longo da espera.
 */

export function Skeleton({ lines = 3, width = "100%" }: { lines?: number; width?: string }) {
  return (
    <div className="skeleton-group" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton-line"
          style={{ width: i === lines - 1 ? "70%" : width }}
        />
      ))}
    </div>
  );
}

export function TypingDots() {
  return (
    <span className="typing-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

/** Mensagens rotativas: sinalizam progresso mesmo quando nao ha percentual. */
export function GeneratingState({
  messages,
  title = "Preparando seu conteudo",
}: {
  messages: string[];
  title?: string;
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (messages.length <= 1) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % messages.length), 2600);
    return () => clearInterval(timer);
  }, [messages.length]);

  return (
    <div className="generating-state" role="status" aria-live="polite">
      <div className="generating-icon">
        <SparkleIcon size={22} />
      </div>
      <div>
        <p className="generating-title">
          {title}
          <TypingDots />
        </p>
        <p className="generating-message">{messages[index]}</p>
      </div>
    </div>
  );
}

export function LoadingCard({ title, messages }: { title?: string; messages: string[] }) {
  return (
    <div className="card">
      <GeneratingState title={title} messages={messages} />
      <Skeleton lines={4} />
    </div>
  );
}
