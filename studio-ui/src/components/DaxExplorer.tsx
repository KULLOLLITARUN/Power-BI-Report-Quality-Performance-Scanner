import React, { useState } from 'react';
import { MeasureInfo, CalculatedColumnInfo, AuditFinding } from '../types';
import { highlightDax } from '../utils/daxHighlighter';
import { 
  Code2, 
  Search, 
  Copy, 
  Check, 
  Calculator,
  Columns,
  Sparkles
} from 'lucide-react';

interface DaxExplorerProps {
  measures: MeasureInfo[];
  calcCols: CalculatedColumnInfo[];
  findings: AuditFinding[];
}

export const DaxExplorer: React.FC<DaxExplorerProps> = ({
  measures,
  calcCols,
  findings,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTable, setSelectedTable] = useState('all');
  const [selectedItem, setSelectedItem] = useState<MeasureInfo | CalculatedColumnInfo | null>(
    measures[0] || calcCols[0] || null
  );
  const [activeTab, setActiveTab] = useState<'measures' | 'calcCols'>('measures');
  const [copied, setCopied] = useState(false);

  // Extract unique table names
  const tableNames = Array.from(
    new Set([...measures.map((m) => m.table), ...calcCols.map((c) => c.table)])
  ).sort();

  // Find duplicates or unused findings related to DAX
  const duplicateFindings = findings.filter((f) => f.rule_id === 'DAX_DUPLICATE_MEASURE');
  const unusedFindings = findings.filter((f) => f.rule_id === 'DAX_UNUSED_MEASURE');

  const filteredMeasures = measures.filter((m) => {
    if (selectedTable !== 'all' && m.table.toLowerCase() !== selectedTable.toLowerCase()) {
      return false;
    }
    if (searchQuery.trim()) {
      return (
        m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.expression.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    return true;
  });

  const filteredCalcCols = calcCols.filter((c) => {
    if (selectedTable !== 'all' && c.table.toLowerCase() !== selectedTable.toLowerCase()) {
      return false;
    }
    if (searchQuery.trim()) {
      return (
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.expression.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    return true;
  });

  const isDuplicate = (name: string) => {
    return duplicateFindings.some((f) => f.evidence.includes(name) || f.location?.includes(name));
  };

  const isUnused = (name: string) => {
    return unusedFindings.some((f) => f.evidence.includes(name) || f.location?.includes(name));
  };

  const handleCopy = () => {
    if (selectedItem?.expression) {
      navigator.clipboard.writeText(selectedItem.expression);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col md:flex-row gap-4 h-[calc(100vh-8.5rem)]">
      {/* Left Sidebar: Master List */}
      <div 
        className="w-full md:w-80 border rounded p-3 flex flex-col justify-between shrink-0 overflow-hidden"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="space-y-2.5 flex-1 flex flex-col min-h-0">
          {/* Tab switch: Measures vs Calc Columns */}
          <div 
            className="grid grid-cols-2 gap-1 p-1 rounded border text-xs font-mono"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
            }}
          >
            <button
              onClick={() => {
                setActiveTab('measures');
                if (filteredMeasures.length > 0) setSelectedItem(filteredMeasures[0]);
              }}
              className="py-1.5 rounded transition flex items-center justify-center gap-1.5 border"
              style={{
                backgroundColor: activeTab === 'measures' ? 'var(--accent-muted)' : 'transparent',
                borderColor: activeTab === 'measures' ? 'var(--accent)' : 'transparent',
                color: activeTab === 'measures' ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'measures' ? 'bold' : 'normal',
              }}
            >
              <Calculator className="w-3.5 h-3.5" />
              <span>Measures ({measures.length})</span>
            </button>
            <button
              onClick={() => {
                setActiveTab('calcCols');
                if (filteredCalcCols.length > 0) setSelectedItem(filteredCalcCols[0]);
              }}
              className="py-1.5 rounded transition flex items-center justify-center gap-1.5 border"
              style={{
                backgroundColor: activeTab === 'calcCols' ? 'var(--accent-muted)' : 'transparent',
                borderColor: activeTab === 'calcCols' ? 'var(--accent)' : 'transparent',
                color: activeTab === 'calcCols' ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'calcCols' ? 'bold' : 'normal',
              }}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Calc Cols ({calcCols.length})</span>
            </button>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Filter by name or formula..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
              style={{
                backgroundColor: 'var(--bg-canvas)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          {/* Table filter dropdown */}
          <select
            value={selectedTable}
            onChange={(e) => setSelectedTable(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-primary)',
            }}
          >
            <option value="all">All Tables ({tableNames.length})</option>
            {tableNames.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          {/* Item List */}
          <div className="flex-1 overflow-y-auto space-y-1 pr-1 min-h-0">
            {activeTab === 'measures' ? (
              filteredMeasures.length > 0 ? (
                filteredMeasures.map((m) => {
                  const isSelected = selectedItem?.name === m.name && selectedItem?.table === m.table;
                  const duplicate = isDuplicate(m.name);
                  const unused = isUnused(m.name);

                  return (
                    <div
                      key={`${m.table}-${m.name}`}
                      onClick={() => setSelectedItem(m)}
                      className="p-2 rounded cursor-pointer transition border text-xs flex items-center justify-between font-mono"
                      style={{
                        backgroundColor: isSelected ? 'var(--accent-muted)' : 'var(--bg-canvas)',
                        borderColor: isSelected ? 'var(--accent)' : 'var(--border-hairline)',
                        color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                      }}
                    >
                      <div className="min-w-0">
                        <div className="font-semibold truncate">{m.name}</div>
                        <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>{m.table}</div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        {duplicate && (
                          <span 
                            className="text-[9px] font-mono px-1 py-0.2 rounded border font-bold"
                            style={{
                              backgroundColor: 'var(--severity-warning-bg)',
                              borderColor: 'var(--severity-warning-border)',
                              color: 'var(--severity-warning)',
                            }}
                          >
                            duplicate
                          </span>
                        )}
                        {unused && (
                          <span 
                            className="text-[9px] font-mono px-1 py-0.2 rounded border font-bold"
                            style={{
                              backgroundColor: 'var(--severity-advisory-bg)',
                              borderColor: 'var(--severity-advisory-border)',
                              color: 'var(--severity-advisory)',
                            }}
                          >
                            unused
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                  No matching measures
                </div>
              )
            ) : filteredCalcCols.length > 0 ? (
              filteredCalcCols.map((c) => {
                const isSelected = selectedItem?.name === c.name && selectedItem?.table === c.table;

                return (
                  <div
                    key={`${c.table}-${c.name}`}
                    onClick={() => setSelectedItem(c)}
                    className="p-2 rounded cursor-pointer transition border text-xs flex items-center justify-between font-mono"
                    style={{
                      backgroundColor: isSelected ? 'var(--accent-muted)' : 'var(--bg-canvas)',
                      borderColor: isSelected ? 'var(--accent)' : 'var(--border-hairline)',
                      color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                    }}
                  >
                    <div className="min-w-0">
                      <div className="font-semibold truncate">{c.name}</div>
                      <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>{c.table}</div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                No calculated columns found
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right Detail: Code Viewer & Diagnostics */}
      <div 
        className="flex-1 border rounded p-4 flex flex-col justify-between overflow-hidden"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        {selectedItem ? (
          <div className="flex-1 flex flex-col min-h-0 space-y-3">
            {/* Header info */}
            <div 
              className="pb-3 border-b flex items-start justify-between gap-4"
              style={{ borderColor: 'var(--border-hairline)' }}
            >
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                    {selectedItem.name}
                  </h3>
                  <span 
                    className="text-[10px] font-mono font-medium px-2 py-0.5 rounded border"
                    style={{
                      backgroundColor: 'var(--bg-canvas)',
                      borderColor: 'var(--border-strong)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {selectedItem.table}
                  </span>
                </div>
                {(selectedItem as any).description && (
                  <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                    {(selectedItem as any).description}
                  </p>
                )}
              </div>

              <button
                onClick={handleCopy}
                className="px-2.5 py-1 rounded border text-xs font-mono flex items-center gap-1.5 transition shrink-0"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-strong)',
                  color: 'var(--text-secondary)',
                }}
              >
                {copied ? <Check className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy DAX'}</span>
              </button>
            </div>

            {/* Code Box */}
            <div 
              className="flex-1 rounded border p-4 font-mono text-xs overflow-y-auto leading-relaxed"
              style={{
                backgroundColor: 'var(--bg-code)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
              }}
            >
              {highlightDax(selectedItem.expression)}
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
            Select a measure or column to inspect formula
          </div>
        )}
      </div>
    </div>
  );
};
