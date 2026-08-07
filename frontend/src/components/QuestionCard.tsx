import type { QuestionOut } from "../api/client";

/**
 * Bloco de enunciado + alternativas, compartilhado pelo diagnostico, pelos
 * questionarios e pelos exercicios avulsos. Concentrar aqui garante que
 * estados (selecionado, correto, errado, bloqueado) e acessibilidade fiquem
 * iguais nos tres fluxos.
 */
export default function QuestionCard({
  question,
  selected,
  onSelect,
  locked = false,
  correctAlternativeId = null,
  showResult = false,
}: {
  question: QuestionOut;
  selected: string | null;
  onSelect: (id: string) => void;
  locked?: boolean;
  correctAlternativeId?: string | null;
  showResult?: boolean;
}) {
  return (
    <>
      {question.topic && <p className="question-topic">{question.topic}</p>}
      <p className="question-statement">{question.statement}</p>

      <div className="alternatives" role="radiogroup" aria-label="Alternativas">
        {question.alternatives.map((alt) => {
          let extraClass = "";
          if (showResult) {
            if (correctAlternativeId && alt.id === correctAlternativeId) extraClass = "correct-reveal";
            else if (alt.id === selected && alt.id !== correctAlternativeId) extraClass = "wrong-reveal";
          }
          return (
            <label
              key={alt.id}
              className={`alternative ${selected === alt.id ? "selected" : ""} ${
                locked ? "disabled" : ""
              } ${extraClass}`}
            >
              <input
                type="radio"
                name={`question-${question.id}`}
                disabled={locked}
                checked={selected === alt.id}
                onChange={() => onSelect(alt.id)}
              />
              {alt.text}
            </label>
          );
        })}
      </div>
    </>
  );
}
