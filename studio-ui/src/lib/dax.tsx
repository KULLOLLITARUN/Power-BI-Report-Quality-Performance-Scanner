import React from 'react';

const KEYWORDS = new Set(['VAR', 'RETURN', 'EVALUATE', 'DEFINE', 'ORDER', 'BY', 'ASC', 'DESC', 'NOT', 'AND', 'OR', 'IN', 'TRUE', 'FALSE']);

// strings | comments | 'Table'[Col] / Table[Col] / [Measure] | FUNCTION( | numbers | words
const TOKEN = /("(?:[^"]|"")*")|(\/\/[^\n]*|--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^']|'')*'(?:\[[^\]]*\])?|[A-Za-z_][\w]*\[[^\]]*\]|\[[^\]]*\])|([A-Za-z_][\w.]*)(?=\s*\()|(\b\d+(?:\.\d+)?\b)|(\b[A-Za-z_]+\b)/g;

/** Tokenise DAX into coloured spans. Plain text stays plain, so this is safe for any input. */
export function highlightDax(src: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  let k = 0;
  let m: RegExpExecArray | null;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(src))) {
    if (m.index > last) out.push(src.slice(last, m.index));
    let cls: string | null = null;
    if (m[1]) cls = 'str';
    else if (m[2]) cls = 'cm';
    else if (m[3]) cls = 'ref';
    else if (m[4]) cls = 'fn';
    else if (m[5]) cls = 'n';
    else if (m[6] && KEYWORDS.has(m[6].toUpperCase())) cls = 'kw';
    out.push(cls ? <span key={k++} className={cls}>{m[0]}</span> : m[0]);
    last = TOKEN.lastIndex;
  }
  if (last < src.length) out.push(src.slice(last));
  return out;
}

/** TMDL / key-value lines: colour the leading keyword. */
export function highlightTmdl(src: string): React.ReactNode[] {
  return src.split('\n').flatMap((line, i, all) => {
    const m = /^(\s*)([A-Za-z_]+)(:|\s|$)(.*)$/.exec(line);
    const node = m
      ? <React.Fragment key={i}>{m[1]}<span className="fn">{m[2]}</span>{m[3]}{m[4]}</React.Fragment>
      : <React.Fragment key={i}>{line}</React.Fragment>;
    return i < all.length - 1 ? [node, '\n'] : [node];
  });
}

/** Evidence text: DAX-looking strings get DAX colours, TMDL-looking ones get TMDL colours. */
export function highlightAuto(src: string): React.ReactNode[] {
  if (/^\s*(relationship|table|column|measure|model|partition|annotation)\b/m.test(src) && /:\s/.test(src)) return highlightTmdl(src);
  if (/[A-Z]{3,}\s*\(|\[[^\]]+\]/.test(src)) return highlightDax(src);
  return [src];
}

export const DaxCode: React.FC<{ code: string; lines?: boolean; wrap?: boolean }> = ({ code, lines, wrap }) => {
  if (!code?.trim()) return <pre className="code muted">No expression defined.</pre>;
  if (!lines) return <pre className={`code${wrap ? ' wrap' : ''}`}>{highlightDax(code)}</pre>;
  return (
    <pre className="code lines">
      {code.replace(/\r\n/g, '\n').split('\n').map((ln, i) => <span key={i} className="ln">{highlightDax(ln)}{'\n'}</span>)}
    </pre>
  );
};
