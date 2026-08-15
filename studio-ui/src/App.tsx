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
  Sparkles, 
  AlertCircle, 
  CheckCircle2,
  FileCode2,
  Database
} from 'lucide-react';

export const App: React.FC = () => {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);

  // Finding filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');

  const scanPath = async (targetPath: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Scan failed');
      }

      const data: ScanResult = await res.json();
      setScanResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to scan report project');
    } finally {
      setLoading(false);
    }
  };

  // Initial load: check URL params for ?path= or default to golden fixture
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const pathParam = urlParams.get('path');
    if (pathParam) {
      scanPath(pathParam);
    } else {
      // Default to scanning the local fixture or pbip_project if available
      scanPath('tests/golden/test_bidirectional');
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
    <div className="min-h-screen bg-obsidian-950 flex flex-col font-sans">
      {/* Top Header */}
      <Header
        scanResult={scanResult}
        loading={loading}
        onOpenBrowser={() => setIsBrowserOpen(true)}
        onRescan={() => scanResult && scanPath(scanResult.source_path)}
      />

      {/* Main Workspace Layout */}
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

        {/* Center Main View Area */}
        <main className="flex-1 overflow-y-auto p-6 bg-obsidian-950">
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{error}</span>
              </div>
              <button
                onClick={() => setIsBrowserOpen(true)}
                className="underline hover:text-white font-medium"
              >
                Browse different folder
              </button>
            </div>
          )}

          {loading && !scanResult ? (
            <div className="h-full flex flex-col items-center justify-center py-24 text-slate-400 gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
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
                      <div className="p-12 rounded-xl bg-obsidian-900/60 border border-obsidian-800 text-center space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <h4 className="text-sm font-bold text-white">No issues match the selected filters</h4>
                        <p className="text-xs text-slate-500">
                          {scanResult.findings.length === 0
                            ? 'This report passed all 11 static quality checks.'
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
            <div className="h-full flex flex-col items-center justify-center py-20 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">No Project Loaded</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  Select a Power BI Project (.pbip) folder from your filesystem to begin static analysis.
                </p>
              </div>
              <button
                onClick={() => setIsBrowserOpen(true)}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-obsidian-950 font-bold rounded-lg text-xs transition shadow-lg shadow-emerald-500/20"
              >
                Browse Projects
              </button>
            </div>
          )}
        </main>
      </div>

      {/* File Browser Modal */}
      <FileBrowserModal
        isOpen={isBrowserOpen}
        onClose={() => setIsBrowserOpen(false)}
        onSelectProject={(path) => scanPath(path)}
      />
    </div>
  );
};
