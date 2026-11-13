// Porta do backend configuravel: util quando a 8000 esta ocupada.
// Defina VITE_API_BASE ao subir o dev server para apontar para outra porta.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type FeedbackGroup = "diretivo" | "socratico";
export type Level = "basico" | "intermediario" | "avancado";
export type ModuleStatus = "nao_iniciado" | "em_andamento" | "concluido";
export type QuizKind = "diagnostico" | "reforco" | "pratica";
export type StepKind = "quiz" | "lesson" | "module_completed" | "diagnostic";

export interface UserOut {
  id: number;
  email: string;
  group: FeedbackGroup | null;
  level: Level;
  diagnostic_completed: boolean;
  is_admin: boolean;
}

export interface Alternative {
  id: string;
  text: string;
}

export interface QuestionOut {
  id: number;
  level: Level;
  topic: string;
  statement: string;
  alternatives: Alternative[];
  is_remedial: boolean;
  is_diagnostic: boolean;
  module_id: number | null;
  subject_id: number | null;
}

export interface DiagnosticOut {
  session_id: number;
  questions: QuestionOut[];
}

export interface FocusArea {
  module_id: number;
  module_title: string;
  subject_name: string;
  correct: number;
  total: number;
  accuracy: number;
}

export interface WrongAnswer {
  question_id: number;
  statement: string;
  chosen_text: string;
  correct_text: string;
  module_title: string;
  topic: string;
}

export interface DiagnosticResult {
  correct_count: number;
  total: number;
  assigned_level: Level;
  focus_areas: FocusArea[];
  strengths: FocusArea[];
  wrong_answers: WrongAnswer[];
  next_module_id: number | null;
}

export interface ModuleOut {
  id: number;
  slug: string;
  title: string;
  summary: string;
  level: Level;
  order_index: number;
  objectives: string[];
  contents: string[];
  bncc_codes: string[];
  status: ModuleStatus;
  completion: number;
  performance: number | null;
  priority: number;
  next_step: string | null;
}

export interface SubjectOut {
  id: number;
  slug: string;
  name: string;
  area: string;
  color: string;
  description: string;
  completion: number;
  performance: number | null;
  modules: ModuleOut[];
}

export interface Recommendation {
  module_id: number;
  module_title: string;
  subject_name: string;
  subject_color: string;
  reason: string;
  next_step: string | null;
  completion: number;
  performance: number | null;
}

export interface StudyPlan {
  level: Level;
  diagnostic_completed: boolean;
  total_attempts: number;
  total_correct: number;
  accuracy: number;
  modules_completed: number;
  modules_total: number;
  overall_completion: number;
  current_module_id: number | null;
  recommendations: Recommendation[];
  weak_topics: string[];
  subjects: SubjectOut[];
}

export interface NextStep {
  kind: StepKind;
  module_id: number | null;
  module_title: string | null;
  subject_name: string | null;
  lesson_id: number | null;
  step_index: number;
  total_steps: number;
  message: string;
}

export interface QuizOut {
  id: number;
  kind: QuizKind;
  level: Level;
  module_id: number | null;
  module_title: string | null;
  subject_name: string | null;
  current_index: number;
  total: number;
  correct_count: number;
  completed: boolean;
  questions: QuestionOut[];
  /** Acerto (true) / erro (false) / nao respondida (null), na ordem das questoes. */
  results: (boolean | null)[];
}

export interface QuizAnswerResult {
  correct: boolean;
  correct_alternative_id: string | null;
  explanation: string | null;
  attempt_id: number;
  answered_index: number;
  total: number;
  correct_count: number;
  finished: boolean;
  feedback_available: boolean;
}

export interface QuizResult {
  quiz_id: number;
  correct_count: number;
  total: number;
  accuracy: number;
  next_step: NextStep;
}

export interface LessonSection {
  heading: string;
  body: string;
}

export interface LessonExample {
  title: string;
  statement: string;
  solution: string;
}

export interface LessonOut {
  id: number;
  module_id: number | null;
  topic: string;
  level: Level;
  title: string;
  intro: string;
  sections: LessonSection[];
  key_concepts: string[];
  examples: LessonExample[];
  diagram: string | null;
  summary: string;
  generated: boolean;
  reexplain_limit: number;
  reexplain_remaining: number;
  reexplain_text: string | null;
}

export interface FeedbackOut {
  mode: FeedbackGroup;
  content: string;
}

export interface AnswerResult {
  correct: boolean;
  correct_alternative_id: string | null;
  level: Level;
  level_changed: boolean;
  needs_remediation: boolean;
  attempt_id: number | null;
  feedback: FeedbackOut | null;
  feedback_available: boolean;
}

export interface ProgressOut {
  level: Level;
  window_count: number;
  window_correct: number;
  /** Acerto/erro de cada exercicio do bloco atual, em ordem. */
  window_results: boolean[];
  needs_remediation: boolean;
  total_attempts: number;
  total_correct: number;
}

export interface TutorSource {
  title: string;
  uri: string;
}

function getToken(): string | null {
  return localStorage.getItem("token");
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = authHeaders({
    ...(options.body && !(options.body instanceof URLSearchParams)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(options.headers as Record<string, string>),
  });

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // resposta sem corpo JSON: mantem o statusText
    }
    const error = new Error(detail) as Error & { status?: number };
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/**
 * Consumo de Server-Sent Events.
 *
 * Nao usa `EventSource` de proposito: ela nao permite enviar o header
 * Authorization nem usar POST. Com `fetch` + reader lemos o mesmo protocolo
 * mantendo o Bearer token, que e como o resto da API se autentica.
 */
export interface StreamHandlers {
  onMeta?: (data: any) => void;
  onChunk?: (text: string) => void;
  onSources?: (sources: TutorSource[]) => void;
  onError?: (message: string) => void;
  onDone?: (data: any) => void;
}

export async function streamSSE(
  path: string,
  options: RequestInit,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const headers = authHeaders({
    Accept: "text/event-stream",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string>),
  });

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, signal });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // sem corpo JSON
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (rawEvent: string) => {
    let name = "message";
    const dataLines: string[] = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let payload: any;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }
    if (name === "chunk") handlers.onChunk?.(payload.text ?? "");
    else if (name === "meta") handlers.onMeta?.(payload);
    else if (name === "sources") handlers.onSources?.(payload.sources ?? []);
    else if (name === "error") handlers.onError?.(payload.message ?? "Erro inesperado");
    else if (name === "done") handlers.onDone?.(payload);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer);
}

// --------------------------------------------------------------------------
// Autenticacao
// --------------------------------------------------------------------------

export async function register(email: string, password: string) {
  const data = await request<{ access_token: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.access_token);
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const data = await request<{ access_token: string }>("/auth/login", { method: "POST", body });
  localStorage.setItem("token", data.access_token);
}

export function logout() {
  localStorage.removeItem("token");
}

export function isAuthenticated() {
  return !!getToken();
}

export const getMe = () => request<UserOut>("/auth/me");

// --------------------------------------------------------------------------
// Diagnostico
// --------------------------------------------------------------------------

export const getDiagnostic = () => request<DiagnosticOut>("/diagnostic");

export const submitDiagnostic = (
  sessionId: number | null,
  answers: { question_id: number; alternative_id: string }[],
) =>
  request<DiagnosticResult>("/diagnostic/submit", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, answers }),
  });

// --------------------------------------------------------------------------
// Trilha, grade e mini aulas
// --------------------------------------------------------------------------

export const getStudyPlan = () => request<StudyPlan>("/study-plan");
export const getSubjects = () => request<SubjectOut[]>("/subjects");
export const getNextStep = () => request<NextStep>("/next-step");

export const selectModule = (moduleId: number) =>
  request<NextStep>(`/modules/${moduleId}/select`, { method: "POST" });

export const getModuleLesson = (moduleId: number) =>
  request<LessonOut>(`/modules/${moduleId}/lesson`);

export const getLesson = (lessonId: number) => request<LessonOut>(`/lessons/${lessonId}`);

export const completeLesson = (lessonId: number) =>
  request<NextStep>(`/lessons/${lessonId}/complete`, { method: "POST" });

/** "Explicar de outro jeito": limitado por aula no backend (409 sem saldo). */
export const streamLessonReexplain = (
  lessonId: number,
  handlers: StreamHandlers,
  signal?: AbortSignal,
) => streamSSE(`/lessons/${lessonId}/reexplain`, { method: "POST" }, handlers, signal);

// --------------------------------------------------------------------------
// Questionarios
// --------------------------------------------------------------------------

export const startQuiz = (moduleId: number | null, kind: QuizKind = "reforco", size?: number) =>
  request<QuizOut>("/quiz/start", {
    method: "POST",
    body: JSON.stringify({ module_id: moduleId, kind, size }),
  });

export const getQuiz = (quizId: number) => request<QuizOut>(`/quiz/${quizId}`);

export const answerQuiz = (quizId: number, question_id: number, alternative_id: string) =>
  request<QuizAnswerResult>(`/quiz/${quizId}/answer`, {
    method: "POST",
    body: JSON.stringify({ question_id, alternative_id }),
  });

export const finishQuiz = (quizId: number) =>
  request<QuizResult>(`/quiz/${quizId}/finish`, { method: "POST" });

// --------------------------------------------------------------------------
// Exercicios avulsos e feedback
// --------------------------------------------------------------------------

export const getNextExercise = (moduleId?: number) =>
  request<QuestionOut>(`/exercises/next${moduleId ? `?module_id=${moduleId}` : ""}`);

export const submitExercise = (question_id: number, alternative_id: string) =>
  request<AnswerResult>("/exercises/submit", {
    method: "POST",
    body: JSON.stringify({ question_id, alternative_id }),
  });

export const getProgress = () => request<ProgressOut>("/progress");

// --------------------------------------------------------------------------
// Dicas durante a questao ("Preciso de ajuda")
// --------------------------------------------------------------------------

export interface HintOut {
  number: number;
  content: string;
}

export interface HintsOut {
  hints: HintOut[];
  max_hints: number;
  remaining: number;
  degraded: boolean;
}

export const getHints = (questionId: number) =>
  request<HintsOut>(`/questions/${questionId}/hints`);

export const requestHint = (questionId: number, quizId?: number | null) =>
  request<HintsOut>(`/questions/${questionId}/hint`, {
    method: "POST",
    body: JSON.stringify({ quiz_id: quizId ?? null }),
  });

export const getFeedback = (attemptId: number) => request<FeedbackOut>(`/feedback/${attemptId}`);

export const streamFeedback = (
  attemptId: number,
  handlers: StreamHandlers,
  signal?: AbortSignal,
) => streamSSE(`/feedback/${attemptId}/stream`, { method: "GET" }, handlers, signal);

// --------------------------------------------------------------------------
// Tutor
// --------------------------------------------------------------------------

export const askTutor = (
  body: { question: string; module_id?: number | null; use_search?: boolean | null },
  handlers: StreamHandlers,
  signal?: AbortSignal,
) => streamSSE("/tutor/ask", { method: "POST", body: JSON.stringify(body) }, handlers, signal);

// --------------------------------------------------------------------------
// Admin
// --------------------------------------------------------------------------

export interface GroupStats {
  group: FeedbackGroup;
  total_users: number;
  total_attempts: number;
  correct_attempts: number;
  accuracy: number;
  level_distribution: Record<Level, number>;
  avg_gemini_latency_ms: number;
  leak_detected_count: number;
  leak_detected_rate: number;
  fallback_used_count: number;
}

export interface AdminStats {
  total_students: number;
  groups: GroupStats[];
}

export const getAdminStats = () => request<AdminStats>("/admin/stats");

export interface StudentOut {
  id: number;
  email: string;
  group: FeedbackGroup;
  level: Level;
  diagnostic_completed: boolean;
}

export const getStudents = () => request<StudentOut[]>("/admin/students");

export const setStudentGroup = (id: number, group: FeedbackGroup) =>
  request<StudentOut>(`/admin/students/${id}/group`, {
    method: "PATCH",
    body: JSON.stringify({ group }),
  });
