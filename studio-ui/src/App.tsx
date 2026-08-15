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
  ShieldCheck,
  Zap,
  HardDrive,
  FileText
} from 'lucide-react';

export const App: React.FC = () => {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [currentPath, setCurrentPath] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);

  // Finding filters
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
      setActiveTab('dashboard');
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to scan report project');
    } finally {
      setLoading(false);
    }
  };

  // Native Windows File / Folder Picker
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
      setIsBrowserOpen(true);
    }
  };

  // Only auto-scan if explicit ?path= was passed in URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const pathParam = urlParams.get('path');
    if (pathParam) {
      setCurrentPath(pathParam);
      scanPath(pathParam);
    }
  }, []);

  // Filtered findings
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
    <div className="min-h-screen bg-studio-bg text-studio-text flex flex-col font-sans">
      {/* Top Header */}
      <Header
        scanResult={scanResult}
        currentPath={currentPath}
        onPathChange={setCurrentPath}
        loading={loading}
        onRunScan={(p) => scanPath(p)}
        onNativeBrowse={() => handleNativeBrowse('file')}
        onResetToHome={() => {
          setScanResult(null);
          setCurrentPath('');
          setError(null);
        }}
      />

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar (Visible when report is loaded) */}
        {scanResult && (
          <Sidebar
            activeTab={activeTab}
            onSelectTab={setActiveTab}
            findingsCount={scanResult.findings.length}
            tablesCount={scanResult.tables.length}
            measuresCount={scanResult.measures.length}
            pagesCount={scanResult.pages.length}
            onNewScan={() => {
              setScanResult(null);
              setCurrentPath('');
            }}
          />
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6 bg-studio-bg">
          {error && (
            <div className="max-w-4xl mx-auto mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span><strong>Scan Error:</strong> {error}</span>
              </div>
              <button
                onClick={() => handleNativeBrowse('file')}
                className="underline hover:text-white font-medium ml-4 text-xs"
              >
                Browse .pbip File
              </button>
            </div>
          )}

          {loading ? (
            <div className="h-full flex flex-col items-center justify-center py-28 text-studio-subtle gap-3">
              <RefreshCw className="w-7 h-7 animate-spin text-blue-500" />
              <div className="text-sm font-semibold text-white">Analyzing Power BI Artifacts...</div>
              <div className="text-xs text-studio-subtle font-mono">Running 11 static model, DAX, and visual checks</div>
            </div>
          ) : scanResult ? (
            /* Active Project Audit Dashboard */
            <div className="max-w-6xl mx-auto space-y-5">
              {/* Tab 1: Dashboard Overview */}
              {activeTab === 'dashboard' && (
                <div className="space-y-5">
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

                  {/* Findings List */}
                  <div className="space-y-2.5">
                    <div className="text-xs font-semibold text-studio-subtle uppercase tracking-wider px-1">
                      Audit Findings ({filteredFindings.length})
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
                      <div className="p-12 rounded-lg bg-studio-card border border-studio-border text-center space-y-2">
                        <CheckCircle2 className="w-7 h-7 text-emerald-400 mx-auto" />
                        <h4 className="text-sm font-semibold text-white">No issues found matching filters</h4>
                        <p className="text-xs text-studio-subtle">
                          {scanResult.findings.length === 0
                            ? 'This report passed all 11 static quality rules.'
                            : 'Try adjusting your search query or severity filters.'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Model Architecture */}
              {activeTab === 'model-map' && (
                <div className="h-[calc(100vh-8.5rem)]">
                  <ModelMap
                    tables={scanResult.tables}
                    relationships={scanResult.relationships}
                  />
                </div>
              )}

              {/* Tab 3: DAX Measures */}
              {activeTab === 'dax-explorer' && (
                <div>
                  <DaxExplorer
                    measures={scanResult.measures}
                    calcCols={scanResult.calculated_columns}
                    findings={scanResult.findings}
                  />
                </div>
              )}

              {/* Tab 4: Visual Pages */}
              {activeTab === 'pages' && (
                <div>
                  <PagesViewer
                    pages={scanResult.pages}
                    findings={scanResult.findings}
                  />
                </div>
              )}
            </div>
          ) : (
            /* Clean Landing Screen (Human-Crafted Tool) */
            <div className="max-w-xl mx-auto py-16 text-center space-y-6">
              <div className="w-12 h-12 rounded-xl bg-studio-card border border-studio-border flex items-center justify-center text-blue-400 mx-auto shadow-sm">
                <FileText className="w-6 h-6" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Power BI Report Quality Scanner
                </h2>
                <p className="text-xs text-studio-subtle mt-1.5 max-w-md mx-auto leading-relaxed">
                  Select your <span className="font-mono text-slate-300">.pbip</span> file or project directory to analyze semantic modeling, DAX performance, and report bloat.
                </p>
              </div>

              {/* Action Box with .pbip file browse button */}
              <div className="p-6 rounded-xl bg-studio-card border border-studio-border text-left space-y-4 shadow-sm">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Selected Path or .pbip File</label>
                  <input
                    type="text"
                    value={currentPath}
                    onChange={(e) => setCurrentPath(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') scanPath(currentPath);
                    }}
                    placeholder="e.g. C:\Reports\SalesAnalytics.pbip"
                    className="w-full px-3 py-2 bg-studio-bg border border-studio-border rounded-md text-xs text-studio-text placeholder-studio-subtle font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* Primary Browse Action Buttons */}
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    onClick={() => handleNativeBrowse('file')}
                    className="py-2 px-3 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow-sm"
                  >
                    <FileText className="w-4 h-4" />
                    <span>Browse .pbip File</span>
                  </button>

                  <button
                    onClick={() => handleNativeBrowse('folder')}
                    className="py-2 px-3 rounded-md bg-studio-bg hover:bg-studio-border text-slate-200 border border-studio-border text-xs font-medium flex items-center justify-center gap-1.5 transition"
                  >
                    <FolderOpen className="w-4 h-4 text-blue-400" />
                    <span>Browse Folder</span>
                  </button>
                </div>

                {/* Run Audit Button */}
                {currentPath.trim() && (
                  <button
                    onClick={() => scanPath(currentPath)}
                    className="w-full py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition flex items-center justify-center gap-2 shadow-sm"
                  >
                    <Play className="w-3.5 h-3.5 fill-white" />
                    <span>Run Quality Audit</span>
                  </button>
                )}
              </div>

              {/* Sample Projects */}
              <div className="pt-4 border-t border-studio-border text-left space-y-2">
                <div className="text-[11px] font-medium text-studio-subtle uppercase tracking-wider">
                  Test Fixtures
                </div>
                <div className="space-y-1.5">
                  <button
                    onClick={() => scanPath('pbip_project/world is going bananas.pbip')}
                    className="w-full p-2.5 rounded-md bg-studio-card hover:bg-studio-cardHover border border-studio-border text-left transition flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-medium text-slate-200">world is going bananas.pbip</div>
                      <div className="text-[10px] font-mono text-studio-subtle">15 tables · TMDL Semantic Model</div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-studio-subtle" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* In-App Explorer Modal */}
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
