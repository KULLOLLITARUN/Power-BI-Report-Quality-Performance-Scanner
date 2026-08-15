import React, { useState } from 'react';
import { MeasureInfo, CalculatedColumnInfo, AuditFinding } from '../types';
import { highlightDax } from '../utils/daxHighlighter';
import { 
  Code2, 
  Search, 
  Copy, 
  Check, 
  AlertTriangle, 
  Eye, 
  EyeOff, 
  Filter,
  Columns,
  Calculator
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

  const handleCopy = () => {
    if (selectedItem?.expression) {
      navigator.clipboard.writeText(selectedItem.expression);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isDuplicate = (name: string) => {
    return duplicateFindings.some((f) => f.evidence.includes(name));
  };

  const isUnused = (name: string) => {
    return unusedFindings.some((f) => f.evidence.includes(name));
  };

  return (
    <div className="h-[calc(100vh-8.5rem)] flex flex-col md:flex-row gap-4">
      {/* Left Column: Measure & Column List */}
      <div className="w-full md:w-80 bg-obsidian-800/80 border border-obsidian-700 rounded-xl p-4 flex flex-col justify-between shrink-0 overflow-hidden shadow-sm">
        <div className="space-y-3 flex-1 flex flex-col min-h-0">
          {/* Tab switch: Measures vs Calc Columns */}
          <div className="grid grid-cols-2 gap-1 p-1 bg-obsidian-950 rounded-lg border border-obsidian-700/80 text-xs">
            <button
              onClick={() => {
                setActiveTab('measures');
                if (filteredMeasures.length > 0) setSelectedItem(filteredMeasures[0]);
              }}
              className={`py-1.5 rounded-md font-medium transition flex items-center justify-center gap-1.5 ${
                activeTab === 'measures'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Calculator className="w-3.5 h-3.5" />
              <span>Measures ({measures.length})</span>
            </button>
            <button
              onClick={() => {
                setActiveTab('calcCols');
                if (filteredCalcCols.length > 0) setSelectedItem(filteredCalcCols[0]);
              }}
              className={`py-1.5 rounded-md font-medium transition flex items-center justify-center gap-1.5 ${
                activeTab === 'calcCols'
                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Calc Cols ({calcCols.length})</span>
            </button>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter by name or formula..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-obsidian-950 border border-obsidian-700 rounded-md text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
            />
          </div>

          {/* Table filter dropdown */}
          <select
            value={selectedTable}
            onChange={(e) => setSelectedTable(e.target.value)}
            className="w-full px-2.5 py-1.5 bg-obsidian-950 border border-obsidian-700 rounded-md text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition font-mono"
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
                      className={`p-2.5 rounded-lg cursor-pointer transition border text-xs flex items-center justify-between ${
                        isSelected
                          ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
                          : 'bg-obsidian-900/60 border-obsidian-700/60 hover:bg-obsidian-800 text-slate-300'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-semibold truncate font-mono">{m.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono truncate">{m.table}</div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        {duplicate && (
                          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                            duplicate
                          </span>
                        )}
                        {unused && (
                          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                            unused
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8 text-xs text-slate-500">No measures match search</div>
              )
            ) : filteredCalcCols.length > 0 ? (
              filteredCalcCols.map((c) => {
                const isSelected = selectedItem?.name === c.name && selectedItem?.table === c.table;
                return (
                  <div
                    key={`${c.table}-${c.name}`}
                    onClick={() => setSelectedItem(c)}
                    className={`p-2.5 rounded-lg cursor-pointer transition border text-xs flex items-center justify-between ${
                      isSelected
                        ? 'bg-blue-500/15 border-blue-500/40 text-blue-200'
                        : 'bg-obsidian-900/60 border-obsidian-700/60 hover:bg-obsidian-800 text-slate-300'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="font-semibold truncate font-mono">{c.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono truncate">{c.table}</div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8 text-xs text-slate-500">No calculated columns match search</div>
            )}
          </div>
        </div>
      </div>

      {/* Right Column: DAX Code Viewer & Quality Alerts */}
      <div className="flex-1 bg-obsidian-800/80 border border-obsidian-700 rounded-xl p-5 flex flex-col justify-between overflow-hidden shadow-sm">
        {selectedItem ? (
          <div className="space-y-4 flex-1 flex flex-col min-h-0">
            {/* Header info */}
            <div className="flex items-center justify-between pb-3 border-b border-obsidian-700/70">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold font-mono text-white">
                    {selectedItem.name}
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-obsidian-700 text-slate-300 border border-obsidian-600">
                    {selectedItem.table}
                  </span>
                </div>
                <div className="text-xs text-slate-400 font-mono mt-0.5">
                  Full reference: <span className="text-teal-300">'{selectedItem.table}'</span>[{selectedItem.name}]
                </div>
              </div>

              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-obsidian-900 hover:bg-obsidian-700 text-xs font-medium text-slate-200 border border-obsidian-700 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy DAX'}</span>
              </button>
            </div>

            {/* Quality Alerts if any */}
            {(isDuplicate(selectedItem.name) || isUnused(selectedItem.name)) && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs space-y-1">
                {isDuplicate(selectedItem.name) && (
                  <div className="text-amber-300 font-medium flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span>Duplicate Logic Detected: This measure has the identical formula as another measure.</span>
                  </div>
                )}
                {isUnused(selectedItem.name) && (
                  <div className="text-indigo-300 font-medium flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Unused Measure: This measure is not placed in any report visuals or referenced by other measures.</span>
                  </div>
                )}
              </div>
            )}

            {/* Syntax Highlighted Code Viewer */}
            <div className="flex-1 rounded-xl bg-obsidian-950 border border-obsidian-700/80 p-4 overflow-y-auto font-mono text-xs">
              {highlightDax(selectedItem.expression)}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
            Select a measure or calculated column to view formula
          </div>
        )}
      </div>
    </div>
  );
};
