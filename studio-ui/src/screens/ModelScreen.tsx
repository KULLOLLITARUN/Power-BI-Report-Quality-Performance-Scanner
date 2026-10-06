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
      .sort((a, b) => order.indexOf(roles.get(a.name)!) - order.indexOf(roles.get(b.name)!) || a.name.localeCompare(b.name));
  }, [tables, roles, query]);

  const table = tables.find((t) => t.name === selected) ?? null;
  const rels = (scan.relationships || []).filter((r) => table && (r.from_table === table.name || r.to_table === table.name));
  const tFindings = table ? sortFindings(byTable.get(table.name) ?? []) : [];
  const measures = (scan.measures || []).filter((m) => table && m.table === table.name);
  const focus = useMemo(() => (table ? { tables: [table.name], rels: rels.map(relKey) } : null), [table?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Model</h2>
          <p>Every table as a block: bigger blocks have more columns. Click a block or a row to see its columns, relationships and findings.</p>
        </div>
      </div>
      <div className="split wide-side">
        <ModelMap scan={scan} findings={findings} focus={focus} marked={selected} onTableClick={setSelected} title="Star schema" tall />
        <div style={{ display: 'grid', gap: 14, minWidth: 0 }}>
          <section className="panel" aria-label="Tables">
            <div className="filters">
              <label className="search"><Search aria-hidden="true" /><span className="sr-only">Search tables</span>
                <input type="search" placeholder="Search tables" value={query} onChange={(e) => setQuery(e.target.value)} />
              </label>
            </div>
            <div className="side-list" role="listbox" aria-label="Tables" style={{ maxHeight: table ? 260 : undefined }}>
              {list.map((t) => {
                const role = roles.get(t.name)!;
                const fs = byTable.get(t.name) ?? [];
                const worst = worstSeverity(fs.map((f) => f.severity));
                return (
                  <div key={t.name} className="item" role="option" tabIndex={0} aria-selected={selected === t.name}
                       onClick={() => setSelected(selected === t.name ? null : t.name)}
                       onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(t.name); } }}>
                    <span className="swatch" style={{ ['--sw' as any]: `var(--t-${ROLE_VAR[role]})`, ['--sw-edge' as any]: `var(--t-${ROLE_VAR[role]}-edge)` }} />
                    <span className="nm">{t.name}</span>
                    <span className="flags">{t.hidden && <EyeOff size={13} aria-label="hidden" />}{worst && <SevMarker sev={worst} size={11} />}</span>
                    <span className="sub">{ROLE_LABEL[role]} · {t.column_count} cols · {t.measures_count} measures{t.calc_cols_count ? ` · ${t.calc_cols_count} calculated` : ''}</span>
                  </div>
                );
              })}
              {!list.length && <div className="empty">No tables match “{query}”.</div>}
            </div>
          </section>

          {table && (
            <section className="panel" aria-label={`${table.name} details`}>
              <div className="panel-head"><h3>{table.name}</h3><span className="chip">{ROLE_LABEL[roles.get(table.name)!]}</span>{table.hidden && <span className="chip">hidden</span>}</div>
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
                      <button key={i} className="btn btn-ghost" style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => onOpenFinding(f)}>
                        <SevMarker sev={f.severity} /> <span style={{ flex: 1 }}>{f.title}</span> <SevTag sev={f.severity} />
                      </button>
                    ))}
                  </div>
                )}
                {rels.length > 0 && (
                  <div className="blk"><div className="label">Relationships</div>
                    <div className="table-wrap"><table className="table">
                      <thead><tr><th>From</th><th>To</th><th>Card.</th><th>Filter</th></tr></thead>
                      <tbody>{rels.map((r) => {
                        const [a, b] = cardinalityLabel(r);
                        return (
                          <tr key={relKey(r)} style={r.is_active === false ? { opacity: 0.6 } : undefined}>
                            <td className="mono">{r.from_table}[{r.from_column}]</td>
                            <td className="mono">{r.to_table}[{r.to_column}]</td>
                            <td className="mono">{a}:{b}</td>
                            <td className="mono" style={isBidirectional(r) ? { color: 'var(--sev-warning)' } : undefined}>{isBidirectional(r) ? 'both' : 'single'}{r.is_active === false ? ' · inactive' : ''}</td>
                          </tr>
                        );
                      })}</tbody>
                    </table></div>
                  </div>
                )}
                {measures.length > 0 && (
                  <div className="blk"><div className="label">Measures</div>
                    <div className="actions">{measures.map((m) => <button key={m.name} className="btn btn-sm" onClick={() => onOpenMeasure(m.name)}>{m.name}</button>)}</div>
                  </div>
                )}
                {table.columns?.length > 0 && (
                  <div className="blk"><div className="label">Columns{table.columns.length < table.column_count ? ` (first ${table.columns.length})` : ''}</div>
                    <div className="table-wrap" style={{ maxHeight: 280, overflowY: 'auto' }}><table className="table">
                      <thead><tr><th>Name</th><th>Type</th><th /></tr></thead>
                      <tbody>{table.columns.map((c) => (
                        <tr key={c.name}>
                          <td>{c.name}</td>
                          <td className="mono muted">{c.data_type}</td>
                          <td style={{ whiteSpace: 'nowrap' }}>
                            {c.in_relationship && <KeyRound size={13} aria-label="used in a relationship" style={{ color: 'var(--accent)' }} />}
                            {c.hidden && <EyeOff size={13} aria-label="hidden" style={{ marginLeft: 4, color: 'var(--ink-3)' }} />}
                          </td>
                        </tr>
                      ))}</tbody>
                    </table></div>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </>
  );
};
