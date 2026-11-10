import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PauseIcon } from "./Icons";

/**
 * "Pausar": sai da atividade com uma confirmacao curta, deixando claro o que
 * fica salvo. Volta para a trilha (/dashboard).
 */
export default function PauseButton({ message }: { message: string }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <button type="button" className="pause-button" onClick={() => setOpen(true)}>
        <PauseIcon size={16} /> Pausar
      </button>

      {open && (
        <div className="help-overlay" onClick={() => setOpen(false)}>
          <div
            className="help-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pause-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="pause-title">Quer fazer uma pausa?</h3>
            <p>{message}</p>
            <div className="button-row" style={{ marginTop: "1.25rem" }}>
              <button type="button" onClick={() => setOpen(false)} style={{ flex: 1 }}>
                Continuar estudando
              </button>
              <button type="button" className="secondary" onClick={() => navigate("/dashboard")}>
                Sair por agora
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
