import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import * as api from "../api/client";
import { BookIcon } from "../components/Icons";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { doLogin, doRegister } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await doLogin(email, password);
      } else {
        await doRegister(email, password);
      }
      const me = await api.getMe();
      if (me.is_admin) navigate("/admin");
      else if (!me.diagnostic_completed) navigate("/diagnostic");
      else navigate("/exercise");
    } catch (err) {
      const status = (err as { status?: number }).status;
      setError(
        mode === "login"
          ? "Nao foi possivel entrar. Confira seu usuario (ou e-mail) e sua senha."
          : status === 400
            ? "Esse usuario ja esta em uso. Escolha outro."
            : status === 422
              ? "Confira os dados: o usuario precisa ter pelo menos 3 caracteres (letras sem acento, numeros, ponto, hifen ou um e-mail) e a senha pelo menos 8."
              : "Nao foi possivel criar sua conta agora. Tente de novo."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <div className="text-center" style={{ marginBottom: "1.25rem" }}>
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "var(--color-primary-bg)",
            color: "var(--color-primary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 0.75rem",
          }}
        >
          <BookIcon size={30} />
        </div>
        <h1>Seu tutor particular</h1>
        <p className="subtitle">Estude no seu ritmo, com ajuda passo a passo.</p>
      </div>

      <div className="tabs" role="tablist" aria-label="Entrar ou criar conta">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "login"}
          className={mode === "login" ? "tab active" : "tab"}
          onClick={() => setMode("login")}
        >
          Já tenho conta
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "register"}
          className={mode === "register" ? "tab active" : "tab"}
          onClick={() => setMode("register")}
        >
          Sou novo aqui
        </button>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="email">
          {mode === "login" ? "Usuario ou e-mail" : "Escolha um nome de usuario (ou use seu e-mail)"}
          <input
            id="email"
            type="text"
            required
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="ex.: joao.silva ou nome@exemplo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label htmlFor="password">
          Sua senha
          <input
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            placeholder="Pelo menos 8 letras ou numeros"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? "Um momento..." : mode === "login" ? "Entrar" : "Criar minha conta"}
        </button>
      </form>
    </div>
  );
}
