const API_BASE = "http://localhost:8000";

export type FeedbackGroup = "diretivo" | "socratico";
export type Level = "basico" | "intermediario" | "avancado";

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
}

export interface DiagnosticResult {
  correct_count: number;
  total: number;
  assigned_level: Level;
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
  feedback: FeedbackOut | null;
}

export interface ProgressOut {
  level: Level;
  window_count: number;
  window_correct: number;
  needs_remediation: boolean;
  total_attempts: number;
  total_correct: number;
}

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof URLSearchParams)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

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
  const data = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body,
  });
  localStorage.setItem("token", data.access_token);
}

export function logout() {
  localStorage.removeItem("token");
}

export function isAuthenticated() {
  return !!getToken();
}

export const getMe = () => request<UserOut>("/auth/me");

export const getDiagnostic = () => request<QuestionOut[]>("/diagnostic");

export const submitDiagnostic = (answers: { question_id: number; alternative_id: string }[]) =>
  request<DiagnosticResult>("/diagnostic/submit", {
    method: "POST",
    body: JSON.stringify({ answers }),
  });

export const getNextExercise = () => request<QuestionOut>("/exercises/next");

export const submitExercise = (question_id: number, alternative_id: string) =>
  request<AnswerResult>("/exercises/submit", {
    method: "POST",
    body: JSON.stringify({ question_id, alternative_id }),
  });

export const getProgress = () => request<ProgressOut>("/progress");

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
