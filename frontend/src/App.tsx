import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Diagnostic from "./pages/Diagnostic";
import Exercise from "./pages/Exercise";
import Dashboard from "./pages/Dashboard";
import Quiz from "./pages/Quiz";
import Lesson from "./pages/Lesson";
import Tutor from "./pages/Tutor";
import Admin from "./pages/Admin";

/**
 * Rota padrao de cada estado do usuario.
 *
 * Depois do diagnostico o destino e o dashboard (e nao mais a lista de
 * exercicios): e ele quem apresenta a trilha recem-montada e diz qual e o
 * proximo passo.
 */
function defaultRouteFor(
  user: { is_admin: boolean; diagnostic_completed: boolean } | null,
): string {
  if (!user) return "/login";
  if (user.is_admin) return "/admin";
  if (!user.diagnostic_completed) return "/diagnostic";
  return "/dashboard";
}

function StudentRoute({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="card">Carregando...</div>;
  if (!user || user.is_admin) return <Navigate to={defaultRouteFor(user)} replace />;
  if (!user.diagnostic_completed) return <Navigate to="/diagnostic" replace />;
  return children;
}

function DiagnosticRoute({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="card">Carregando...</div>;
  if (!user || user.is_admin) return <Navigate to={defaultRouteFor(user)} replace />;
  // Diagnostico concluido nunca reabre: o aluno vai direto para a trilha.
  if (user.diagnostic_completed) return <Navigate to="/dashboard" replace />;
  return children;
}

function AdminRoute({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="card">Carregando...</div>;
  if (!user || !user.is_admin) return <Navigate to={defaultRouteFor(user)} replace />;
  return children;
}

export default function App() {
  const { user, doLogout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h2>Meu Tutor</h2>
        {user && (
          <div className="header-user">
            {!user.is_admin && (
              <>
                <Link className="link-button" to="/dashboard">
                  Minha trilha
                </Link>
                <Link className="link-button" to="/tutor">
                  Tutor
                </Link>
                <Link className="link-button" to="/exercise">
                  Pratica livre
                </Link>
              </>
            )}
            <span>{user.email}</span>
            <button className="link-button" onClick={doLogout}>
              Sair
            </button>
          </div>
        )}
      </header>
      <main>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/diagnostic"
            element={
              <DiagnosticRoute>
                <Diagnostic />
              </DiagnosticRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <StudentRoute>
                <Dashboard />
              </StudentRoute>
            }
          />
          <Route
            path="/quiz"
            element={
              <StudentRoute>
                <Quiz />
              </StudentRoute>
            }
          />
          <Route
            path="/lesson"
            element={
              <StudentRoute>
                <Lesson />
              </StudentRoute>
            }
          />
          <Route
            path="/tutor"
            element={
              <StudentRoute>
                <Tutor />
              </StudentRoute>
            }
          />
          <Route
            path="/exercise"
            element={
              <StudentRoute>
                <Exercise />
              </StudentRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <Admin />
              </AdminRoute>
            }
          />
          <Route path="*" element={<Navigate to={defaultRouteFor(user)} replace />} />
        </Routes>
      </main>
    </div>
  );
}
