import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ModuleOut, NextStep, QuizSummary } from "../api/client";
import { AlertIcon, BookIcon, CheckIcon, ClipboardCheckIcon, TrophyIcon } from "./Icons";
import Mascot, { MascotSays, useMascotLine } from "./Mascot";

/**
 * Trilha de estudos em caminho: cada modulo e uma faixa colorida seguida das
 * suas etapas (questionario / mini aula) em zigue-zague.
 *
 * Estados de cada etapa:
 * - feita: cor do modulo + selo (verde >= 70% de acerto, laranja abaixo);
 * - atual: maior, pulsando, com o balao "Comecar";
 * - futura: cinza. Em outro modulo pode ser iniciada (o aluno escolhe a
 *   ordem); dentro do modulo atual, so depois das anteriores.
 */

export interface TrailModule extends ModuleOut {
  /** Motivo da recomendacao (vem de /study-plan), quando houver. */
  reason?: string;
}

const ZIG = [0, 46, 70, 46, 0, -46, -70, -46];
const UNIT_COLORS = 5;
const GOOD_SCORE = 0.7;
// Quantos modulos ainda nao iniciados aparecem antes do botao "ver os outros".
const UPCOMING_VISIBLE = 3;

type StepState = "done" | "current" | "idle";

function stepLabel(steps: string[], s: number): string {
  const kind = steps[s];
  const sameBefore = steps.slice(0, s + 1).filter((k) => k === kind).length;
  const isLastQuiz = kind === "quiz" && steps.slice(s + 1).every((k) => k !== "quiz");
  if (kind === "quiz") return isLastQuiz && sameBefore > 1 ? "Questionario final" : `Questionario ${sameBefore}`;
  return `Mini aula ${sameBefore}`;
}

function quizFor(module: TrailModule, s: number): QuizSummary | undefined {
  const quizIndex = module.steps.slice(0, s).filter((k) => k === "quiz").length;
  return module.quiz_results[quizIndex];
}

/** Ordem da trilha: concluidos, atual, em andamento, depois nao iniciados por prioridade. */
export function trailOrder(modules: TrailModule[], currentId: number | null): TrailModule[] {
  const rank = (m: TrailModule) =>
    m.status === "concluido" ? 0 : m.id === currentId ? 1 : m.status === "em_andamento" ? 2 : 3;
  return [...modules].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      (rank(a) === 0 ? a.order_index - b.order_index : a.priority - b.priority) ||
      a.order_index - b.order_index,
  );
}

export default function Trail({
  modules,
  currentModuleId,
  nextStep,
  busy,
  onContinue,
  onStudyModule,
  currentRef,
}: {
  modules: TrailModule[];
  currentModuleId: number | null;
  nextStep: NextStep | null;
  busy: boolean;
  onContinue: () => void;
  onStudyModule: (moduleId: number) => void;
  currentRef: React.RefObject<HTMLDivElement>;
}) {
  const [showAll, setShowAll] = useState(false);
  const startLine = useMascotLine("start");
  const lessonLine = useMascotLine("lesson");
  const [open, setOpen] = useState<string | null>(null);
  const trailRef = useRef<HTMLDivElement>(null);
  const [pathD, setPathD] = useState("");
  const [box, setBox] = useState({ w: 0, h: 0 });

  const firstIdle = modules.findIndex((m) => m.status === "nao_iniciado" && m.id !== currentModuleId);
  const cut = firstIdle === -1 ? modules.length : firstIdle + UPCOMING_VISIBLE;
  const visible = showAll ? modules : modules.slice(0, cut);
  const hiddenCount = modules.length - cut;

  const drawPath = useCallback(() => {
    const trail = trailRef.current;
    if (!trail) return;
    const base = trail.getBoundingClientRect();
    const pts = Array.from(trail.querySelectorAll<HTMLElement>(".trail-node")).map((n) => {
      const r = n.getBoundingClientRect();
      return [r.left - base.left + r.width / 2, r.top - base.top + r.height / 2];
    });
    setBox({ w: base.width, h: base.height });
    if (pts.length < 2) return setPathD("");
    let d = `M${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [px, py] = pts[i - 1];
      const [qx, qy] = pts[i];
      const my = (py + qy) / 2;
      d += ` C${px} ${my} ${qx} ${my} ${qx} ${qy}`;
    }
    setPathD(d);
  }, []);

  useLayoutEffect(() => {
    drawPath();
  }, [drawPath, visible.length, modules]);

  useEffect(() => {
    const trail = trailRef.current;
    if (!trail || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => drawPath());
    ro.observe(trail);
    return () => ro.disconnect();
  }, [drawPath]);

  useEffect(() => {
    const close = () => setOpen(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  let zig = 0;

  return (
    <section className="trail" ref={trailRef} aria-label="Sua trilha de estudos">
      <svg className="trail-svg" viewBox={`0 0 ${box.w} ${box.h}`} aria-hidden="true">
        <path d={pathD} />
      </svg>

      {visible.map((module, position) => {
        const isCurrent = module.id === currentModuleId;
        const total = module.steps.length;
        const done = Math.min(module.step_index, total);
        const idleUnit = done === 0 && !isCurrent;
        const color = `var(--unit-${(position % UNIT_COLORS) + 1})`;
        const status =
          module.status === "concluido" ? "Concluido" : done > 0 || isCurrent ? "Em andamento" : "Nao iniciado";

        return (
          <div
            key={module.id}
            className={`trail-unit${idleUnit ? " idle" : ""}`}
            style={{ "--u": color } as React.CSSProperties}
          >
            <div className="trail-banner">
              <div>
                <div className="trail-eyebrow">
                  Modulo {position + 1} de {modules.length}
                </div>
                <h3 className="trail-title">{module.title}</h3>
              </div>
              <div className="trail-progress">
                {done}/{total}
                <small>{status}</small>
              </div>
              {((module.reason && module.status !== "concluido") || module.status === "concluido") && (
                <div className="trail-meta">
                  {module.reason && module.status !== "concluido" && (
                    <span className="trail-reason">{module.reason}</span>
                  )}
                  {module.status === "concluido" && (
                    <button
                      type="button"
                      className="trail-review"
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation();
                        onStudyModule(module.id);
                      }}
                    >
                      Revisar do inicio
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="trail-nodes">
              {module.steps.map((kind, s) => {
                const state: StepState =
                  s < done ? "done" : isCurrent && s === done ? "current" : "idle";
                const isFinal = kind === "quiz" && s === total - 1;
                const label = stepLabel(module.steps, s);
                const key = `${module.id}-${s}`;
                const quiz = kind === "quiz" && state === "done" ? quizFor(module, s) : undefined;
                const good = quiz ? quiz.total > 0 && quiz.correct_count / quiz.total >= GOOD_SCORE : true;
                const x = ZIG[zig++ % ZIG.length];

                return (
                  <div
                    key={key}
                    className={`trail-node-wrap${state === "current" ? " is-current" : ""}`}
                    style={{ "--x": `${x}px`, zIndex: open === key ? 12 : undefined } as React.CSSProperties}
                    ref={state === "current" ? currentRef : undefined}
                  >
                    {state === "current" && (
                      <div className="trail-perch" aria-hidden="true">
                        <MascotSays>{kind === "lesson" ? lessonLine : startLine}</MascotSays>
                        <Mascot mood="zen" size={88} />
                      </div>
                    )}
                    <button
                      type="button"
                      className={`trail-node ${state}${isFinal ? " final" : ""}`}
                      aria-label={`${label}: ${module.title}`}
                      aria-expanded={open === key}
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpen(open === key ? null : key);
                      }}
                    >
                      {kind === "lesson" ? (
                        <BookIcon size={30} />
                      ) : isFinal ? (
                        <TrophyIcon size={34} />
                      ) : (
                        <ClipboardCheckIcon size={30} />
                      )}
                      {state === "done" && (
                        <span className={`trail-badge ${good ? "ok" : "low"}`}>
                          {good ? <CheckIcon size={13} /> : <AlertIcon size={13} />}
                        </span>
                      )}
                    </button>

                    {open === key && (
                      <div className="trail-pop" role="dialog" onClick={(e) => e.stopPropagation()}>
                        <div className="trail-pop-kind">
                          {kind === "lesson" ? "Mini aula" : "Questionario"} · {module.title}
                        </div>
                        <p className="trail-pop-title">{label}</p>
                        <StepPopBody
                          state={state}
                          kind={kind}
                          quiz={quiz}
                          inCurrentModule={isCurrent}
                          moduleStarted={done > 0}
                          busy={busy}
                          onStart={() => {
                            setOpen(null);
                            if (isCurrent && nextStep?.module_id === module.id) onContinue();
                            else onStudyModule(module.id);
                          }}
                          onGoCurrent={() => {
                            setOpen(null);
                            onContinue();
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {hiddenCount > 0 && (
        <button type="button" className="trail-more" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Mostrar so os proximos modulos" : `Ver os outros ${hiddenCount} modulos da grade`}
        </button>
      )}
    </section>
  );
}

function StepPopBody({
  state,
  kind,
  quiz,
  inCurrentModule,
  moduleStarted,
  busy,
  onStart,
  onGoCurrent,
}: {
  state: StepState;
  kind: string;
  quiz?: QuizSummary;
  inCurrentModule: boolean;
  moduleStarted: boolean;
  busy: boolean;
  onStart: () => void;
  onGoCurrent: () => void;
}) {
  if (state === "done") {
    if (kind === "lesson") return <p className="trail-pop-text">Voce ja leu esta mini aula.</p>;
    if (!quiz) return <p className="trail-pop-text">Questionario concluido.</p>;
    return (
      <>
        <p className="trail-pop-text">
          Voce acertou {quiz.correct_count} de {quiz.total}.
        </p>
        <div className="trail-score">
          {quiz.results.map((r, i) => (
            <span key={i} className={r === true ? "ok" : r === false ? "bad" : ""} />
          ))}
        </div>
      </>
    );
  }

  if (state === "current") {
    return (
      <>
        <p className="trail-pop-text">
          {kind === "lesson"
            ? "Uma explicacao curta, focada no que voce errou."
            : "Responda no seu ritmo. Se travar, peca uma dica ao tutor."}
        </p>
        <button type="button" className="trail-pop-btn" disabled={busy} onClick={onStart}>
          {kind === "lesson" ? "Ler mini aula" : "Comecar questionario"}
        </button>
      </>
    );
  }

  if (inCurrentModule) {
    return (
      <>
        <p className="trail-pop-text">Termine as etapas anteriores deste modulo primeiro.</p>
        <button type="button" className="trail-pop-btn ghost" onClick={onGoCurrent}>
          Ir para a etapa atual
        </button>
      </>
    );
  }

  return (
    <>
      <p className="trail-pop-text">
        Sua trilha ainda nao chegou aqui, mas voce pode estudar este conteudo agora se quiser.
      </p>
      <button type="button" className="trail-pop-btn ghost" disabled={busy} onClick={onStart}>
        {moduleStarted ? "Continuar este modulo" : "Comecar este modulo"}
      </button>
    </>
  );
}
