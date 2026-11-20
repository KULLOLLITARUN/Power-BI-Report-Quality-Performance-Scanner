import React, { useMemo, useState } from 'react';
import { KeyRound, Search, EyeOff } from 'lucide-react';
import type { AuditFinding, ScanResult } from '../types';
import { cardinalityLabel, classifyTables, findingTargets, isAutoDateTable, isBidirectional, relKey, type TableRole } from '../lib/model';
import { sortFindings, worstSeverity } from '../lib/severity';
import { ModelMap } from '../components/ModelMap';
import { SevMarker, SevTag } from '../components/ui';

const ROLE_LABEL: Record<TableRole, string> = { fact: 'Fact', dim: 'Dimension', date: 'Date', other: 'Unrelated' };
const ROLE_VAR: Record<TableRole, string> = { fact: 'fact', dim: 'dim', date: 'date', other: 'other' };

export const ModelScreen: React.FC<{
  scan: ScanResult; findings: AuditFinding[]; onOpenFinding: (f: AuditFinding) => void; onOpenMeasure: (name: string) => void;
}> = ({ scan, findings, onOpenFinding, onOpenMeasure }) => {
  const tables = useMemo(() => (scan.tables || []).filter((t) => !isAutoDateTable(t.name)), [scan.tables]);
  const roles = useMemo(() => classifyTables(tables, scan.relationships || []), [tables, scan.relationships]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<'all' | 'fact' | 'dim'>('all');
  const autoDate = useMemo(() => (scan.tables || []).filter((t) => isAutoDateTable(t.name)).length, [scan.tables]);
  const allRels = scan.relationships || [];

  const byTable = useMemo(() => {
    const m = new Map<string, AuditFinding[]>();
    for (const f of findings) for (const t of findingTargets(f, scan).tables) m.set(t, [...(m.get(t) ?? []), f]);
    return m;
  }, [findings, scan]);

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    const order: TableRole[] = ['fact', 'date', 'dim', 'other'];
    return tables
      .filter((t) => !q || t.name.toLowerCase().includes(q))
      .filter((t) => roleFilter === 'all' || roles.get(t.name) === roleFilter)
      .sort((a, b) => order.indexOf(roles.get(a.name)!) - order.indexOf(roles.get(b.name)!) || a.name.localeCompare(b.name));
  }, [tables, roles, query, roleFilter]);

  const table = tables.find((t) => t.name === selected) ?? null;
  const rels = (scan.relationships || []).filter((r) => table && (r.from_table === table.name || r.to_table === table.name));
  const tFindings = table ? sortFindings(byTable.get(table.name) ?? []) : [];
  const measures = (scan.measures || []).filter((m) => table && m.table === table.name);
  const focus = useMemo(() => (table ? { tables: [table.name], rels: rels.map(relKey) } : null), [table?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="page-head">
        <div>
          <p>Every table as a block: bigger blocks have more columns. Click a block or a row to see its columns, relationships and findings.</p>
        </div>
        <div className="actions">
          <span className="chip">{tables.length} table{tables.length === 1 ? '' : 's'}</span>
          <span className="chip">{allRels.length} relationship{allRels.length === 1 ? '' : 's'}</span>
          {autoDate > 0 && <span className="chip hot">{autoDate} hidden auto date table{autoDate === 1 ? '' : 's'}</span>}
        </div>
      </div>
      <div className="model-grid">
        <section className="panel" aria-label="Tables">
          <div className="panel-head">
            <h2>Tables</h2><span className="grow" />
            <div className="seg" role="group" aria-label="Role">
              {([['all', 'All'], ['fact', 'Fact'], ['dim', 'Dim']] as const).map(([k, label]) => (
                <button key={k} aria-pressed={roleFilter === k} onClick={() => setRoleFilter(k)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="filters">
            <label className="search"><Search aria-hidden="true" /><span className="sr-only">Search tables</span>
              <input type="search" placeholder="Search tables" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
          </div>
          <div className="side-list">
            <table className="tbl" aria-label="Tables">
              <thead><tr><th scope="col">Table</th><th scope="col">Role</th><th scope="col" className="r">Findings</th></tr></thead>
              <tbody>
                {list.map((t) => {
                  const role = roles.get(t.name)!;
                  const fs = byTable.get(t.name) ?? [];
                  return (
                    <tr key={t.name} className="pick" tabIndex={0} aria-selected={selected === t.name}
                        onClick={() => setSelected(selected === t.name ? null : t.name)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(selected === t.name ? null : t.name); } }}>
                      <td><span className="swatch" style={{ '--sw': `var(--t-${ROLE_VAR[role]})`, '--sw-edge': `var(--t-${ROLE_VAR[role]}-edge)` }} /> {t.name}{t.hidden && <EyeOff size={13} aria-label="hidden" style={{ marginLeft: 6, color: 'var(--muted)', verticalAlign: -2 }} />}</td>
                      <td className="muted nowrap">{ROLE_LABEL[role]}</td>
                      <td className="r">{fs.length === 0 ? <span className="muted">None</span> : <span className={`chip${fs.length >= 2 ? ' hot' : ''}`}>{fs.length}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!list.length && <div className="empty">No tables match.</div>}
          </div>
        </section>
        <ModelMap scan={scan} findings={findings} focus={focus} marked={selected} onTableClick={setSelected} title="Map" tall />
      </div>

      {table && (
        <section className="panel" aria-label={`${table.name} details`}>
          <div className="panel-head"><h2>{table.name}</h2><span className="chip">{ROLE_LABEL[roles.get(table.name)!]}</span>{table.hidden && <span className="chip">hidden</span>}</div>
          <div className="panel-body">
            <div className="stat-row">
              <div className="stat"><b>{table.column_count}</b><span>columns</span></div>
              <div className="stat"><b>{table.measures_count}</b><span>measures</span></div>
              <div className="stat"><b>{table.calc_cols_count}</b><span>calculated</span></div>
              <div className="stat"><b>{rels.length}</b><span>relationships</span></div>
            </div>
            {tFindings.length > 0 && (
              <div className="blk"><div className="label">Findings</div>
                {tFindings.map((f, i) => (
                  <button key={i} className="btn btn-quiet" style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left', height: 'auto', minHeight: 34, padding: '6px 10px' }} onClick={() => onOpenFinding(f)}>
                    <SevMarker sev={f.severity} /> <span style={{ flex: 1 }}>{f.title}</span> <SevTag sev={f.severity} />
                  </button>
                ))}
              </div>
            )}
            {measures.length > 0 && (
              <div className="blk"><div className="label">Measures</div>
                <div className="actions">{measures.map((m) => <button key={m.name} className="btn btn-sm" onClick={() => onOpenMeasure(m.name)}>{m.name}</button>)}</div>
              </div>
            )}
            {table.columns?.length > 0 && (
              <div className="blk"><div className="label">Columns{table.columns.length < table.column_count ? ` (first ${table.columns.length})` : ''}</div>
                <div className="table-wrap" style={{ maxHeight: 280, overflowY: 'auto' }}><table className="tbl">
                  <thead><tr><th>Name</th><th>Type</th><th /></tr></thead>
                  <tbody>{table.columns.map((c) => (
                    <tr key={c.name}>
                      <td>{c.name}</td>
                      <td className="muted">{c.data_type}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {c.in_relationship && <KeyRound size={13} aria-label="used in a relationship" style={{ color: 'var(--accent)' }} />}
                        {c.hidden && <EyeOff size={13} aria-label="hidden" style={{ marginLeft: 4, color: 'var(--muted)' }} />}
                      </td>
                    </tr>
                  ))}</tbody>
                </table></div>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="panel" aria-label="Relationships">
        <div className="panel-head"><h2>Relationships</h2><span className="grow" /><span className="muted small">{allRels.length} total{allRels.length && allRels.every((r) => !isBidirectional(r)) ? ', all single direction' : ''}</span></div>
        {allRels.length === 0 ? <div className="empty">This model has no relationships.</div> : (
          <div className="table-wrap"><table className="tbl rel-tbl" aria-label="Relationships">
            <thead><tr><th scope="col">From</th><th scope="col">To</th><th scope="col">Note</th></tr></thead>
            <tbody>{allRels.map((r) => {
              const [ca, cb] = cardinalityLabel(r);
              const auto = isAutoDateTable(r.from_table) || isAutoDateTable(r.to_table);
              const note = [auto ? null : `${ca}:${cb}`, isBidirectional(r) ? 'both directions' : null, r.is_active === false ? 'inactive' : null].filter(Boolean).join(', ');
              return (
                <tr key={relKey(r)} style={r.is_active === false ? { opacity: 0.7 } : undefined}>
                  <td className="mono" data-label="From">{r.from_table}[{r.from_column}]</td>
                  <td className="mono" data-label="To">{r.to_table}[{r.to_column}]</td>
                  <td>{auto && <span className="chip hot">Auto date/time</span>}{isBidirectional(r) && <span className="chip hot">Both directions</span>}{!auto && !isBidirectional(r) && <span className="muted">{note}</span>}</td>
                </tr>
              );
            })}</tbody>
          </table></div>
        )}
      </section>
    </>
  );
};
