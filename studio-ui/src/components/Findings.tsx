import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, ChevronLeft, ClipboardCopy, EyeOff, FileStack, Search, Sigma, TriangleAlert, Wrench } from 'lucide-react';
import type { AuditFinding } from '../types';
import { AREA_LABEL, sevMeta, type Severity } from '../lib/severity';
import { groupWhere, type FindingGroup } from '../lib/groups';
import { highlightAuto } from '../lib/dax';
import { animate } from '../lib/motion';
import { Confidence, SevMarker, copyText, useToast } from './ui';

// Rules `pbiscan fix` can patch (pbiscan/remediation/patchers).
export const FIXABLE_RULES = new Set(['MODEL_BIDIRECTIONAL', 'DAX_UNUSED_MEASURE', 'M_HARDCODED_DATA_SOURCE', 'MODEL_AUTO_DATETIME_BLOAT']);

export const findingKey = (f: AuditFinding) => `${f.rule_id}|${f.location ?? ''}|${f.evidence ?? ''}`;

interface ListProps {
  groups: FindingGroup[];          // already filtered and sorted
  shown: number;                   // findings across the groups
  total: number;
  selectedRule: string | null;
  onSelect: (g: FindingGroup) => void;
  query: string; onQuery: (q: string) => void;
  area: string; onArea: (a: string) => void;
  sev: Severity | null; onClearSev: () => void;
  table: string | null; onClearTable: () => void;
  suppressedCount: number; showSuppressed: boolean; onShowSuppressed: (v: boolean) => void;
}

const SevLabel: React.FC<{ sev: string }> = ({ sev }) => (
  <span className="sev-label" style={{ color: `var(${sevMeta(sev).token})` }}><SevMarker sev={sev} size={11} />{sevMeta(sev).label}</span>
);

export const FindingsList: React.FC<ListProps> = (p) => {
  const listRef = useRef<HTMLUListElement>(null);
  const firstRender = useRef(true);
  useEffect(() => {
    animate({
      targets: listRef.current?.querySelectorAll('.frow'),
      translateY: [6, 0], opacity: [0.25, 1],
      delay: (_: unknown, i: number) => (firstRender.current ? 120 : 0) + Math.min(i, 14) * 30,
      duration: 380, easing: 'easeOutCubic',
    });
    firstRender.current = false;
  }, [p.area, p.sev, p.table, p.showSuppressed]);

  const onKey = (e: React.KeyboardEvent<HTMLLIElement>, g: FindingGroup) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); p.onSelect(g); }
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
        <span className="muted small">{p.shown} of {p.total}, in {p.groups.length} group{p.groups.length === 1 ? '' : 's'}</span>
      </div>
      <div className="filters">
        <label className="search">
          <Search aria-hidden="true" />
          <span className="sr-only">Search findings</span>
          <input type="search" value={p.query} onChange={(e) => p.onQuery(e.target.value)} placeholder="Search findings" autoComplete="off" />
        </label>
        <div className="seg" role="group" aria-label="Area">
          {['all', 'model', 'dax', 'report'].map((a) => (
            <button key={a} aria-pressed={p.area === a} onClick={() => p.onArea(a)}>{a === 'all' ? 'All' : AREA_LABEL[a]}</button>
          ))}
        </div>
        {p.table && <span className="filter-chip">table: {p.table}<button onClick={p.onClearTable} aria-label="Clear table filter">×</button></span>}
        {p.sev && <span className="filter-chip">severity: {sevMeta(p.sev).label.toLowerCase()}<button onClick={p.onClearSev} aria-label="Clear severity filter">×</button></span>}
      </div>
      {p.groups.length === 0 ? (
        <div className="empty">
          <CheckCircle2 aria-hidden="true" />
          {p.total === 0 ? <><strong>No open findings</strong><span>This project passes every rule pbiscan checks.</span></>
            : <><strong>No findings match these filters</strong><span>Clear a filter to see the other {p.total}.</span></>}
        </div>
      ) : (
        <ul className="rows" role="listbox" aria-label="Findings list" ref={listRef}>
          {p.groups.map((g) => {
            const suppressed = g.members.every((m) => m.suppressed);
            return (
              <li key={g.rule_id} className={`frow${suppressed ? ' is-suppressed' : ''}`} role="option" tabIndex={0} aria-selected={p.selectedRule === g.rule_id}
                  onClick={() => p.onSelect(g)} onKeyDown={(e) => onKey(e, g)}>
                <SevLabel sev={g.severity} />
                <span className="frow-main">
                  <span className="t">{g.title}</span>
                  <span className="mono muted rid">{g.rule_id}</span>
                  <span className="s">{groupWhere(g)}{suppressed ? ' (suppressed)' : ''}</span>
                </span>
                <span className="frow-side">
                  <Confidence value={g.confidence} />
                  {g.fixable ? <span className="chip good">Fix ready</span> : <span className="chip">Manual</span>}
                </span>
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
  group: FindingGroup | null;
  /** The finding whose details are shown: the picked member, or the group's first. */
  finding: AuditFinding | null;
  /** True while a multi-finding group is shown as a whole (no single member picked). */
  wholeGroup: boolean;
  onPickMember: (f: AuditFinding | null) => void;
  canSuppress: boolean;
  onSuppress: (findings: AuditFinding[]) => Promise<void>;
  onOpenFixes: () => void;
  onOpenMeasure?: (() => void) | null;
  onOpenPage?: (() => void) | null;
  /** Extra rule-specific evidence, shown after the finding's own evidence. */
  evidence?: React.ReactNode;
}

export const FindingDetail: React.FC<DetailProps> = ({ group, finding: f, wholeGroup, onPickMember, canSuppress, onSuppress, onOpenFixes, onOpenMeasure, onOpenPage, evidence }) => {
  const toast = useToast();
  const ref = useRef<HTMLDivElement>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setConfirming(false);
    animate({ targets: ref.current?.children, translateY: [8, 0], opacity: [0.2, 1], delay: (_: unknown, i: number) => i * 40, duration: 360, easing: 'easeOutQuad' });
  }, [f, wholeGroup]);

  if (!f || !group) {
    return <div className="empty" style={{ padding: 28 }}><strong>Select a finding</strong><span>Its evidence, impact and fix appear here.</span></div>;
  }

  const targets = wholeGroup ? group.members.filter((m) => !m.suppressed) : f.suppressed ? [] : [f];
  const count = group.members.length;
  const copyTask = async () => {
    const ok = await copyText(`${f.rule_id}: ${f.title}\n${wholeGroup ? groupWhere(group, 5) : f.location ?? ''}\n\n${f.issue}\n\nFix: ${f.recommendation}`);
    toast(ok ? 'Copied the finding as a task.' : 'Copying is blocked here. Select the text instead.', ok ? 'info' : 'error');
  };
  const suppress = async () => {
    setBusy(true);
    try { await onSuppress(targets); setConfirming(false); } finally { setBusy(false); }
  };

  return (
    <div ref={ref}>
      <div className="detail-head">
        <div className="detail-meta">
          <SevLabel sev={wholeGroup ? group.severity : f.severity} />
          <span className="muted">{AREA_LABEL[f.category] ?? f.category}</span>
          <Confidence value={wholeGroup ? group.confidence : f.confidence ?? 0} label />
          {f.suppressed && <span className="chip">suppressed</span>}
        </div>
        <h3>{f.title}</h3>
        <span className="mono muted">{f.rule_id}</span>
      </div>
      <div className="detail-body">
        {!wholeGroup && count > 1 && (
          <button className="btn btn-quiet btn-sm back-all" onClick={() => onPickMember(null)}><ChevronLeft aria-hidden="true" />All {count} findings of this rule</button>
        )}
        <dl className="kv">
          <dt>Found in</dt><dd>{wholeGroup ? groupWhere(group, 3) : f.location || 'The whole model'}</dd>
          {f.issue && <><dt>What</dt><dd>{f.issue}</dd></>}
          {f.impact && <><dt>Why it matters</dt><dd>{f.impact}</dd></>}
          {f.recommendation && <><dt>Suggested fix</dt><dd>{f.recommendation}</dd></>}
        </dl>
        {f.evidence && <div className="blk"><div className="label">Evidence</div><pre className="code wrap">{highlightAuto(f.evidence)}</pre></div>}
        {evidence}
        {wholeGroup && (
          <div className="blk">
            <div className="label">Affected ({count})</div>
            <ul className="affected">
              {group.members.map((m) => (
                <li key={findingKey(m)}><button className="btn btn-quiet btn-sm" onClick={() => onPickMember(m)}>{m.location || m.title}</button></li>
              ))}
            </ul>
          </div>
        )}
        {f.rule_id === 'DAX_UNUSED_MEASURE' && (
          <div className="notice warn"><TriangleAlert aria-hidden="true" /><span className="grow"><strong>Check other reports before you delete it.</strong> Reports outside this project (thin reports, Excel pivot tables) can still use this measure.</span></div>
        )}
        {f.suppressed && f.suppression_reason && <div className="notice"><EyeOff aria-hidden="true" /><span className="grow">Suppressed: {f.suppression_reason}</span></div>}
        {confirming ? (
          <div className="confirm">
            <span>
              {targets.length > 1
                ? <>Suppress all <strong>{targets.length}</strong> findings of <strong className="mono">{f.rule_id}</strong>? </>
                : <>Suppress <strong className="mono">{f.rule_id}</strong> for <strong className="mono">{f.location || 'this location'}</strong>? </>}
              {targets.length > 1 ? 'They are' : 'It is'} saved to the project's suppressions file and hidden from future scans.
            </span>
            <div className="actions">
              <button className="btn btn-primary" onClick={suppress} disabled={busy}>{busy ? 'Saving…' : targets.length > 1 ? `Suppress ${targets.length} findings` : 'Suppress finding'}</button>
              <button className="btn" onClick={() => setConfirming(false)} disabled={busy}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="actions">
            {FIXABLE_RULES.has(f.rule_id) && <button className="btn btn-primary" onClick={onOpenFixes}><Wrench aria-hidden="true" />Review fix</button>}
            {onOpenMeasure && <button className="btn" onClick={onOpenMeasure}><Sigma aria-hidden="true" />Open measure</button>}
            {onOpenPage && <button className="btn" onClick={onOpenPage}><FileStack aria-hidden="true" />Open page</button>}
            {targets.length > 0 && (
              <button className="btn" onClick={() => setConfirming(true)} disabled={!canSuppress} title={canSuppress ? undefined : 'Suppressing needs the local engine (pbiscan studio)'}>
                <EyeOff aria-hidden="true" />Suppress…
              </button>
            )}
            <button className="btn btn-quiet" onClick={copyTask}><ClipboardCopy aria-hidden="true" />Copy as task</button>
          </div>
        )}
      </div>
    </div>
  );
};
