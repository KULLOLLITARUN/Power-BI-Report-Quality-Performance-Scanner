import React, { useEffect, useMemo, useState } from 'react';
import { ClipboardCopy, Search, TriangleAlert } from 'lucide-react';
import type { AuditFinding, ScanResult } from '../types';
import { DaxCode } from '../lib/dax';
import { findingTargets, measureUsage } from '../lib/model';
import { sortFindings, worstSeverity } from '../lib/severity';
import { SevMarker, SevTag, copyText, useToast } from '../components/ui';

type Item = { kind: 'measure' | 'column'; name: string; table: string; expression: string; hidden?: boolean; data_type?: string };

export const MeasuresScreen: React.FC<{
  scan: ScanResult; findings: AuditFinding[]; initial: string | null; onOpenFinding: (f: AuditFinding) => void; onOpenPage: (name: string) => void;
}> = ({ scan, findings, initial, onOpenFinding, onOpenPage }) => {
  const toast = useToast();
  const [kind, setKind] = useState<'measure' | 'column'>('measure');
  const [query, setQuery] = useState('');
  const [table, setTable] = useState('all');
  const [flagged, setFlagged] = useState(false);
  const [selected, setSelected] = useState<string | null>(initial);

  useEffect(() => { if (initial) { setSelected(initial); setKind('measure'); } }, [initial]);

  const items: Item[] = useMemo(() => [
    ...(scan.measures || []).map((m) => ({ kind: 'measure' as const, ...m })),
    ...(scan.calculated_columns || []).map((c) => ({ kind: 'column' as const, ...c })),
  ], [scan.measures, scan.calculated_columns]);

  const findingsFor = useMemo(() => {
    const m = new Map<string, AuditFinding[]>();
    for (const f of findings) {
      const t = findingTargets(f, scan);
      if (t.measure) m.set(`${t.measure.table}|${t.measure.name}`.toLowerCase(), [...(m.get(`${t.measure.table}|${t.measure.name}`.toLowerCase()) ?? []), f]);
    }
    return m;
  }, [findings, scan]);
  const keyOf = (it: Item) => `${it.table}|${it.name}`.toLowerCase();

  const tables = useMemo(() => [...new Set(items.filter((i) => i.kind === kind).map((i) => i.table))].sort(), [items, kind]);
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items
      .filter((i) => i.kind === kind)
      .filter((i) => table === 'all' || i.table === table)
      .filter((i) => !q || i.name.toLowerCase().includes(q) || i.expression.toLowerCase().includes(q))
      .filter((i) => !flagged || findingsFor.has(keyOf(i)))
      .sort((a, b) => a.table.localeCompare(b.table) || a.name.localeCompare(b.name));
  }, [items, kind, table, query, flagged, findingsFor]);

  const current = items.find((i) => i.name === selected && i.kind === kind) ?? list[0] ?? null;
  const curFindings = current ? sortFindings(findingsFor.get(keyOf(current)) ?? []) : [];
  const usage = current && current.kind === 'measure' ? measureUsage(current as any, scan.pages || []) : [];
  const node = current ? scan.dax_graph?.nodes?.find((n) => n.name.toLowerCase() === current.name.toLowerCase()) : undefined;
  const hasVisualData = (scan.pages || []).some((p) => p.visuals);

  const copy = async () => {
    if (!current) return;
    const ok = await copyText(current.expression);
    toast(ok ? `Copied the DAX for ${current.name}.` : 'Copying is blocked here. Select the text instead.', ok ? 'info' : 'error');
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Measures</h2>
          <p>{(scan.measures || []).length} measures and {(scan.calculated_columns || []).length} calculated columns. Flagged items carry a severity mark.</p>
        </div>
      </div>
      <div className="split">
        <section className="panel" aria-label="Measure list">
          <div className="filters" style={{ display: 'grid', gap: 8 }}>
            <div className="seg" role="group" aria-label="Kind">
              <button aria-pressed={kind === 'measure'} onClick={() => { setKind('measure'); setTable('all'); }}>Measures ({(scan.measures || []).length})</button>
              <button aria-pressed={kind === 'column'} onClick={() => { setKind('column'); setTable('all'); }}>Calculated columns ({(scan.calculated_columns || []).length})</button>
            </div>
            <label className="search"><Search aria-hidden="true" /><span className="sr-only">Search</span>
              <input type="search" placeholder="Search name or DAX" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <label className="sr-only" htmlFor="measure-table">Table</label>
              <select id="measure-table" className="select" value={table} onChange={(e) => setTable(e.target.value)} style={{ flex: 1 }}>
                <option value="all">All tables</option>
                {tables.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <label className="check"><input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} />Flagged only</label>
            </div>
          </div>
          <div className="side-list" role="listbox" aria-label={kind === 'measure' ? 'Measures' : 'Calculated columns'}>
            {list.map((it) => {
              const fs = findingsFor.get(keyOf(it)) ?? [];
              const worst = worstSeverity(fs.map((f) => f.severity));
              return (
                <div key={keyOf(it)} className="item" role="option" tabIndex={0} aria-selected={current?.name === it.name && current?.table === it.table}
                     onClick={() => setSelected(it.name)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(it.name); } }}>
                  <span>{worst ? <SevMarker sev={worst} size={11} /> : null}</span>
                  <span className="nm">{it.name}</span>
                  <span className="flags">{it.hidden && <span className="chip">hidden</span>}</span>
                  <span className="sub">{it.table}</span>
                </div>
              );
            })}
            {!list.length && <div className="empty">Nothing matches these filters.</div>}
          </div>
        </section>

        {current ? (
          <section className="panel" aria-label={`${current.name} details`}>
            <div className="panel-head">
              <h3>{current.name}</h3>
              <span className="chip">{current.table}</span>
              {current.kind === 'column' && current.data_type && <span className="chip">{current.data_type}</span>}
              <span className="spacer" />
              <button className="btn btn-sm" onClick={copy}><ClipboardCopy aria-hidden="true" />Copy DAX</button>
            </div>
            <div className="panel-body">
              <DaxCode code={current.expression} lines />
              {curFindings.length > 0 && (
                <div className="blk"><div className="label">Findings</div>
                  {curFindings.map((f, i) => (
                    <button key={i} className="btn btn-ghost" style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => onOpenFinding(f)}>
                      <SevMarker sev={f.severity} /><span style={{ flex: 1 }}>{f.title}</span><SevTag sev={f.severity} />
                    </button>
                  ))}
                </div>
              )}
              {current.kind === 'measure' && (
                <div className="grid-2">
                  <div className="blk">
                    <div className="label">Used on report pages</div>
                    {!hasVisualData ? <p className="muted" style={{ fontSize: 13 }}>This scan has no visual-level data. Rescan with this version of pbiscan to see it.</p>
                      : usage.length ? (
                        <div className="actions">{usage.map((u) => <button key={u.page.name} className="btn btn-sm" onClick={() => onOpenPage(u.page.name)}>{u.page.display_name} · {u.visuals}</button>)}</div>
                      ) : <p className="muted" style={{ fontSize: 13 }}>No visual places it directly. Other measures, calculation groups or filters can still use it.</p>}
                  </div>
                  <div className="blk">
                    <div className="label">DAX dependencies</div>
                    {node ? (
                      <dl className="kv">
                        <dt>uses</dt><dd className="mono" style={{ fontSize: 12 }}>{node.references.length ? node.references.join(', ') : 'no other measures'}</dd>
                        <dt>used by</dt><dd className="mono" style={{ fontSize: 12 }}>{node.referenced_by.length ? node.referenced_by.join(', ') : 'no other measures'}</dd>
                      </dl>
                    ) : <p className="muted" style={{ fontSize: 13 }}>Dependency data comes from the local engine.</p>}
                  </div>
                </div>
              )}
              {curFindings.some((f) => f.rule_id === 'DAX_UNUSED_MEASURE') && (
                <div className="notice warn"><TriangleAlert aria-hidden="true" /><span className="grow">Thin reports and Excel files outside this project are not scanned. Check them before deleting this measure.</span></div>
              )}
            </div>
          </section>
        ) : (
          <div className="panel empty"><strong>No {kind === 'measure' ? 'measures' : 'calculated columns'}</strong><span>This project defines none.</span></div>
        )}
      </div>
    </>
  );
};
