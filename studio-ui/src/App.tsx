import React, { useState, useEffect, useMemo } from 'react';
import { Header } from './components/Header';
import { Sidebar, TabType } from './components/Sidebar';
import { HealthScorecard } from './components/HealthScorecard';
import { FindingCard } from './components/FindingCard';
import { FindingFilterBar } from './components/FindingFilterBar';
import { ModelMap } from './components/ModelMap';
import { DaxExplorer } from './components/DaxExplorer';
import { PagesViewer } from './components/PagesViewer';
import { FileBrowserModal } from './components/FileBrowserModal';
import { ScanResult } from './types';
import { 
  RefreshCw, 
  FolderOpen, 
  Play, 
  AlertCircle, 
  CheckCircle2,
  FileCode2,
  Database,
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Zap
} from 'lucide-react';

export const App: React.FC = () => {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [currentPath, setCurrentPath] = useState<string>('pbip_project/world is going bananas.pbip');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  // Finding filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');

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
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to scan report project');
    } finally {
      setLoading(false);
    }
  };

  // Native folder picker trigger
  const handleNativeBrowse = async () => {
    try {
      const res = await fetch('/api/native-dialog', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (!data.canceled && data.path) {
          setCurrentPath(data.path);
          scanPath(data.path);
        }
      }
    } catch (err) {
      // Fallback to in-app explorer
      setIsBrowserOpen(true);
    }
  };

  // Initial load
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const pathParam = urlParams.get('path');
    if (pathParam) {
      setCurrentPath(pathParam);
      scanPath(pathParam);
    } else {
      scanPath('pbip_project/world is going bananas.pbip');
    }
  }, []);

  // Filtered findings calculation
  const filteredFindings = useMemo(() => {
    if (!scanResult) return [];
    return scanResult.findings.filter((f) => {
      if (selectedCategory !== 'all' && f.category.toLowerCase() !== selectedCategory.toLowerCase()) {
        return false;
      }
      if (selectedSeverity !== 'all' && f.severity.toUpperCase() !== selectedSeverity.toUpperCase()) {
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
  }, [scanResult, selectedCategory, selectedSeverity, searchQuery]);

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans`}>
      {/* Top Header with Browse & Run Controls */}
      <Header
        scanResult={scanResult}
        currentPath={currentPath}
        onPathChange={setCurrentPath}
        loading={loading}
        onRunScan={(p) => scanPath(p)}
        onOpenBrowserModal={() => setIsBrowserOpen(true)}
        onNativeBrowse={handleNativeBrowse}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      />

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          findingsCount={scanResult?.findings.length || 0}
          tablesCount={scanResult?.tables.length || 0}
          measuresCount={scanResult?.measures.length || 0}
          pagesCount={scanResult?.pages.length || 0}
        />

        {/* Center View */}
        <main className="flex-1 overflow-y-auto p-6 bg-slate-950">
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span><strong>Scan Failed:</strong> {error}</span>
              </div>
              <button
                onClick={handleNativeBrowse}
                className="underline hover:text-white font-medium ml-4"
              >
                Browse folder
              </button>
            </div>
          )}

          {loading && !scanResult ? (
            <div className="h-full flex flex-col items-center justify-center py-24 text-slate-400 gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
              <div className="text-sm font-semibold text-white">Analyzing Power BI Artifacts...</div>
              <div className="text-xs text-slate-500 font-mono">Running 11 quality &amp; performance checks</div>
            </div>
          ) : scanResult ? (
            <div className="max-w-7xl mx-auto space-y-6">
              {/* Tab 1: Audit Dashboard */}
              {activeTab === 'dashboard' && (
                <div className="space-y-6 animate-in fade-in duration-200">
                  <HealthScorecard
                    scores={scanResult.scores}
                    warningsCount={scanResult.warnings.length}
                  />

                  <FindingFilterBar
                    searchQuery={searchQuery}
                    onSearchChange={setSearchQuery}
                    selectedCategory={selectedCategory}
                    onCategoryChange={setSelectedCategory}
                    selectedSeverity={selectedSeverity}
                    onSeverityChange={setSelectedSeverity}
                    totalCount={scanResult.findings.length}
                    filteredCount={filteredFindings.length}
                  />

                  {/* Finding List */}
                  <div className="space-y-3">
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">
                      Quality Audit Findings ({filteredFindings.length})
                    </div>

                    {filteredFindings.length > 0 ? (
                      filteredFindings.map((finding, idx) => (
                        <FindingCard
                          key={`${finding.rule_id}-${finding.location}-${idx}`}
                          finding={finding}
                          index={idx}
                        />
                      ))
                    ) : (
                      <div className="p-12 rounded-xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <h4 className="text-sm font-bold text-white">No issues found matching the selected filters</h4>
                        <p className="text-xs text-slate-500">
                          {scanResult.findings.length === 0
                            ? 'This report passed all 11 static quality rules.'
                            : 'Try adjusting your search query or severity filters.'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Semantic Model Map */}
              {activeTab === 'model-map' && (
                <div className="h-[calc(100vh-9rem)] animate-in fade-in duration-200">
                  <ModelMap
                    tables={scanResult.tables}
                    relationships={scanResult.relationships}
                  />
                </div>
              )}

              {/* Tab 3: DAX Explorer */}
              {activeTab === 'dax-explorer' && (
                <div className="animate-in fade-in duration-200">
                  <DaxExplorer
                    measures={scanResult.measures}
                    calcCols={scanResult.calculated_columns}
                    findings={scanResult.findings}
                  />
                </div>
              )}

              {/* Tab 4: Report Pages */}
              {activeTab === 'pages' && (
                <div className="animate-in fade-in duration-200">
                  <PagesViewer
                    pages={scanResult.pages}
                    findings={scanResult.findings}
                  />
                </div>
              )}
            </div>
          ) : (
            /* Home / Welcome State with Quick Actions */
            <div className="max-w-2xl mx-auto py-16 text-center space-y-6">
              <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mx-auto shadow-lg">
                <Database className="w-7 h-7" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-white">Open a Power BI Report (.pbip)</h2>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                  Browse a project folder on your computer or paste the folder path above to run the 11-rule automated quality and performance scanner.
                </p>
              </div>

              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={handleNativeBrowse}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl text-xs transition flex items-center gap-2 shadow-md shadow-blue-500/20"
                >
                  <FolderOpen className="w-4 h-4" />
                  <span>Browse Folder on PC</span>
                </button>
                <button
                  onClick={() => setIsBrowserOpen(true)}
                  className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl text-xs transition border border-slate-700"
                >
                  In-App Explorer
                </button>
              </div>

              {/* Quick Sample Presets */}
              <div className="pt-8 border-t border-slate-800 text-left space-y-2">
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Quick Load Demo Reports
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    onClick={() => scanPath('pbip_project/world is going bananas.pbip')}
                    className="p-3 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-left transition flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-200">World is Going Bananas</div>
                      <div className="text-[10px] font-mono text-slate-500">15 tables, TMDL model</div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                  </button>

                  <button
                    onClick={() => scanPath('tests/golden/test_bidirectional')}
                    className="p-3 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-left transition flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-200">Bi-directional Fixture</div>
                      <div className="text-[10px] font-mono text-slate-500">Model quality test fixture</div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* In-App File Browser Modal */}
      <FileBrowserModal
        isOpen={isBrowserOpen}
        onClose={() => setIsBrowserOpen(false)}
        onSelectProject={(path) => {
          setCurrentPath(path);
          scanPath(path);
        }}
      />
    </div>
  );
};
