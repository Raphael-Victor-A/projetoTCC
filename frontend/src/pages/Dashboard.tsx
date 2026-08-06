import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import type { ProgressOut, QuestionOut } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ArrowRightIcon, BookIcon, ClockIcon, TrophyIcon } from "../components/Icons";

const LEVELS: { key: string; label: string }[] = [
  { key: "basico", label: "Basico" },
  { key: "intermediario", label: "Intermediario" },
  { key: "avancado", label: "Avancado" },
];

function studyTimeKey() {
  return `tempo-estudo-${new Date().toISOString().slice(0, 10)}`;
}

function useStudyMinutesToday(): number {
  const [minutes, setMinutes] = useState(() => Math.round(Number(localStorage.getItem(studyTimeKey()) ?? 0) / 60));
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

export default function Dashboard() {
  const [progress, setProgress] = useState<ProgressOut | null>(null);
  const [nextQuestion, setNextQuestion] = useState<QuestionOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();
  const studyMinutes = useStudyMinutesToday();

  useEffect(() => {
    Promise.all([api.getProgress(), api.getNextExercise()])
      .then(([p, q]) => {
        setProgress(p);
        setNextQuestion(q);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"));
  }, []);

  if (error) return <div className="card error">{error}</div>;
  if (!progress) return <div className="card">Carregando seu painel...</div>;

  const name = user?.email.split("@")[0] ?? "por ai";
  const accuracy = progress.total_attempts > 0 ? Math.round((progress.total_correct / progress.total_attempts) * 100) : 0;
  const levelIndex = LEVELS.findIndex((l) => l.key === progress.level);

  const achievements = [
    { label: "Primeiros passos", unlocked: progress.total_attempts >= 1 },
    { label: "Nivel intermediario", unlocked: levelIndex >= 1 },
    { label: "Nivel avancado", unlocked: levelIndex >= 2 },
    { label: "10 acertos", unlocked: progress.total_correct >= 10 },
  ];

  return (
    <div className="card">
      <p className="greeting">Ola, {name}!</p>
      <p className="greeting-sub">Vamos continuar de onde voce parou?</p>

      <p className="section-label">Seu nivel atual</p>
      <div className="level-track">
        {LEVELS.map((l, i) => (
          <div key={l.key} className={`level-step ${i < levelIndex ? "done" : i === levelIndex ? "current" : ""}`}>
            <div className="level-step-dot">{i + 1}</div>
            <div className="level-step-label">{l.label}</div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <div className="summary-card">
          <div className="summary-icon">
            <BookIcon />
          </div>
          <div>
            <div className="summary-value">{accuracy}%</div>
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

      {nextQuestion && (
        <>
          <p className="section-label">Sua proxima atividade</p>
          <div className="summary-card">
            <div className="summary-icon">
              <ArrowRightIcon />
            </div>
            <div>
              <div className="summary-value" style={{ fontSize: "1.05rem" }}>
                {nextQuestion.topic}
              </div>
              <div className="summary-label">Nivel {nextQuestion.level}</div>
            </div>
          </div>
        </>
      )}

      <p className="section-label">Suas conquistas</p>
      <div className="badges-row">
        {achievements.map((a) => (
          <span key={a.label} className={`achievement-badge ${a.unlocked ? "" : "locked"}`}>
            <TrophyIcon size={16} /> {a.label}
          </span>
        ))}
      </div>

      <div style={{ marginTop: "2rem" }}>
        <button onClick={() => navigate("/exercise")} style={{ width: "100%" }}>
          Continuar estudando <ArrowRightIcon size={18} />
        </button>
      </div>
    </div>
  );
}
