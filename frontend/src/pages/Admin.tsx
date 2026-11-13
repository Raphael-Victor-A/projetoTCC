import { useEffect, useState } from "react";
import * as api from "../api/client";
import type { AdminStats, FeedbackGroup, StudentOut } from "../api/client";
import { UserIcon } from "../components/Icons";
import EvaluationPanel from "../components/admin/EvaluationPanel";
import ReviewPanel from "../components/admin/ReviewPanel";

type AdminTab = "alunos" | "avaliacao" | "revisao";

const TABS: { id: AdminTab; label: string }[] = [
  { id: "alunos", label: "Alunos" },
  { id: "avaliacao", label: "Avaliacao da IA" },
  { id: "revisao", label: "Revisao manual" },
];

function readTab(): AdminTab {
  const h = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === h) ? (h as AdminTab) : "alunos";
}

const GROUP_LABEL: Record<FeedbackGroup, string> = {
  diretivo: "Explicacao direta",
  socratico: "Perguntas guiadas",
};

export default function Admin() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [students, setStudents] = useState<StudentOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [tab, setTab] = useState<AdminTab>(readTab);

  function changeTab(t: AdminTab) {
    setTab(t);
    if (window.location.hash !== `#${t}`) window.location.hash = t;
  }

  function reload() {
    Promise.all([api.getAdminStats(), api.getStudents()])
      .then(([s, st]) => {
        setStats(s);
        setStudents(st);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro inesperado"));
  }

  useEffect(() => {
    reload();
    const onHash = () => setTab(readTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  async function handleGroupChange(id: number, group: FeedbackGroup) {
    setSavingId(id);
    setError(null);
    try {
      const updated = await api.setStudentGroup(id, group);
      setStudents((prev) => prev && prev.map((s) => (s.id === id ? updated : s)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setSavingId(null);
    }
  }

  if (error) return <div className="card error">{error}</div>;
  if (!stats || !students) return <div className="card">Carregando painel...</div>;

  return (
    <div className="card admin-card">
      <h2>Painel do professor</h2>
      <p className="subtitle">Acompanhe como seus {stats.total_students} alunos estao indo.</p>

      <div className="tabs admin-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? " active" : ""}`}
            onClick={() => changeTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "avaliacao" && <EvaluationPanel />}
      {tab === "revisao" && <ReviewPanel />}

      {tab === "alunos" && (
      <>
      <div className="groups-grid">
        {stats.groups.map((g) => (
          <div key={g.group} className="group-panel">
            <h3>{GROUP_LABEL[g.group]}</h3>

            <div className="stat-grid">
              <div className="stat-tile">
                <span className="stat-value">{g.total_users}</span>
                <span className="stat-label">Alunos</span>
              </div>
              <div className="stat-tile">
                <span className="stat-value">{g.total_attempts}</span>
                <span className="stat-label">Atividades feitas</span>
              </div>
              <div className="stat-tile">
                <span className="stat-value">{(g.accuracy * 100).toFixed(0)}%</span>
                <span className="stat-label">Acertam</span>
              </div>
              <div className="stat-tile">
                <span className="stat-value">{(g.avg_gemini_latency_ms / 1000).toFixed(1)}s</span>
                <span className="stat-label">Tempo de resposta da IA</span>
              </div>
              <div className="stat-tile">
                <span className="stat-value">{g.leak_detected_count}</span>
                <span className="stat-label">Vezes que a IA se autocorrigiu</span>
              </div>
              <div className="stat-tile">
                <span className="stat-value">{g.fallback_used_count}</span>
                <span className="stat-label">Vezes que a IA ficou indisponivel</span>
              </div>
            </div>

            <p className="section-label">Como estao distribuidos</p>
            <div className="level-bars">
              {Object.entries(g.level_distribution).map(([level, count]) => (
                <div key={level} className="level-bar-row">
                  <span className="level-bar-label">{level}</span>
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill"
                      style={{ width: g.total_users ? `${(count / g.total_users) * 100}%` : "0%" }}
                    />
                  </div>
                  <span className="level-bar-count">{count}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="section-label">Seus alunos</p>
      <p className="hint" style={{ marginBottom: "1rem" }}>
        O modo de ensino e sorteado automaticamente. Voce pode trocar manualmente se quiser.
      </p>

      {students.length === 0 && (
        <div className="empty-state">
          <UserIcon size={32} />
          <p>Nenhum aluno cadastrado ainda.</p>
        </div>
      )}

      <div className="student-cards">
        {students.map((s) => (
          <div key={s.id} className="student-card">
            <div className="student-card-header">
              <div className="student-avatar">{s.email[0]?.toUpperCase()}</div>
              <div>
                <div className="student-email">{s.email}</div>
                <div className="badge-row" style={{ marginTop: "0.35rem" }}>
                  <span className="badge capitalize">{s.level}</span>
                  <span className={s.diagnostic_completed ? "badge" : "badge badge-warning"}>
                    {s.diagnostic_completed ? "Diagnostico feito" : "Diagnostico pendente"}
                  </span>
                </div>
              </div>
            </div>
            <label htmlFor={`group-${s.id}`} style={{ fontSize: "0.85rem" }}>
              Modo de ensino
              <select
                id={`group-${s.id}`}
                value={s.group}
                disabled={savingId === s.id}
                onChange={(e) => handleGroupChange(s.id, e.target.value as FeedbackGroup)}
              >
                <option value="diretivo">Explicacao direta</option>
                <option value="socratico">Perguntas guiadas</option>
              </select>
            </label>
          </div>
        ))}
      </div>
      </>
      )}
    </div>
  );
}
