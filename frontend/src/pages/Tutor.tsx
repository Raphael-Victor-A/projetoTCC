import { useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import type { TutorSource } from "../api/client";
import Markdown from "../components/Markdown";
import { TypingDots } from "../components/Loading";
import { ChatIcon, SearchIcon, SparkleIcon } from "../components/Icons";

interface Message {
  role: "user" | "assistant";
  content: string;
  searching?: boolean;
  sources?: TutorSource[];
  streaming?: boolean;
}

/**
 * Tutor de duvidas.
 *
 * A resposta e escrita na tela conforme chega (SSE). Quando o backend liga a
 * busca ao vivo, a interface avisa e lista as fontes ao final — o aluno
 * sempre sabe se a resposta veio so do modelo ou tambem da web.
 */
export default function Tutor() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [searchMode, setSearchMode] = useState<"auto" | "on" | "off">("auto");
  const controllerRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", streaming: true },
    ]);

    const controller = new AbortController();
    controllerRef.current = controller;

    const updateLast = (patch: Partial<Message>) =>
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        next[next.length - 1] = { ...last, ...patch, content: patch.content ?? last.content };
        return next;
      });

    const appendChunk = (piece: string) =>
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        next[next.length - 1] = { ...last, content: last.content + piece };
        return next;
      });

    try {
      await api.askTutor(
        {
          question,
          use_search: searchMode === "auto" ? null : searchMode === "on",
        },
        {
          onMeta: (meta) => updateLast({ searching: !!meta.search }),
          onChunk: appendChunk,
          onSources: (sources) => updateLast({ sources }),
          onError: (message) => appendChunk(`\n\n_${message}_`),
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        appendChunk(`\n\n_${err instanceof Error ? err.message : "Falha na conexao."}_`);
      }
    } finally {
      updateLast({ streaming: false });
      setBusy(false);
    }
  }

  return (
    <div className="card tutor">
      <p className="lesson-eyebrow">
        <ChatIcon size={16} /> Tutor
      </p>
      <h1>Tire suas duvidas</h1>
      <p className="subtitle">
        Pergunte sobre qualquer conteudo da sua trilha. Quando a resposta depender de informacao
        atual, eu consulto a web e mostro as fontes.
      </p>

      <div className="search-toggle" role="radiogroup" aria-label="Modo de busca">
        {(
          [
            ["auto", "Automatico"],
            ["on", "Sempre buscar"],
            ["off", "Sem busca"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`chip ${searchMode === value ? "active" : ""}`}
            onClick={() => setSearchMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="chat-log">
        {messages.length === 0 && (
          <p className="chat-empty">
            Exemplo: "Nao entendi por que delta negativo significa que nao ha raiz real."
          </p>
        )}
        {messages.map((message, i) => (
          <div className={`chat-message ${message.role}`} key={i}>
            {message.role === "assistant" && (
              <div className="chat-avatar">
                <SparkleIcon size={16} />
              </div>
            )}
            <div className="chat-bubble">
              {message.searching && (
                <p className="search-badge">
                  <SearchIcon size={14} /> Consultando fontes atualizadas
                </p>
              )}
              {message.content ? (
                <Markdown text={message.content} />
              ) : (
                message.streaming && (
                  <p className="feedback-placeholder">
                    Pensando
                    <TypingDots />
                  </p>
                )
              )}
              {message.streaming && message.content && (
                <span className="stream-cursor" aria-hidden="true" />
              )}
              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <p className="sources-label">Fontes</p>
                  <ul>
                    {message.sources.map((source) => (
                      <li key={source.uri}>
                        <a href={source.uri} target="_blank" rel="noreferrer noopener">
                          {source.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={send}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Digite sua duvida..."
          aria-label="Sua duvida"
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "..." : "Enviar"}
        </button>
      </form>
    </div>
  );
}
