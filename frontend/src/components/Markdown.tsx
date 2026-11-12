import { Fragment, ReactNode } from "react";
import katex from "katex";

/**
 * Renderizador de markdown minimo, com matematica via KaTeX.
 *
 * Cobre exatamente o que os prompts pedem ao modelo (titulos "## ", listas
 * "- ", negrito, codigo inline e formulas LaTeX) e nada alem disso.
 *
 * Formulas:
 * - bloco: $$...$$ ou \[...\] (podem ocupar varias linhas);
 * - inline: $...$ ou \(...\).
 *
 * O "$" de moeda nao vira formula: "R$ 10" e ignorado (cifrao colado a uma
 * letra), e um "$" seguido de espaco nao abre formula. Durante o streaming,
 * uma formula ainda sem o delimitador de fechamento aparece crua ate fechar.
 *
 * Seguranca: o unico HTML inserido e o gerado pelo KaTeX (com `trust: false`,
 * o padrao), que escapa o texto da formula. Nenhum HTML vindo do modelo e
 * inserido diretamente.
 */

/**
 * Vírgula decimal: em LaTeX "3,14" vira "3, 14" (a virgula e tratada como
 * pontuacao e ganha espaco). Envolver em chaves ("3{,}14") a transforma em
 * simbolo comum, sem espaco. Aplicado so entre dois digitos, entao "f(x, y)"
 * nao muda.
 */
export function normalizeDecimalComma(tex: string): string {
  return tex.replace(/(\d),(?=\d)/g, "$1{,}");
}

function MathSpan({ tex, display, k }: { tex: string; display: boolean; k: string }) {
  const html = katex.renderToString(normalizeDecimalComma(tex.trim()), {
    displayMode: display,
    throwOnError: false,
    strict: "ignore",
  });
  return display ? (
    <div className="md-math-block" key={k} dangerouslySetInnerHTML={{ __html: html }} />
  ) : (
    <span className="md-math" key={k} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

// Ordem importa: negrito e codigo antes da matematica.
// - \(...\)                         -> inline
// - $...$ : abre com "$" que nao vem depois de letra/numero/"$"/"\" e nao e
//   seguido de espaco; fecha com "$" que nao vem depois de espaco/"\" e nao e
//   seguido de digito (evita "$5 e $10" e "R$ 10").
const INLINE_PATTERN =
  /(\*\*[^*]+\*\*|`[^`]+`|\\\((?:.+?)\\\)|(?<![\\$\w])\$(?![\s$])[^$\n]+?(?<![\s\\])\$(?!\d))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = new RegExp(INLINE_PATTERN.source, "g");
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${index}`;
    if (token.startsWith("**")) {
      nodes.push(<strong key={key}>{renderInline(token.slice(2, -2), key)}</strong>);
    } else if (token.startsWith("`")) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("\\(")) {
      nodes.push(<MathSpan key={key} k={key} tex={token.slice(2, -2)} display={false} />);
    } else {
      nodes.push(<MathSpan key={key} k={key} tex={token.slice(1, -1)} display={false} />);
    }
    lastIndex = match.index + token.length;
    index += 1;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

/** Texto de uma linha (sem estrutura de markdown) com negrito e formulas. */
export function MathText({ text }: { text: string }) {
  return <Fragment>{renderInline(text ?? "", "mt")}</Fragment>;
}

function renderLines(text: string, keyPrefix: string, blocks: ReactNode[]) {
  const lines = text.split("\n");
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
    const k = `${keyPrefix}-${i}`;
    const line = rawLine.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^\s*[-*]\s+/, ""));
      return;
    }
    flushList(`list-${k}`);

    if (!line.trim()) return;
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = renderInline(heading[2], `h-${k}`);
      blocks.push(
        level <= 2 ? (
          <h3 className="md-heading" key={`h-${k}`}>
            {content}
          </h3>
        ) : (
          <h4 className="md-heading" key={`h-${k}`}>
            {content}
          </h4>
        ),
      );
      return;
    }
    blocks.push(
      <p className="md-paragraph" key={`p-${k}`}>
        {renderInline(line, `p-${k}`)}
      </p>,
    );
  });

  flushList(`list-${keyPrefix}-end`);
}

const BLOCK_MATH = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g;

export default function Markdown({ text }: { text: string }) {
  const source = text ?? "";
  const blocks: ReactNode[] = [];
  const pattern = new RegExp(BLOCK_MATH.source, "g");
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let segment = 0;

  // Formulas em bloco primeiro: podem atravessar varias linhas, entao nao
  // cabem no processamento linha a linha.
  while ((match = pattern.exec(source)) !== null) {
    if (match.index > lastIndex) {
      renderLines(source.slice(lastIndex, match.index), `s${segment}`, blocks);
    }
    const key = `math-${segment}`;
    blocks.push(<MathSpan key={key} k={key} tex={match[1] ?? match[2] ?? ""} display />);
    lastIndex = match.index + match[0].length;
    segment += 1;
  }
  if (lastIndex < source.length) renderLines(source.slice(lastIndex), `s${segment}`, blocks);

  return <Fragment>{blocks}</Fragment>;
}
