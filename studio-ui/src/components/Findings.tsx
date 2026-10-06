import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, ClipboardCopy, EyeOff, FileStack, Search, Sigma, TriangleAlert, Wrench } from 'lucide-react';
import type { AuditFinding } from '../types';
import { AREA_LABEL, sevMeta, type Severity } from '../lib/severity';
import { highlightAuto } from '../lib/dax';
import { animate } from '../lib/motion';
import { Confidence, SevMarker, SevTag, copyText, useToast } from './ui';

// Rules `pbiscan fix` can patch (pbiscan/remediation/patchers).
export const FIXABLE_RULES = new Set(['MODEL_BIDIRECTIONAL', 'DAX_UNUSED_MEASURE', 'M_HARDCODED_DATA_SOURCE', 'MODEL_AUTO_DATETIME_BLOAT']);

export const findingKey = (f: AuditFinding) => `${f.rule_id}|${f.location ?? ''}|${f.evidence ?? ''}`;

interface ListProps {
  findings: AuditFinding[];        // already filtered + sorted
  total: number;
  selected: string | null;
  onSelect: (f: AuditFinding) => void;
  query: string; onQuery: (q: string) => void;
  area: string; onArea: (a: string) => void;
  sev: Severity | null; onClearSev: () => void;
  table: string | null; onClearTable: () => void;
  suppressedCount: number; showSuppressed: boolean; onShowSuppressed: (v: boolean) => void;
}

export const FindingsList: React.FC<ListProps> = (p) => {
  const listRef = useRef<HTMLUListElement>(null);
  const firstRender = useRef(true);
  useEffect(() => {
    animate({
      targets: listRef.current?.querySelectorAll('.row'),
      translateY: [6, 0], opacity: [0.25, 1],
      delay: (_: unknown, i: number) => (firstRender.current ? 120 : 0) + Math.min(i, 14) * 30,
      duration: 380, easing: 'easeOutCubic',
    });
    firstRender.current = false;
  }, [p.area, p.sev, p.table, p.showSuppressed]);

  const onKey = (e: React.KeyboardEvent<HTMLLIElement>, f: AuditFinding) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); p.onSelect(f); }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const sib = (e.key === 'ArrowDown' ? e.currentTarget.nextElementSibling : e.currentTarget.previousElementSibling) as HTMLElement | null;
      sib?.focus();
    }
  };

  return (
    <section className="panel" aria-label="Findings">
      <div className="panel-head">
        <h2>Findings</h2>
        <span className="spacer" />
        <span className="label">{p.findings.length} of {p.total}</span>
      </div>
      <div className="filters">
        <label className="search">
          <Search aria-hidden="true" />
          <span className="sr-only">Search findings</span>
          <input type="search" value={p.query} onChange={(e) => p.onQuery(e.target.value)} placeholder="Search rule, table, measure…" autoComplete="off" />
        </label>
        <div className="seg" role="group" aria-label="Area">
          {['all', 'model', 'dax', 'report'].map((a) => (
            <button key={a} aria-pressed={p.area === a} onClick={() => p.onArea(a)}>{a === 'all' ? 'All' : AREA_LABEL[a]}</button>
          ))}
        </div>
        {p.table && <span className="filter-chip">table: {p.table}<button onClick={p.onClearTable} aria-label="Clear table filter">×</button></span>}
        {p.sev && <span className="filter-chip">severity: {sevMeta(p.sev).label.toLowerCase()}<button onClick={p.onClearSev} aria-label="Clear severity filter">×</button></span>}
      </div>
      {p.findings.length === 0 ? (
        <div className="empty">
          <CheckCircle2 aria-hidden="true" />
          {p.total === 0 ? <><strong>No open findings</strong><span>This project passes every rule pbiscan checks.</span></>
            : <><strong>No findings match these filters</strong><span>Clear a filter to see the other {p.total}.</span></>}
        </div>
      ) : (
        <ul className="rows" role="listbox" aria-label="Findings list" ref={listRef}>
          {p.findings.map((f) => {
            const key = findingKey(f);
            return (
              <li key={key} className={`row${f.suppressed ? ' is-suppressed' : ''}`} role="option" tabIndex={0} aria-selected={p.selected === key}
                  onClick={() => p.onSelect(f)} onKeyDown={(e) => onKey(e, f)}>
                <span className="mk"><SevMarker sev={f.severity} /></span>
                <span className="row-title">{f.title}</span>
                <span className="row-sub"><span>{f.rule_id}</span>{f.location && <span className="loc">{f.location}</span>}{f.suppressed && <span>suppressed</span>}</span>
                <span className="row-side"><SevTag sev={f.severity} /><Confidence value={f.confidence ?? 0} /></span>
              </li>
            );
          })}
        </ul>
      )}
      {p.suppressedCount > 0 && (
        <div className="list-foot">
          <label className="check"><input type="checkbox" checked={p.showSuppressed} onChange={(e) => p.onShowSuppressed(e.target.checked)} />Show {p.suppressedCount} suppressed</label>
        </div>
      )}
    </section>
  );
};

interface DetailProps {
  finding: AuditFinding | null;
  canSuppress: boolean;
  onSuppress: (f: AuditFinding) => Promise<void>;
  onOpenFixes: () => void;
  onOpenMeasure?: (() => void) | null;
  onOpenPage?: (() => void) | null;
}

export const FindingDetail: React.FC<DetailProps> = ({ finding: f, canSuppress, onSuppress, onOpenFixes, onOpenMeasure, onOpenPage }) => {
  const toast = useToast();
  const ref = useRef<HTMLDivElement>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setConfirming(false);
    animate({ targets: ref.current?.children, translateY: [8, 0], opacity: [0.2, 1], delay: (_: unknown, i: number) => i * 40, duration: 360, easing: 'easeOutQuad' });
  }, [f]);

  if (!f) {
    return <div className="empty" style={{ padding: 28 }}><strong>Select a finding</strong><span>Its evidence, impact and fix appear here.</span></div>;
  }

  const copyTask = async () => {
    const ok = await copyText(`${f.rule_id}: ${f.title}\n${f.location ?? ''}\n\n${f.issue}\n\nFix: ${f.recommendation}`);
    toast(ok ? 'Copied the finding as a task.' : 'Copying is blocked here. Select the text instead.', ok ? 'info' : 'error');
  };
  const suppress = async () => {
    setBusy(true);
    try { await onSuppress(f); setConfirming(false); } finally { setBusy(false); }
  };

  return (
    <div ref={ref}>
      <div className="detail-head">
        <div className="detail-meta">
          <SevMarker sev={f.severity} /><SevTag sev={f.severity} /><span>{f.rule_id}</span><span>· {AREA_LABEL[f.category] ?? f.category}</span>
          <Confidence value={f.confidence ?? 0} label />
          {f.suppressed && <span className="chip">suppressed</span>}
        </div>
        <h3>{f.title}</h3>
        {f.location && <div className="where">{f.location}</div>}
      </div>
      <div className="detail-body">
        {f.issue && <div className="blk"><div className="label">What pbiscan found</div><p>{f.issue}</p></div>}
        {f.evidence && <div className="blk"><div className="label">Evidence</div><pre className="code wrap">{highlightAuto(f.evidence)}</pre></div>}
        {f.impact && <div className="blk"><div className="label">Why it matters</div><p>{f.impact}</p></div>}
        {f.recommendation && <div className="blk"><div className="label">What to do</div><p>{f.recommendation}</p></div>}
        {f.rule_id === 'DAX_UNUSED_MEASURE' && (
          <div className="notice warn"><TriangleAlert aria-hidden="true" /><span className="grow">Reports outside this project (thin reports, Excel pivot tables) can still use this measure. Check them before deleting it.</span></div>
        )}
        {f.suppressed && f.suppression_reason && <div className="notice"><EyeOff aria-hidden="true" /><span className="grow">Suppressed: {f.suppression_reason}</span></div>}
        {confirming ? (
          <div className="confirm">
            <span>Suppress <strong className="mono">{f.rule_id}</strong> for <strong className="mono">{f.location || 'this location'}</strong>? It is saved to the project's suppressions file and hidden from future scans.</span>
            <div className="actions">
              <button className="btn btn-primary" onClick={suppress} disabled={busy}>{busy ? 'Saving…' : 'Suppress finding'}</button>
              <button className="btn" onClick={() => setConfirming(false)} disabled={busy}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="actions">
            {FIXABLE_RULES.has(f.rule_id) && <button className="btn btn-primary" onClick={onOpenFixes}><Wrench aria-hidden="true" />Review fix</button>}
            {onOpenMeasure && <button className="btn" onClick={onOpenMeasure}><Sigma aria-hidden="true" />Open measure</button>}
            {onOpenPage && <button className="btn" onClick={onOpenPage}><FileStack aria-hidden="true" />Open page</button>}
            {!f.suppressed && (
              <button className="btn" onClick={() => setConfirming(true)} disabled={!canSuppress} title={canSuppress ? undefined : 'Suppressing needs the local engine (pbiscan studio)'}>
                <EyeOff aria-hidden="true" />Suppress…
              </button>
            )}
            <button className="btn btn-ghost" onClick={copyTask}><ClipboardCopy aria-hidden="true" />Copy as task</button>
          </div>
        )}
      </div>
    </div>
  );
};
