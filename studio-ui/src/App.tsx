import React, { useState, useEffect, useMemo } from 'react';
import { 
  FolderOpen, 
  Play, 
  RefreshCw, 
  FileText, 
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Database,
  Layers,
  Code2,
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle2,
  Table as TableIcon,
  Key,
  Tag,
  Lightbulb,
  Search,
  Filter,
  Columns,
  HardDrive,
  Layout,
  Network,
  X
} from 'lucide-react';
import { ScanResult, AuditFinding, TableInfo, RelationshipInfo, MeasureInfo, PageInfo } from './types';
import { highlightDax } from './utils/daxHighlighter';
import { ModelMap } from './components/ModelMap';
import { FileBrowserModal } from './components/FileBrowserModal';

export const App: React.FC = () => {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [currentPath, setCurrentPath] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Navigation / View modes: 'audit' (3-pane IDE) | 'model-graph' (Visualizer)
  const [mainView, setMainView] = useState<'audit' | 'model-graph'>('audit');

  // Selected item in IDE
  const [selectedFinding, setSelectedFinding] = useState<AuditFinding | null>(null);
  const [selectedTreeTable, setSelectedTreeTable] = useState<TableInfo | null>(null);
  const [selectedTreeMeasure, setSelectedTreeMeasure] = useState<MeasureInfo | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [treeSearch, setTreeSearch] = useState('');

  // Tree expansion state
  const [expandedSections, setExpandedSections] = useState({
    tables: true,
    relationships: false,
    measures: true,
    pages: false,
  });

  const [isBrowserModalOpen, setIsBrowserModalOpen] = useState(false);

  // Scan execution
  const scanPath = async (targetPath: string) => {
    if (!targetPath || !targetPath.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath.trim() }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Scan failed');
      }

      const data: ScanResult = await res.json();
      setScanResult(data);
      setCurrentPath(targetPath.trim());
      if (data.findings.length > 0) {
        setSelectedFinding(data.findings[0]);
      }
      setSelectedTreeTable(null);
      setSelectedTreeMeasure(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to scan report project');
    } finally {
      setLoading(false);
    }
  };

  // Native Windows File / Folder dialogs
  const handleNativeBrowse = async (mode: 'file' | 'folder' = 'file') => {
    try {
      const res = await fetch('/api/native-dialog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) {
        const data = await res.json();
        if (!data.canceled && data.path) {
          setCurrentPath(data.path);
          scanPath(data.path);
        }
      }
    } catch (err) {
      setIsBrowserModalOpen(true);
    }
  };

  // Initial check for URL query params
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const pathParam = urlParams.get('path');
    if (pathParam) {
      setCurrentPath(pathParam);
      scanPath(pathParam);
    }
  }, []);

  // Filtered findings list
  const filteredFindings = useMemo(() => {
    if (!scanResult) return [];
    return scanResult.findings.filter((f) => {
      if (filterCategory !== 'all' && f.category.toLowerCase() !== filterCategory.toLowerCase()) {
        return false;
      }
      if (filterSeverity !== 'all' && f.severity.toUpperCase() !== filterSeverity.toUpperCase()) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          f.title.toLowerCase().includes(q) ||
          f.rule_id.toLowerCase().includes(q) ||
          f.evidence.toLowerCase().includes(q) ||
          (f.location && f.location.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [scanResult, filterCategory, filterSeverity, searchQuery]);

  const overallScore = scanResult ? Math.round(scanResult.scores.overall) : 100;

  return (
    <div className="h-screen w-screen flex flex-col bg-[#12141A] text-[#E2E8F0] font-sans overflow-hidden select-none">
      {/* ── Top IDE Titlebar ────────────────────────────────────────── */}
      <header className="h-12 border-b border-[#232733] bg-[#161922] px-4 flex items-center justify-between shrink-0 z-30">
        {/* Left: Brand & View Switcher */}
        <div className="flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-blue-600 flex items-center justify-center text-white text-[11px] font-bold">
              P
            </div>
            <span className="font-semibold text-xs text-white tracking-wide">
              pbiscan Studio
            </span>
          </div>

          {scanResult && (
            <div className="flex items-center gap-1 bg-[#1F2430] p-0.5 rounded border border-[#2B3242] text-xs">
              <button
                onClick={() => setMainView('audit')}
                className={`px-2.5 py-1 rounded font-medium transition ${
                  mainView === 'audit'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Workbench &amp; Rules
              </button>
              <button
                onClick={() => setMainView('model-graph')}
                className={`px-2.5 py-1 rounded font-medium transition flex items-center gap-1.5 ${
                  mainView === 'model-graph'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Network className="w-3.5 h-3.5" />
                <span>Model Map</span>
              </button>
            </div>
          )}
        </div>

        {/* Center: File Input & Browse Controls */}
        <div className="flex-1 max-w-xl mx-4 flex items-center gap-2">
          <div className="relative flex-1 flex items-center">
            <input
              type="text"
              value={currentPath}
              onChange={(e) => setCurrentPath(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') scanPath(currentPath);
              }}
              placeholder="Browse or type path to .pbip file / folder..."
              className="w-full pl-3 pr-24 py-1 bg-[#0E1015] border border-[#232733] rounded text-xs text-slate-200 font-mono placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
            />
            <button
              onClick={() => handleNativeBrowse('file')}
              className="absolute right-1 px-2 py-0.5 rounded bg-[#1F2430] hover:bg-[#2B3242] text-slate-300 border border-[#2B3242] text-[11px] font-medium flex items-center gap-1 transition"
              title="Open native Windows file picker"
            >
              <FolderOpen className="w-3 h-3 text-blue-400" />
              <span>Browse</span>
            </button>
          </div>

          <button
            onClick={() => scanPath(currentPath)}
            disabled={loading || !currentPath.trim()}
            className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center gap-1.5 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shrink-0"
          >
            {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3 fill-white" />}
            <span>{loading ? 'Scanning...' : 'Analyze'}</span>
          </button>
        </div>

        {/* Right: Health Badge & GitHub Link */}
        <div className="flex items-center gap-3 shrink-0 text-xs">
          {scanResult && (
            <div className="flex items-center gap-2 px-2.5 py-0.5 rounded bg-[#1F2430] border border-[#2B3242] font-mono">
              <span className="text-slate-400 text-[11px]">Score:</span>
              <span className={`font-bold ${overallScore >= 90 ? 'text-emerald-400' : overallScore >= 70 ? 'text-amber-400' : 'text-red-400'}`}>
                {overallScore}/100
              </span>
              <span className="text-slate-500 text-[10px]">·</span>
              <span className="text-slate-300 text-[11px]">{scanResult.findings.length} findings</span>
            </div>
          )}

          <a
            href="https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white transition p-1"
            title="GitHub Repository"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* ── Main Workspace Body ────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {error && (
          <div className="absolute top-14 left-1/2 -translate-x-1/2 z-50 p-3 rounded bg-red-950 border border-red-800 text-red-200 text-xs flex items-center gap-3 shadow-xl">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span><strong>Scan Error:</strong> {error}</span>
            <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
            <div className="text-xs font-mono">Parsing TMDL, TMSL, and PBIR artifacts...</div>
          </div>
        ) : !scanResult ? (
          /* ── Clean Landing / File Selection State ────────────────── */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center max-w-lg mx-auto space-y-5">
            <div className="w-10 h-10 rounded-lg bg-[#1F2430] border border-[#2B3242] flex items-center justify-center text-blue-400 shadow-sm">
              <FolderOpen className="w-5 h-5" />
            </div>

            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Power BI Static Quality Workbench
              </h2>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Select your <span className="font-mono text-slate-200">.pbip</span> file or project folder to begin automated diagnostics.
              </p>
            </div>

            <div className="w-full space-y-2">
              <div className="flex gap-2">
                <button
                  onClick={() => handleNativeBrowse('file')}
                  className="flex-1 py-2 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition shadow-sm"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Browse .pbip File</span>
                </button>
                <button
                  onClick={() => handleNativeBrowse('folder')}
                  className="py-2 px-3 rounded bg-[#1F2430] hover:bg-[#2B3242] text-slate-200 border border-[#2B3242] text-xs font-medium flex items-center justify-center gap-1.5 transition"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-blue-400" />
                  <span>Folder</span>
                </button>
              </div>

              <div className="pt-4 border-t border-[#232733] text-left space-y-1.5">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                  Test Fixture
                </div>
                <button
                  onClick={() => scanPath('pbip_project/world is going bananas.pbip')}
                  className="w-full p-2.5 rounded bg-[#161922] hover:bg-[#1F2430] border border-[#232733] text-left transition flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-mono font-medium text-slate-200">world is going bananas.pbip</div>
                    <div className="text-[10px] font-mono text-slate-500">15 tables · TMDL Model · 2 Findings</div>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                </button>
              </div>
            </div>
          </div>
        ) : mainView === 'model-graph' ? (
          /* ── Full Canvas View: Model Map ─────────────────────────── */
          <div className="flex-1 p-3 bg-[#0E1015]">
            <ModelMap tables={scanResult.tables} relationships={scanResult.relationships} />
          </div>
        ) : (
          /* ── 3-Pane Developer Workbench ──────────────────────────── */
          <div className="flex-1 flex w-full overflow-hidden">
            {/* ══ PANE 1: Model Explorer Tree (Left) ═════════════════ */}
            <div className="w-64 border-r border-[#232733] bg-[#161922] flex flex-col justify-between shrink-0 overflow-hidden text-xs">
              <div className="flex flex-col flex-1 min-h-0">
                {/* Tree Header & Quick Search */}
                <div className="p-2.5 border-b border-[#232733] space-y-2 shrink-0">
                  <div className="flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    <span>Model Explorer</span>
                    <span className="font-mono text-slate-500">{scanResult.tables.length} tables</span>
                  </div>
                  <div className="relative">
                    <Search className="w-3 h-3 text-slate-500 absolute left-2 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search schema..."
                      value={treeSearch}
                      onChange={(e) => setTreeSearch(e.target.value)}
                      className="w-full pl-6 pr-2 py-1 bg-[#0E1015] border border-[#232733] rounded text-[11px] text-slate-200 font-mono placeholder-slate-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                {/* Tree View Items */}
                <div className="flex-1 overflow-y-auto p-1.5 space-y-1 font-mono text-[11px]">
                  {/* Tables Node */}
                  <div>
                    <div
                      onClick={() => setExpandedSections((s) => ({ ...s, tables: !s.tables }))}
                      className="flex items-center justify-between p-1 rounded hover:bg-[#1F2430] cursor-pointer text-slate-300 font-semibold"
                    >
                      <div className="flex items-center gap-1.5">
                        {expandedSections.tables ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        <Database className="w-3.5 h-3.5 text-blue-400" />
                        <span>Tables ({scanResult.tables.length})</span>
                      </div>
                    </div>

                    {expandedSections.tables && (
                      <div className="pl-4 space-y-0.5 mt-0.5">
                        {scanResult.tables
                          .filter((t) => !treeSearch || t.name.toLowerCase().includes(treeSearch.toLowerCase()))
                          .map((tbl) => {
                            const isSelected = selectedTreeTable?.name === tbl.name;
                            return (
                              <div
                                key={tbl.name}
                                onClick={() => {
                                  setSelectedTreeTable(tbl);
                                  setSelectedTreeMeasure(null);
                                  setSelectedFinding(null);
                                }}
                                className={`px-2 py-1 rounded cursor-pointer truncate flex items-center justify-between ${
                                  isSelected
                                    ? 'bg-blue-600 text-white font-medium'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#1F2430]'
                                }`}
                                title={tbl.name}
                              >
                                <span className="truncate">{tbl.name}</span>
                                <span className="text-[10px] text-slate-500 shrink-0">{tbl.column_count}c</span>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>

                  {/* Measures Node */}
                  <div>
                    <div
                      onClick={() => setExpandedSections((s) => ({ ...s, measures: !s.measures }))}
                      className="flex items-center justify-between p-1 rounded hover:bg-[#1F2430] cursor-pointer text-slate-300 font-semibold mt-1"
                    >
                      <div className="flex items-center gap-1.5">
                        {expandedSections.measures ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        <Code2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Measures ({scanResult.measures.length})</span>
                      </div>
                    </div>

                    {expandedSections.measures && (
                      <div className="pl-4 space-y-0.5 mt-0.5">
                        {scanResult.measures
                          .filter((m) => !treeSearch || m.name.toLowerCase().includes(treeSearch.toLowerCase()))
                          .map((m) => {
                            const isSelected = selectedTreeMeasure?.name === m.name;
                            return (
                              <div
                                key={`${m.table}-${m.name}`}
                                onClick={() => {
                                  setSelectedTreeMeasure(m);
                                  setSelectedTreeTable(null);
                                  setSelectedFinding(null);
                                }}
                                className={`px-2 py-1 rounded cursor-pointer truncate flex items-center justify-between ${
                                  isSelected
                                    ? 'bg-emerald-600 text-white font-medium'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#1F2430]'
                                }`}
                                title={`[${m.name}] in '${m.table}'`}
                              >
                                <span className="truncate">[{m.name}]</span>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>

                  {/* Relationships Node */}
                  <div>
                    <div
                      onClick={() => setExpandedSections((s) => ({ ...s, relationships: !s.relationships }))}
                      className="flex items-center justify-between p-1 rounded hover:bg-[#1F2430] cursor-pointer text-slate-300 font-semibold mt-1"
                    >
                      <div className="flex items-center gap-1.5">
                        {expandedSections.relationships ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        <Network className="w-3.5 h-3.5 text-amber-400" />
                        <span>Relationships ({scanResult.relationships.length})</span>
                      </div>
                    </div>

                    {expandedSections.relationships && (
                      <div className="pl-4 space-y-0.5 mt-0.5 text-[10px] text-slate-400">
                        {scanResult.relationships.map((r, i) => (
                          <div key={i} className="p-1 rounded hover:bg-[#1F2430] truncate" title={`${r.from_table} -> ${r.to_table}`}>
                            {r.from_table} ↔ {r.to_table}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Left Pane Footer: Category Score Mini-Bar */}
              <div className="p-2.5 border-t border-[#232733] bg-[#12141A] text-[10px] font-mono text-slate-400 space-y-1">
                <div className="flex justify-between">
                  <span>Model Score:</span>
                  <span className="text-slate-200">{scanResult.scores.category_scores.model ?? 100}%</span>
                </div>
                <div className="flex justify-between">
                  <span>DAX Score:</span>
                  <span className="text-slate-200">{scanResult.scores.category_scores.dax ?? 100}%</span>
                </div>
                <div className="flex justify-between">
                  <span>Canvas Score:</span>
                  <span className="text-slate-200">{scanResult.scores.category_scores.report ?? 100}%</span>
                </div>
              </div>
            </div>

            {/* ══ PANE 2: Issues & Findings Stream (Middle) ════════════ */}
            <div className="w-80 lg:w-96 border-r border-[#232733] bg-[#12141A] flex flex-col justify-between shrink-0 overflow-hidden text-xs">
              {/* Finding Filters Header */}
              <div className="p-2.5 border-b border-[#232733] bg-[#161922] space-y-2 shrink-0">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-slate-400 uppercase tracking-wider">
                    Diagnostic Findings
                  </span>
                  <span className="font-mono text-slate-400 font-semibold">
                    {filteredFindings.length} of {scanResult.findings.length}
                  </span>
                </div>

                {/* Filter Controls */}
                <div className="flex items-center gap-1.5 text-[11px] font-mono">
                  {['all', 'CRITICAL', 'MEDIUM', 'ADVISORY'].map((sev) => (
                    <button
                      key={sev}
                      onClick={() => setFilterSeverity(sev)}
                      className={`px-2 py-0.5 rounded transition ${
                        filterSeverity === sev
                          ? 'bg-blue-600 text-white font-semibold'
                          : 'bg-[#1F2430] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {sev === 'all' ? 'ALL' : sev}
                    </button>
                  ))}
                </div>
              </div>

              {/* Findings List (Dense Problem Rows like VS Code / GitHub) */}
              <div className="flex-1 overflow-y-auto divide-y divide-[#1F2430]">
                {filteredFindings.length > 0 ? (
                  filteredFindings.map((f, idx) => {
                    const isSelected = selectedFinding?.rule_id === f.rule_id && selectedFinding?.location === f.location;
                    const isCrit = f.severity === 'CRITICAL';
                    const isMed = f.severity === 'MEDIUM' || f.severity === 'WARNING';
                    
                    return (
                      <div
                        key={`${f.rule_id}-${f.location}-${idx}`}
                        onClick={() => {
                          setSelectedFinding(f);
                          setSelectedTreeTable(null);
                          setSelectedTreeMeasure(null);
                        }}
                        className={`p-3 cursor-pointer transition text-left select-none ${
                          isSelected
                            ? 'bg-[#1F2430] border-l-2 border-blue-500'
                            : 'hover:bg-[#161922]'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`w-2 h-2 rounded-full shrink-0 ${
                                isCrit ? 'bg-red-500' : isMed ? 'bg-amber-500' : 'bg-blue-500'
                              }`}
                            />
                            <span className="font-mono font-bold text-[10px] text-slate-400">
                              {f.rule_id}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-slate-500 uppercase">
                            {f.category}
                          </span>
                        </div>

                        <div className="font-medium text-slate-200 text-xs truncate">
                          {f.title}
                        </div>

                        {f.location && (
                          <div className="font-mono text-[10px] text-slate-500 truncate mt-0.5">
                            {f.location}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="p-8 text-center text-slate-500 text-xs space-y-1">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto" />
                    <div>No findings match filter</div>
                  </div>
                )}
              </div>
            </div>

            {/* ══ PANE 3: Finding Detail Inspector & Code Viewer (Right) */}
            <div className="flex-1 bg-[#0E1015] flex flex-col justify-between overflow-hidden text-xs">
              {selectedFinding ? (
                /* Finding Inspector */
                <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-5">
                  {/* Title & Metadata */}
                  <div className="pb-4 border-b border-[#232733]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-[#1F2430] text-slate-300 font-mono text-[11px] font-semibold border border-[#2B3242]">
                        {selectedFinding.rule_id}
                      </span>
                      <span className="text-slate-500 font-mono text-xs">
                        Category: {selectedFinding.category.toUpperCase()}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-white mt-1">
                      {selectedFinding.title}
                    </h3>
                    {selectedFinding.location && (
                      <p className="font-mono text-xs text-blue-400 mt-1">
                        Location: {selectedFinding.location}
                      </p>
                    )}
                  </div>

                  {/* Evidence Box */}
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5 text-blue-400" />
                      <span>Evidence / Raw Signal</span>
                    </div>
                    <div className="p-3 rounded bg-[#161922] border border-[#232733] font-mono text-xs text-emerald-300 break-all leading-relaxed">
                      {selectedFinding.evidence}
                    </div>
                  </div>

                  {/* Technical Analysis Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3.5 rounded bg-[#161922] border border-[#232733] space-y-1">
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                        Issue Detail
                      </div>
                      <p className="text-slate-300 text-xs leading-relaxed">
                        {selectedFinding.issue}
                      </p>
                    </div>

                    <div className="p-3.5 rounded bg-[#161922] border border-[#232733] space-y-1">
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                        Technical Impact
                      </div>
                      <p className="text-slate-300 text-xs leading-relaxed">
                        {selectedFinding.impact}
                      </p>
                    </div>
                  </div>

                  {/* Remediation Box */}
                  <div className="p-4 rounded bg-[#161922] border-l-4 border-l-emerald-500 border border-[#232733] space-y-1.5">
                    <div className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Lightbulb className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Remediation Guidance</span>
                    </div>
                    <p className="text-slate-200 text-xs leading-relaxed">
                      {selectedFinding.recommendation}
                    </p>
                  </div>
                </div>
              ) : selectedTreeTable ? (
                /* Table Schema Inspector */
                <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-4">
                  <div className="pb-3 border-b border-[#232733]">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-blue-400" />
                      <h3 className="text-base font-bold font-mono text-white">
                        {selectedTreeTable.name}
                      </h3>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      {selectedTreeTable.column_count} columns · {selectedTreeTable.measures_count} measures
                    </p>
                  </div>

                  <div className="space-y-1 font-mono text-xs">
                    <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Column Schema
                    </div>
                    {selectedTreeTable.columns?.map((col) => (
                      <div
                        key={col.name}
                        className="p-2 rounded bg-[#161922] border border-[#232733] flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          {col.in_relationship && <Key className="w-3.5 h-3.5 text-blue-400" />}
                          <span className="text-slate-200">{col.name}</span>
                        </div>
                        <span className="text-slate-500 text-[11px]">{col.data_type || 'string'}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : selectedTreeMeasure ? (
                /* Measure DAX Viewer */
                <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-4">
                  <div className="pb-3 border-b border-[#232733]">
                    <div className="flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-emerald-400" />
                      <h3 className="text-base font-bold font-mono text-white">
                        [{selectedTreeMeasure.name}]
                      </h3>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      Table: '{selectedTreeMeasure.table}'
                    </p>
                  </div>

                  <div className="space-y-1.5 flex-1 flex flex-col min-h-0">
                    <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      DAX Expression
                    </div>
                    <div className="flex-1 p-4 rounded bg-[#161922] border border-[#232733] overflow-y-auto font-mono text-xs">
                      {highlightDax(selectedTreeMeasure.expression)}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
                  Select a diagnostic finding or tree item to view details
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Fallback In-App File Browser */}
      <FileBrowserModal
        isOpen={isBrowserModalOpen}
        onClose={() => setIsBrowserModalOpen(false)}
        onSelectProject={(path) => {
          setCurrentPath(path);
          scanPath(path);
        }}
      />
    </div>
  );
};
