import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import type { NextStep, StudyPlan, SubjectOut } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ProgressBar, ProgressRing } from "../components/Progress";
import { Skeleton } from "../components/Loading";
import {
  ArrowRightIcon,
  BookIcon,
  ChatIcon,
  CheckIcon,
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

const STATUS_LABEL: Record<string, string> = {
  nao_iniciado: "Nao iniciado",
  em_andamento: "Em andamento",
  concluido: "Concluido",
};

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
 * Painel do aluno.
 *
 * Responde a quatro perguntas, nesta ordem: o que eu faco agora, como estou
 * indo, o que devo estudar em seguida e como esta cada disciplina da grade.
 */
export default function Dashboard() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [nextStep, setNextStep] = useState<NextStep | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();
  const studyMinutes = useStudyMinutesToday();

  const load = useCallback(async () => {
    setError(null);
    try {
      // Duas consultas independentes: pedidas em paralelo.
      const [planData, stepData] = await Promise.all([api.getStudyPlan(), api.getNextStep()]);
      setPlan(planData);
      setNextStep(stepData);
      // Com uma unica disciplina, esconder os modulos atras de um clique so
      // adiciona atrito: a grade ja abre aberta.
      if (planData.subjects.length === 1) setExpanded(planData.subjects[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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

  return (
    <div className="dashboard">
      <div className="card">
        <p className="greeting">Ola, {name}!</p>
        <p className="greeting-sub">Sua trilha esta montada a partir do seu diagnostico.</p>

        {nextStep && (
          <div className="next-step-card">
            <div className="next-step-icon">
              {nextStep.kind === "lesson" ? <BookIcon size={22} /> : <PlayIcon size={22} />}
            </div>
            <div className="next-step-body">
              <p className="next-step-label">Proximo passo</p>
              <p className="next-step-title">
                {nextStep.module_title ?? "Continue estudando"}
                {nextStep.subject_name ? ` — ${nextStep.subject_name}` : ""}
              </p>
              <p className="next-step-message">{nextStep.message}</p>
            </div>
            <button onClick={() => navigateToStep(nextStep)} disabled={busy}>
              {nextStep.kind === "lesson" ? "Ver mini aula" : "Comecar"} <ArrowRightIcon size={18} />
            </button>
          </div>
        )}

        <p className="section-label">Seu nivel atual</p>
        <div className="level-track">
          {LEVELS.map((l, i) => (
            <div
              key={l.key}
              className={`level-step ${i < levelIndex ? "done" : i === levelIndex ? "current" : ""}`}
            >
              <div className="level-step-dot">{i + 1}</div>
              <div className="level-step-label">{l.label}</div>
            </div>
          ))}
        </div>

        <div className="dashboard-grid">
          <div className="summary-card">
            <ProgressRing value={plan.overall_completion} />
            <div>
              <div className="summary-value">
                {plan.modules_completed}/{plan.modules_total}
              </div>
              <div className="summary-label">Modulos concluidos</div>
            </div>
          </div>
          <div className="summary-card">
            <div className="summary-icon">
              <TargetIcon />
            </div>
            <div>
              <div className="summary-value">{plan.accuracy}%</div>
              <div className="summary-label">Voce acerta</div>
            </div>
          </div>
          <div className="summary-card">
            <div className="summary-icon">
              <ClockIcon />
            </div>
            <div>
              <div className="summary-value">{studyMinutes} min</div>
              <div className="summary-label">Estudados hoje</div>
            </div>
          </div>
        </div>
      </div>

      {plan.recommendations.length > 0 && (
        <div className="card">
          <p className="section-label">
            <TargetIcon size={16} /> Recomendado para voce
          </p>
          <div className="recommendation-list">
            {plan.recommendations.map((rec) => (
              <div className="recommendation" key={rec.module_id}>
                <span className="subject-dot" style={{ background: rec.subject_color }} />
                <div className="recommendation-body">
                  <div className="recommendation-title">{rec.module_title}</div>
                  <div className="recommendation-subject">{rec.subject_name}</div>
                  <div className="recommendation-reason">{rec.reason}</div>
                  <ProgressBar value={rec.completion} color={rec.subject_color} />
                </div>
                <button
                  className="secondary"
                  onClick={() => studyModule(rec.module_id)}
                  disabled={busy}
                >
                  Estudar
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.weak_topics.length > 0 && (
        <div className="card">
          <p className="section-label">Conteudos para reforcar</p>
          <div className="badges-row">
            {plan.weak_topics.map((topic) => (
              <span className="topic-chip" key={topic}>
                {topic}
              </span>
            ))}
          </div>
          <button className="secondary" onClick={() => navigate("/tutor")} style={{ marginTop: "1rem" }}>
            <ChatIcon size={16} /> Tirar duvida com o tutor
          </button>
        </div>
      )}

      <div className="card">
        <p className="section-label">
          <LayersIcon size={16} /> Sua grade de estudos
        </p>
        <div className="subject-list">
          {plan.subjects.map((subject) => (
            <SubjectRow
              key={subject.id}
              subject={subject}
              expanded={expanded === subject.id}
              onToggle={() => setExpanded(expanded === subject.id ? null : subject.id)}
              onStudy={studyModule}
              busy={busy}
            />
          ))}
        </div>
      </div>

      <div className="card">
        <p className="section-label">Suas conquistas</p>
        <div className="badges-row">
          {achievements.map((a) => (
            <span key={a.label} className={`achievement-badge ${a.unlocked ? "" : "locked"}`}>
              <TrophyIcon size={16} /> {a.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function SubjectRow({
  subject,
  expanded,
  onToggle,
  onStudy,
  busy,
}: {
  subject: SubjectOut;
  expanded: boolean;
  onToggle: () => void;
  onStudy: (moduleId: number) => void;
  busy: boolean;
}) {
  return (
    <div className="subject-row">
      <button className="subject-header" onClick={onToggle} aria-expanded={expanded}>
        <span className="subject-dot" style={{ background: subject.color }} />
        <span className="subject-name">{subject.name}</span>
        <span className="subject-meta">
          {subject.modules.filter((m) => m.status === "concluido").length}/{subject.modules.length}{" "}
          modulos
        </span>
        <span className={`chevron ${expanded ? "open" : ""}`} aria-hidden="true" />
      </button>
      <ProgressBar value={subject.completion} color={subject.color} />

      {expanded && (
        <div className="module-list">
          {subject.modules.map((module) => (
            <div className="module-row" key={module.id}>
              <div className="module-info">
                <div className="module-title">
                  {module.status === "concluido" && <CheckIcon size={15} />} {module.title}
                </div>
                <div className="module-meta">
                  {STATUS_LABEL[module.status]} · {module.completion}% concluido
                  {module.performance !== null ? ` · ${module.performance}% de acerto` : ""}
                </div>
                <details className="module-details">
                  <summary>Objetivos e conteudos</summary>
                  <p className="module-summary">{module.summary}</p>
                  <ul>
                    {module.objectives.map((objective, i) => (
                      <li key={`o-${i}`}>{objective}</li>
                    ))}
                  </ul>
                  <p className="module-contents">{module.contents.join(" · ")}</p>
                  {module.bncc_codes.length > 0 && (
                    <p className="module-bncc">BNCC: {module.bncc_codes.join(", ")}</p>
                  )}
                </details>
              </div>
              <button className="secondary" onClick={() => onStudy(module.id)} disabled={busy}>
                {module.status === "nao_iniciado" ? "Comecar" : "Continuar"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
