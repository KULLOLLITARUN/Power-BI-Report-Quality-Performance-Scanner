import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { TriangleAlert, Wrench } from 'lucide-react';
import type { AuditFinding, ScanResult } from '../types';
import type { Severity } from '../lib/severity';
import { sortFindings } from '../lib/severity';
import { findingTargets } from '../lib/model';
import type { HistoryPoint } from '../lib/history';
import { Ledger } from '../components/Ledger';
import { FIXABLE_RULES, FindingDetail, FindingsList, findingKey } from '../components/Findings';
import { groupByRule } from '../lib/groups';
import { ModelMap, type MapFocus } from '../components/ModelMap';
import { Sheet, useMobile } from '../components/ui';
import { UsageEvidence } from '../components/UsageEvidence';

interface Props {
  scan: ScanResult;
  history: HistoryPoint[];
  canSuppress: boolean;
  onSuppress: (findings: AuditFinding[]) => Promise<void>;
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

  const groups = useMemo(() => groupByRule(filtered, (r) => FIXABLE_RULES.has(r)), [filtered]);
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const [memberKey, setMemberKey] = useState<string | null>(null);

  // Keep a valid selection: the first group unless the user picked one that is still visible.
  useEffect(() => {
    if (!groups.length) return;
    if (!selectedRule || !groups.some((g) => g.rule_id === selectedRule)) { setSelectedRule(groups[0].rule_id); setMemberKey(null); }
  }, [groups, selectedRule]);

  const group = groups.find((g) => g.rule_id === selectedRule) ?? null;
  const member = group && memberKey ? group.members.find((m) => findingKey(m) === memberKey) ?? null : null;
  const wholeGroup = !!group && !member && group.members.length > 1;
  const selected = member ?? group?.members[0] ?? null;
  const targets = selected ? findingTargets(selected, scan) : null;

  // A whole group highlights every table its findings touch; one finding highlights its own.
  const focus: MapFocus | null = useMemo(() => {
    if (!group || !selected || !targets) return null;
    const list = wholeGroup ? group.members : [selected];
    const tables = [...new Set(list.flatMap((f) => findingTargets(f, scan).tables))];
    const rels = [...new Set(list.flatMap((f) => findingTargets(f, scan).rels))];
    if (tables.length) return { tables, rels };
    return {
      tables: [], rels: [],
      caption: selected.category === 'report' ? 'This finding is on a report page, not in the model.' : 'This finding is a model-wide setting, so no single table is highlighted.',
    };
  }, [group, selected, wholeGroup, scan]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = useCallback((g: { rule_id: string }) => {
    setSelectedRule(g.rule_id);
    setMemberKey(null);
    setSheetOpen(true);
  }, []);
  const closeSheet = useCallback(() => setSheetOpen(false), []);
  const fixable = useMemo(() => open.filter((f) => FIXABLE_RULES.has(f.rule_id)), [open]);
  const fixableRules = new Set(fixable.map((f) => f.rule_id)).size;

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
      {fixable.length > 0 && (
        <button className="fixbar" onClick={onOpenFixes}>
          <Wrench aria-hidden="true" />
          <span className="fixbar-t">{fixableRules === 1 ? '1 fix is ready to review' : `${fixableRules} fixes are ready to review`}</span>
          <span className="muted fixbar-s">They resolve {fixable.length} finding{fixable.length === 1 ? '' : 's'}. Every change is backed up first.</span>
          <span className="grow" />
          <span className="btn btn-primary">Review fixes</span>
        </button>
      )}
      <div className="work">
        <FindingsList
          groups={groups} shown={filtered.length} total={showSuppressed ? all.length : open.length}
          selectedRule={selectedRule} onSelect={select}
          query={query} onQuery={setQuery} area={area} onArea={setArea}
          sev={sev} onClearSev={() => setSev(null)} table={table} onClearTable={() => setTable(null)}
          suppressedCount={suppressedCount} showSuppressed={showSuppressed} onShowSuppressed={setShowSuppressed}
        />
        <aside className="inspector">
          <ModelMap scan={scan} findings={open} focus={focus} marked={table} onTableClick={setTable} />
          <Sheet open={sheetOpen && mobile} onClose={closeSheet} label="Finding details" className="panel panel-raised">
            <FindingDetail
              group={group} finding={selected} wholeGroup={wholeGroup} onPickMember={(f) => setMemberKey(f ? findingKey(f) : null)}
              canSuppress={canSuppress}
              onSuppress={async (list) => { await onSuppress(list); setSheetOpen(false); }}
              onOpenFixes={onOpenFixes}
              onOpenMeasure={targets?.measure ? () => onOpenMeasure(targets.measure!.name) : null}
              onOpenPage={targets?.page ? () => onOpenPage(targets.page!) : null}
              evidence={!wholeGroup && selected?.rule_id === 'DAX_UNUSED_MEASURE' && targets?.measure ? <UsageEvidence name={targets.measure.name} scan={scan} /> : null}
            />
          </Sheet>
        </aside>
      </div>
    </>
  );
};
