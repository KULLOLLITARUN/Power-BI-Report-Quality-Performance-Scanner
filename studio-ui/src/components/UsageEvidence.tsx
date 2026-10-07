import React, { useMemo } from 'react';
import type { ScanResult } from '../types';
import { measureEvidence, summarizeSources } from '../lib/usage';

const MAX_SOURCES = 4;

const Sources: React.FC<{ items: string[] }> = ({ items }) => (
  <>
    {items.slice(0, MAX_SOURCES).join(', ')}
    {items.length > MAX_SOURCES && <span className="muted"> and {items.length - MAX_SOURCES} more</span>}
  </>
);

/** What the unused-measure check looked at for one measure, and what it found in each place. */
export const UsageEvidence: React.FC<{ name: string; scan: ScanResult; title?: string }> = ({ name, scan, title = 'Where pbiscan looked' }) => {
  const ev = useMemo(() => measureEvidence(name, scan), [name, scan]);

  if (!ev.hasReferences) {
    return (
      <div className="blk"><div className="label">{title}</div>
        <p className="muted" style={{ fontSize: 13 }}>This scan has no reference data. Rescan with this version of pbiscan to see where the measure is used.</p>
      </div>
    );
  }

  const verdict = ev.used
    ? (ev.isRoot ? 'Used directly.' : 'Used through another measure.')
    : 'No checked place uses it, directly or through other measures.';

  return (
    <div className="blk">
      <div className="label">{title}</div>
      <table className="evidence">
        <caption className="sr-only">Places checked for uses of {name}</caption>
        <tbody>
          {ev.rows.map((row) => (
            <tr key={row.id} className={row.refs.length ? 'hit' : undefined}>
              <th scope="row">{row.label}</th>
              <td>
                {row.refs.length ? <Sources items={summarizeSources(row.refs)} /> : <span className="muted">none</span>}
                {row.uncounted.length > 0 && (
                  <div className="muted">Also named in {summarizeSources(row.uncounted).join(', ')}, but not counted as a use.</div>
                )}
              </td>
            </tr>
          ))}
          <tr className={ev.referencedBy.some((r) => r.used) ? 'hit' : undefined}>
            <th scope="row">DAX in other measures</th>
            <td>
              {!ev.hasGraph ? <span className="muted">not in this scan</span>
                : ev.referencedBy.length ? ev.referencedBy.map((r, i) => (
                  <React.Fragment key={r.name}>
                    {i > 0 && ', '}<span className="mono">[{r.name}]</span>{!r.used && <span className="muted"> (itself unused)</span>}
                  </React.Fragment>
                )) : <span className="muted">none</span>}
            </td>
          </tr>
        </tbody>
      </table>
      <p style={{ fontSize: 13 }}>{verdict}</p>
    </div>
  );
};
