import { useMemo } from "react";
import sixsevenImg from "../assets/sixseven.webp";

/**
 * Sixseven ("Meia-Sete", "O 67"): a capivara mascote.
 *
 * Regras (ver tambem o prototipo aprovado):
 * - uma fala curta por momento, nunca com conteudo da questao — explicar e
 *   dar dica continua sendo papel do tutor de IA e do filtro anti-vazamento;
 * - igual para os dois grupos do experimento (diretivo e socratico), para nao
 *   virar uma variavel a mais no TCC: nada aqui depende de `user.group`.
 *
 * A ilustracao tem uma pose so; cada estado muda a animacao (styles.css,
 * secao "Mascote") e, na comemoracao, aparece o trofeu.
 */
export type MascotMood = "zen" | "happy" | "oops" | "hint" | "party";

export const MASCOT_LINES: Record<MascotMood | "start" | "lesson" | "tutor", string[]> = {
  zen: [
    "Calma la, a gente resolve isso tomando um terere.",
    "Respira. Uma questao de cada vez.",
    "To de boa. Manda a braba!",
  ],
  start: ["Bora? Sao so 5 questoes.", "Calma la, a gente resolve isso tomando um terere."],
  lesson: ["Bora ler rapidinho? Depois tem questionario.", "Mini aula na faixa. Pega o terere."],
  happy: [
    "Absolutamente cinematografico.",
    "O verdadeiro Giga Chad da aritmetica.",
    "Cravou! Nem precisei tirar o oculos.",
  ],
  oops: [
    "Deu ruim, F no chat... mas bora de novo!",
    "Errar faz parte. Ate capivara escorrega no barranco.",
    "Respira, um gole de terere e le a explicacao.",
  ],
  hint: [
    "Travou? Normal. Pede uma dica que eu te mostro o caminho.",
    "Le de novo com calma. O que a questao quer descobrir?",
  ],
  tutor: ["Manda a braba!"],
  party: ["Modulo zerado! Cinematografico.", "Trofeu numa mao, terere na outra."],
};

/** Sorteia uma fala uma vez por montagem (nao troca a cada render). */
export function useMascotLine(kind: keyof typeof MASCOT_LINES, seed?: unknown): string {
  return useMemo(() => {
    const lines = MASCOT_LINES[kind];
    return lines[Math.floor(Math.random() * lines.length)];
    // seed: troca a fala quando muda a questao, por exemplo
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, seed]);
}

const TROPHY = (
  <svg className="mascot-trophy" viewBox="0 0 48 56" aria-hidden="true">
    <defs>
      <linearGradient id="mascot-gold" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#fde68a" />
        <stop offset=".5" stopColor="#f59e0b" />
        <stop offset="1" stopColor="#b45309" />
      </linearGradient>
    </defs>
    <path d="M10 4 H38 V16 A14 14 0 0 1 10 16 Z" fill="url(#mascot-gold)" stroke="#92400e" strokeWidth="2" />
    <path d="M10 8 C1 8 2 22 12 22 M38 8 C47 8 46 22 36 22" fill="none" stroke="#b45309" strokeWidth="3" />
    <rect x="20" y="30" width="8" height="10" fill="#d97706" />
    <rect x="12" y="40" width="24" height="8" rx="2" fill="url(#mascot-gold)" stroke="#92400e" strokeWidth="1.6" />
    <path d="M17 8 l3 8" stroke="#fff" strokeOpacity=".75" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

export default function Mascot({
  mood = "zen",
  crop = "full",
  size,
  className = "",
}: {
  mood?: MascotMood;
  /** "full" = corpo inteiro; "head" = avatar redondo so do rosto. */
  crop?: "full" | "head";
  /** Largura em px (a altura acompanha). */
  size?: number;
  className?: string;
}) {
  return (
    <div
      className={`mascot crop-${crop} ${className}`}
      data-mood={mood}
      style={size ? { width: size } : undefined}
    >
      <img src={sixsevenImg} alt="" draggable={false} />
      {mood === "party" && TROPHY}
    </div>
  );
}

/** Balao de fala do mascote. */
export function MascotSays({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <span className={`mascot-says ${className}`}>{children}</span>;
}

/** Fala sorteada de um momento, num balao. */
export function MascotLine({ kind, className = "" }: { kind: keyof typeof MASCOT_LINES; className?: string }) {
  const line = useMascotLine(kind);
  return <MascotSays className={className}>{line}</MascotSays>;
}

/**
 * Reacao do mascote a correcao (avatar + uma fala), ao lado do titulo do
 * resultado. O feedback pedagogico continua logo abaixo, sem mudanca.
 */
export function MascotReaction({ correct, title }: { correct: boolean; title: string }) {
  const line = useMascotLine(correct ? "happy" : "oops");
  return (
    <div className="mascot-reaction">
      <Mascot mood={correct ? "happy" : "oops"} crop="head" size={58} />
      <div className="mascot-reaction-text">
        <div className="result-title">{title}</div>
        <MascotSays className="small">{line}</MascotSays>
      </div>
    </div>
  );
}
