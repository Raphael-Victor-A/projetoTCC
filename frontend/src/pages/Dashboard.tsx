import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import type { NextStep, StudyPlan } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Skeleton } from "../components/Loading";
import Trail, { trailOrder } from "../components/Trail";
import type { TrailModule } from "../components/Trail";
import Mascot from "../components/Mascot";
import {
  ArrowRightIcon,
  BarsIcon,
  BookIcon,
  ChatIcon,
  ClockIcon,
  LayersIcon,
  PlayIcon,
  TargetIcon,
  TrophyIcon,
} from "../components/Icons";

const LEVELS = [
  { key: "basico", label: "Basico" },
  { key: "intermediario", label: "Intermediario" },
  { key: "avancado", label: "Avancado" },
];

function studyTimeKey() {
  return `tempo-estudo-${new Date().toISOString().slice(0, 10)}`;
}

function useStudyMinutesToday(): number {
  const [minutes, setMinutes] = useState(() =>
    Math.round(Number(localStorage.getItem(studyTimeKey()) ?? 0) / 60),
  );
  const secondsRef = useRef(Number(localStorage.getItem(studyTimeKey()) ?? 0));

  useEffect(() => {
    const interval = setInterval(() => {
      secondsRef.current += 15;
      localStorage.setItem(studyTimeKey(), String(secondsRef.current));
      setMinutes(Math.round(secondsRef.current / 60));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  return minutes;
}

/**
 * Painel do aluno, organizado como trilha.
 *
 * No centro, o caminho de modulos e etapas (o que fazer e o que ja foi
 * feito). Ao lado, o resumo: proximo passo, nivel, o que reforcar e
 * conquistas. No celular o painel desce para baixo da trilha.
 */
export default function Dashboard() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [nextStep, setNextStep] = useState<NextStep | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();
  const studyMinutes = useStudyMinutesToday();
  const currentRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // Duas consultas independentes: pedidas em paralelo.
      const [planData, stepData] = await Promise.all([api.getStudyPlan(), api.getNextStep()]);
      setPlan(planData);
      setNextStep(stepData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const currentModuleId = nextStep?.module_id ?? plan?.current_module_id ?? null;

  const modules: TrailModule[] = useMemo(() => {
    if (!plan) return [];
    const reasons = new Map(plan.recommendations.map((r) => [r.module_id, r.reason]));
    const all = plan.subjects.flatMap((s) =>
      s.modules.map((m) => ({ ...m, reason: reasons.get(m.id) })),
    );
    return trailOrder(all, currentModuleId);
  }, [plan, currentModuleId]);

  function navigateToStep(step: NextStep) {
    if (step.kind === "quiz" && step.module_id) navigate(`/quiz?module=${step.module_id}`);
    else if (step.kind === "lesson" && step.module_id) navigate(`/lesson?module=${step.module_id}`);
    else if (step.kind === "diagnostic") navigate("/diagnostic");
    else navigate("/exercise");
  }

  async function studyModule(moduleId: number) {
    setBusy(true);
    try {
      const step = await api.selectModule(moduleId);
      navigateToStep(step);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel abrir o modulo.");
    } finally {
      setBusy(false);
    }
  }

  function scrollToCurrent() {
    const node = currentRef.current;
    if (!node) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    node.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    node.querySelector<HTMLButtonElement>(".trail-node")?.focus({ preventScroll: true });
  }

  if (error && !plan) return <div className="card error">{error}</div>;
  if (!plan) {
    return (
      <div className="card">
        <Skeleton lines={6} />
      </div>
    );
  }

  const name = user?.email.split("@")[0] ?? "por ai";
  const levelIndex = LEVELS.findIndex((l) => l.key === plan.level);

  const achievements = [
    { label: "Primeiros passos", unlocked: plan.total_attempts >= 1 },
    { label: "Primeiro modulo", unlocked: plan.modules_completed >= 1 },
    { label: "Nivel intermediario", unlocked: levelIndex >= 1 },
    { label: "10 acertos", unlocked: plan.total_correct >= 10 },
  ];

  const continueLabel =
    nextStep?.kind === "lesson" ? "Ver mini aula" : nextStep?.kind === "quiz" ? "Comecar" : "Continuar";

  return (
    <div className="trail-page">
      <div className="trail-hello">
        <div>
          <p className="greeting">Ola, {name}!</p>
          <p className="greeting-sub">Sua trilha foi montada a partir do seu diagnostico.</p>
        </div>
        <div className="trail-stats" aria-label="Seu resumo">
          <span className="trail-stat level" title="Seu nivel">
            <BarsIcon size={18} /> {LEVELS[levelIndex]?.label ?? plan.level}
          </span>
          <span className="trail-stat acc" title="Voce acerta">
            <TargetIcon size={18} /> {plan.accuracy}%
          </span>
          <span className="trail-stat time" title="Estudado hoje">
            <ClockIcon size={18} /> {studyMinutes} <small>min</small>
          </span>
          <span className="trail-stat mods" title="Modulos concluidos">
            <LayersIcon size={18} /> {plan.modules_completed}
            <small>/{plan.modules_total}</small>
          </span>
        </div>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="trail-layout">
        <Trail
          modules={modules}
          currentModuleId={currentModuleId}
          nextStep={nextStep}
          busy={busy}
          onContinue={() => (nextStep ? navigateToStep(nextStep) : undefined)}
          onStudyModule={studyModule}
          currentRef={currentRef}
        />

        <aside className="trail-side">
          {nextStep && (
            <div className="trail-panel trail-next">
              <h2>Proximo passo</h2>
              <div className="trail-next-head">
                <span className="trail-next-icon">
                  {nextStep.kind === "lesson" ? <BookIcon size={20} /> : <PlayIcon size={20} />}
                </span>
                <p className="trail-next-title">{nextStep.module_title ?? "Continue estudando"}</p>
              </div>
              <p className="trail-next-sub">{nextStep.message}</p>
              <button onClick={() => navigateToStep(nextStep)} disabled={busy} style={{ width: "100%" }}>
                {continueLabel} <ArrowRightIcon size={18} />
              </button>
            </div>
          )}

          <div className="trail-panel">
            <h2>Seu nivel</h2>
            <div className="trail-levels">
              {LEVELS.map((l, i) => (
                <div
                  key={l.key}
                  className={`trail-level ${i < levelIndex ? "done" : i === levelIndex ? "now" : ""}`}
                >
                  <i />
                  {l.label}
                </div>
              ))}
            </div>
          </div>

          <div className="trail-panel">
            {plan.weak_topics.length > 0 ? (
              <>
                <h2>Para reforcar</h2>
                <div className="badges-row">
                  {plan.weak_topics.map((topic) => (
                    <span className="topic-chip" key={topic}>
                      {topic}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <h2>Duvidas?</h2>
            )}
            <div className="trail-tutor-cta">
              <button className="secondary" onClick={() => navigate("/tutor")}>
                <ChatIcon size={16} /> Tirar duvida com o tutor
              </button>
              <div className="trail-tutor-mascot" aria-hidden="true">
                <span className="mascot-sign">Manda a braba!</span>
                <Mascot mood="hint" size={96} />
              </div>
            </div>
          </div>

          <div className="trail-panel">
            <h2>Conquistas</h2>
            <div className="trail-achs">
              {achievements.map((a) => (
                <div key={a.label} className={`trail-ach ${a.unlocked ? "on" : ""}`}>
                  <b>
                    <TrophyIcon size={22} />
                  </b>
                  {a.label}
                </div>
              ))}
            </div>
          </div>

          <div className="trail-panel">
            <h2>Como ler a trilha</h2>
            <div className="trail-legend">
              <div>
                <i style={{ background: "var(--unit-1)" }} /> Etapa feita (cor do modulo)
              </div>
              <div>
                <i style={{ background: "var(--color-success)" }} /> Selo verde: 70% ou mais de acerto
              </div>
              <div>
                <i style={{ background: "var(--color-hint)" }} /> Selo laranja: vale revisar
              </div>
              <div>
                <i style={{ background: "var(--trail-idle)" }} /> Ainda nao chegou la
              </div>
            </div>
          </div>
        </aside>
      </div>

      {currentModuleId !== null && (
        <button
          type="button"
          className="trail-fab"
          onClick={scrollToCurrent}
          aria-label="Ir para a etapa atual"
          title="Ir para a etapa atual"
        >
          <TargetIcon size={24} />
        </button>
      )}
    </div>
  );
}
