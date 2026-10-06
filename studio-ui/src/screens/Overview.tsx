import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { TriangleAlert } from 'lucide-react';
import type { AuditFinding, ScanResult } from '../types';
import type { Severity } from '../lib/severity';
import { sortFindings } from '../lib/severity';
import { findingTargets } from '../lib/model';
import type { HistoryPoint } from '../lib/history';
import { Ledger } from '../components/Ledger';
import { FindingDetail, FindingsList, findingKey } from '../components/Findings';
import { ModelMap, type MapFocus } from '../components/ModelMap';
import { Sheet, useMobile } from '../components/ui';

interface Props {
  scan: ScanResult;
  history: HistoryPoint[];
  canSuppress: boolean;
  onSuppress: (f: AuditFinding) => Promise<void>;
  onOpenFixes: () => void;
  onOpenMeasure: (name: string) => void;
  onOpenPage: (name: string) => void;
}

export const Overview: React.FC<Props> = ({ scan, history, canSuppress, onSuppress, onOpenFixes, onOpenMeasure, onOpenPage }) => {
  const mobile = useMobile();
  const all = scan.findings || [];
  const open = useMemo(() => all.filter((f) => !f.suppressed), [all]);
  const suppressedCount = all.length - open.length;

  const [query, setQuery] = useState('');
  const [area, setArea] = useState('all');
  const [sev, setSev] = useState<Severity | null>(null);
  const [table, setTable] = useState<string | null>(null);
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sortFindings((showSuppressed ? all : open).filter((f) => {
      if (area !== 'all' && f.category !== area) return false;
      if (sev && f.severity !== sev) return false;
      if (table && !findingTargets(f, scan).tables.includes(table)) return false;
      if (q && !`${f.rule_id} ${f.title} ${f.location ?? ''} ${f.evidence ?? ''}`.toLowerCase().includes(q)) return false;
      return true;
    }));
  }, [all, open, showSuppressed, area, sev, table, query, scan]);

  // Keep a valid selection: first visible finding unless the user picked one that is still visible.
  useEffect(() => {
    if (!filtered.length) return;
    if (!selectedKey || !all.some((f) => findingKey(f) === selectedKey)) setSelectedKey(findingKey(filtered[0]));
  }, [filtered, all, selectedKey]);

  const selected = all.find((f) => findingKey(f) === selectedKey) ?? null;
  const targets = selected ? findingTargets(selected, scan) : null;

  const focus: MapFocus | null = useMemo(() => {
    if (!selected || !targets) return null;
    if (targets.tables.length) return { tables: targets.tables, rels: targets.rels };
    return {
      tables: [], rels: [],
      caption: selected.category === 'report' ? 'This finding is on a report page, not in the model.' : 'This finding is a model-wide setting, so no single table is highlighted.',
    };
  }, [selected, targets?.tables.join('|'), targets?.rels.join('|')]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = useCallback((f: AuditFinding) => {
    setSelectedKey(findingKey(f));
    setSheetOpen(true);
  }, []);
  const closeSheet = useCallback(() => setSheetOpen(false), []);

  return (
    <>
      {scan.warnings?.length > 0 && (
        <div className="notice warn">
          <TriangleAlert aria-hidden="true" />
          <div className="grow">
            <strong>{scan.warnings.length === 1 ? 'One file' : `${scan.warnings.length} files`} could not be read fully.</strong>{' '}
            Findings that depend on them, such as unused measures, may be incomplete.
            <details className="disclosure" style={{ marginTop: 6 }}><summary className="mono" style={{ fontSize: 12 }}>Show details</summary>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{scan.warnings.map((w, i) => <li key={i} className="mono" style={{ fontSize: 12 }}>{w}</li>)}</ul>
            </details>
          </div>
        </div>
      )}
      <Ledger scores={scan.scores} findings={open} suppressedCount={suppressedCount} history={history} sev={sev} onSev={setSev} />
      <div className="work">
        <FindingsList
          findings={filtered} total={showSuppressed ? all.length : open.length}
          selected={selectedKey} onSelect={select}
          query={query} onQuery={setQuery} area={area} onArea={setArea}
          sev={sev} onClearSev={() => setSev(null)} table={table} onClearTable={() => setTable(null)}
          suppressedCount={suppressedCount} showSuppressed={showSuppressed} onShowSuppressed={setShowSuppressed}
        />
        <aside className="inspector">
          <ModelMap scan={scan} findings={open} focus={focus} marked={table} onTableClick={setTable} />
          <Sheet open={sheetOpen && mobile} onClose={closeSheet} label="Finding details" className="panel panel-raised">
            <FindingDetail
              finding={selected}
              canSuppress={canSuppress}
              onSuppress={async (f) => { await onSuppress(f); setSheetOpen(false); }}
              onOpenFixes={onOpenFixes}
              onOpenMeasure={targets?.measure ? () => onOpenMeasure(targets.measure!.name) : null}
              onOpenPage={targets?.page ? () => onOpenPage(targets.page!) : null}
            />
          </Sheet>
        </aside>
      </div>
    </>
  );
};
