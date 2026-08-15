import React from 'react';

const DAX_KEYWORDS = new Set([
  'VAR', 'RETURN', 'EVALUATE', 'DEFINE', 'ORDER', 'BY', 'ASC', 'DESC', 'NOT', 'AND', 'OR', 'IN'
]);

const DAX_FUNCTIONS = new Set([
  'CALCULATE', 'CALCULATETABLE', 'FILTER', 'ALL', 'ALLEXCEPT', 'ALLSELECTED', 'VALUES', 'DISTINCT',
  'SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'COUNTA', 'COUNTROWS', 'DIVIDE', 'IF', 'SWITCH',
  'ISBLANK', 'BLANK', 'RELATED', 'RELATEDTABLE', 'USERELATIONSHIP', 'CROSSFILTER', 'TREATAS',
  'KEEPFILTERS', 'REMOVEFILTERS', 'SELECTEDVALUE', 'FORMAT', 'DATE', 'DATEDIFF', 'DATEADD',
  'TOTALYTD', 'TOTALQTD', 'TOTALMTD', 'SAMEPERIODLASTYEAR', 'PARALLELPERIOD', 'DATESYTD',
  'DATESINPERIOD', 'EARLIER', 'EARLIEST', 'LOOKUPVALUE', 'SUMX', 'AVERAGEX', 'COUNTX', 'MINX', 'MAXX'
]);

export function highlightDax(code: string): React.ReactNode {
  if (!code) return <span className="text-slate-500 italic">No expression defined</span>;

  const lines = code.split('\n');

  return (
    <pre className="font-mono text-xs leading-relaxed overflow-x-auto selection:bg-emerald-500/30">
      {lines.map((line, lineIdx) => {
        // Simple regex-based line tokenization
        // Matches strings, comments, measure refs [Measure], table refs 'Table'[Col], words
        const tokens: React.ReactNode[] = [];
        let remaining = line;
        let tokenKey = 0;

        // Check for line comment
        if (remaining.trim().startsWith('--') || remaining.trim().startsWith('//')) {
          return (
            <div key={lineIdx} className="text-slate-500 italic">
              {line}
            </div>
          );
        }

        while (remaining.length > 0) {
          // String literal "..."
          if (remaining.startsWith('"')) {
            const endIdx = remaining.indexOf('"', 1);
            if (endIdx !== -1) {
              const str = remaining.substring(0, endIdx + 1);
              tokens.push(<span key={tokenKey++} className="text-emerald-300">{str}</span>);
              remaining = remaining.substring(endIdx + 1);
              continue;
            }
          }

          // Table reference 'Table'[Column] or 'Table'
          if (remaining.startsWith("'")) {
            const endQuote = remaining.indexOf("'", 1);
            if (endQuote !== -1) {
              const tbl = remaining.substring(0, endQuote + 1);
              tokens.push(<span key={tokenKey++} className="text-teal-400 font-medium">{tbl}</span>);
              remaining = remaining.substring(endQuote + 1);
              continue;
            }
          }

          // Measure or column bracket [Name]
          if (remaining.startsWith('[')) {
            const endBracket = remaining.indexOf(']');
            if (endBracket !== -1) {
              const bracketRef = remaining.substring(0, endBracket + 1);
              tokens.push(<span key={tokenKey++} className="text-amber-400 font-semibold">{bracketRef}</span>);
              remaining = remaining.substring(endBracket + 1);
              continue;
            }
          }

          // Word tokens (keywords / functions / identifiers)
          const wordMatch = remaining.match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
          if (wordMatch) {
            const word = wordMatch[0];
            const upperWord = word.toUpperCase();
            if (DAX_KEYWORDS.has(upperWord)) {
              tokens.push(<span key={tokenKey++} className="text-pink-400 font-bold">{word}</span>);
            } else if (DAX_FUNCTIONS.has(upperWord)) {
              tokens.push(<span key={tokenKey++} className="text-blue-400 font-bold">{word}</span>);
            } else {
              tokens.push(<span key={tokenKey++} className="text-slate-200">{word}</span>);
            }
            remaining = remaining.substring(word.length);
            continue;
          }

          // Operators & other chars
          tokens.push(<span key={tokenKey++} className="text-slate-400">{remaining[0]}</span>);
          remaining = remaining.substring(1);
        }

        return (
          <div key={lineIdx} className="min-h-[1.25rem]">
            {tokens}
          </div>
        );
      })}
    </pre>
  );
}
