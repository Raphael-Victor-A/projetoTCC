import { Fragment, ReactNode } from "react";

/**
 * Renderizador de markdown minimo.
 *
 * Cobre exatamente o que os prompts pedem ao modelo (titulos "## ", listas
 * "- ", negrito e codigo inline) e nada alem disso. Preferimos ~40 linhas
 * proprias a uma dependencia de markdown + sanitizador so por causa disso;
 * como nao inserimos HTML cru, tambem nao abrimos superficie de XSS.
 */

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(<strong key={`${keyPrefix}-b${index}`}>{token.slice(2, -2)}</strong>);
    } else {
      nodes.push(<code key={`${keyPrefix}-c${index}`}>{token.slice(1, -1)}</code>);
    }
    lastIndex = match.index + token.length;
    index += 1;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

export default function Markdown({ text }: { text: string }) {
  const lines = (text ?? "").split("\n");
  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = (key: string) => {
    if (!listBuffer.length) return;
    blocks.push(
      <ul className="md-list" key={key}>
        {listBuffer.map((item, i) => (
          <li key={`${key}-${i}`}>{renderInline(item, `${key}-${i}`)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  lines.forEach((rawLine, i) => {
    const line = rawLine.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^\s*[-*]\s+/, ""));
      return;
    }
    flushList(`list-${i}`);

    if (!line.trim()) return;
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = renderInline(heading[2], `h-${i}`);
      blocks.push(
        level <= 2 ? (
          <h3 className="md-heading" key={`h-${i}`}>
            {content}
          </h3>
        ) : (
          <h4 className="md-heading" key={`h-${i}`}>
            {content}
          </h4>
        ),
      );
      return;
    }
    blocks.push(
      <p className="md-paragraph" key={`p-${i}`}>
        {renderInline(line, `p-${i}`)}
      </p>,
    );
  });

  flushList("list-end");
  return <Fragment>{blocks}</Fragment>;
}
