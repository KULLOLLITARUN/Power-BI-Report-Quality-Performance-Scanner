import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Header } from './components/Header';
import { Sidebar, TabType } from './components/Sidebar';
import { HealthScorecard } from './components/HealthScorecard';
import { FindingCard } from './components/FindingCard';
import { FindingFilterBar } from './components/FindingFilterBar';
import { ModelMap } from './components/ModelMap';
import { DaxExplorer } from './components/DaxExplorer';
import { PagesViewer } from './components/PagesViewer';
import { DiffViewer } from './components/DiffViewer';
import { RemediationPanel } from './components/RemediationPanel';
import { AgentIntegrationPanel } from './components/AgentIntegrationPanel';
import { FileBrowserModal } from './components/FileBrowserModal';
import { ScanResult } from './types';
import { useTheme } from './hooks/useTheme';
import { SAMPLE_BANANAS_REPORT, SAMPLE_ENTERPRISE_REPORT } from './data/sampleReports';
import { parseDroppedPbip, DroppedFile } from './engine/clientScanner';
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
  FileText,
  UploadCloud,
  GitCompare
} from 'lucide-react';

export const App: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [currentPath, setCurrentPath] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [hasBackend, setHasBackend] = useState<boolean>(false);

  const folderInputRef = useRef<HTMLInputElement>(null);

  // Finding filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');

  // Detect if local Python FastAPI backend is alive
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          const ct = res.headers.get('content-type') || '';
          if (ct.includes('application/json')) {
            const data = await res.json();
            if (data?.status === 'ok') {
              setHasBackend(true);
              return;
            }
          }
        }
      } catch {}
      setHasBackend(false);
    };
    checkBackend();
  }, []);

  // Explicit demo loader
  const loadExplicitDemo = (type: 'bananas' | 'enterprise') => {
    setIsDemoMode(true);
    setError(null);
    if (type === 'bananas') {
      setScanResult(SAMPLE_BANANAS_REPORT);
      setCurrentPath('[DEMO] world is going bananas.pbip');
    } else {
      setScanResult(SAMPLE_ENTERPRISE_REPORT);
      setCurrentPath('[DEMO] Enterprise Sales Analytics.pbip');
    }
    setActiveTab('dashboard');
  };

  // Check URL params on mount for explicit demo activation or path
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const demoParam = params.get('demo');
    if (demoParam === 'sample_bananas' || demoParam === 'bananas') {
      loadExplicitDemo('bananas');
    } else if (demoParam === 'sample_enterprise' || demoParam === 'enterprise') {
      loadExplicitDemo('enterprise');
    } else {
      const initialPath = params.get('path');
      if (initialPath) {
        scanPath(initialPath);
      }
    }
  }, []);

  const scanPath = async (targetPath: string, preserveTab: boolean = false) => {
    if (!targetPath || !targetPath.trim()) return;

    if (!hasBackend) {
      if (targetPath.startsWith('[DEMO]')) return;
      setError('To scan by local file path, run `pbiscan studio` from your terminal. On the web workbench, please use "Select Local .pbip Folder" or drag & drop below.');
      return;
    }

    setLoading(true);
    setError(null);
    setIsDemoMode(false);

    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath.trim() }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Scan failed (${res.status}: ${res.statusText})`);
      }

      const ct = res.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        throw new Error('Backend did not return valid JSON');
      }

      const data: ScanResult = await res.json();
      setScanResult(data);
      setCurrentPath(targetPath.trim());
      if (!preserveTab) {
        setActiveTab('dashboard');
      }
    } catch (err: any) {
      console.error('Scan error:', err);
      // Strictly set error state - NEVER fall back to demo data on failed real scans
      setError(err.message || 'Failed to scan report project');
      setScanResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Process dropped files or directory items client-side
  const handleFilesDropped = async (items: DataTransferItemList) => {
    setLoading(true);
    setError(null);
    const files: DroppedFile[] = [];
    let projectName = "uploaded_report.pbip";

    const traverseEntry = async (entry: any, path = "") => {
      if (entry.isFile) {
        const file: File = await new Promise((resolve) => entry.file(resolve));
        if (file.name.endsWith('.pbip')) {
          projectName = file.name;
        }
        if (
          file.name.endsWith('.tmdl') ||
          file.name.endsWith('.json') ||
          file.name.endsWith('.pbir') ||
          file.name.endsWith('.pbip') ||
          file.name.endsWith('.pbism')
        ) {
          const text = await file.text();
          files.push({
            name: file.name,
            path: path + "/" + file.name,
            content: text,
          });
        }
      } else if (entry.isDirectory) {
        if (entry.name.endsWith('.pbip') || entry.name.includes('.Report') || entry.name.includes('.SemanticModel')) {
          projectName = entry.name.split('.')[0] + ".pbip";
        }
        const dirReader = entry.createReader();
        const entries: any[] = await new Promise((resolve) => {
          dirReader.readEntries(resolve);
        });
        for (const child of entries) {
          await traverseEntry(child, path + "/" + entry.name);
        }
      }
    };

    try {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
          if (entry) {
            await traverseEntry(entry);
          } else {
            const file = item.getAsFile();
            if (file) {
              const text = await file.text();
              files.push({ name: file.name, path: file.name, content: text });
            }
          }
        }
      }

      if (files.length > 0) {
        const result = parseDroppedPbip(files, projectName);
        setScanResult(result);
        setCurrentPath(projectName);
        setActiveTab('dashboard');
      } else {
        setError('No valid TMDL or PBIP definition files found in dropped folder.');
      }
    } catch (e: any) {
      console.error('Error processing dropped folder:', e);
      setError('Failed to parse dropped PBIP files: ' + e.message);
    } finally {
      setLoading(false);
      setIsDragging(false);
    }
  };

  // Browser folder input selection
  const handleFolderInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    setLoading(true);
    setError(null);
    const files: DroppedFile[] = [];
    let projectName = "selected_project.pbip";

    for (let i = 0; i < e.target.files.length; i++) {
      const file = e.target.files[i];
      if (file.name.endsWith('.pbip')) {
        projectName = file.name;
      }
      if (
        file.name.endsWith('.tmdl') ||
        file.name.endsWith('.json') ||
        file.name.endsWith('.pbir') ||
        file.name.endsWith('.pbip')
      ) {
        const text = await file.text();
        files.push({
          name: file.name,
          path: file.webkitRelativePath || file.name,
          content: text,
        });
      }
    }

    if (files.length > 0) {
      const result = parseDroppedPbip(files, projectName);
      setScanResult(result);
      setCurrentPath(projectName);
      setActiveTab('dashboard');
    }
    setLoading(false);
  };

  // Native Windows File / Folder Picker with In-App Fallback
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
          return;
        }
      }
      // If on web or dialog canceled, open file picker
      if (folderInputRef.current) {
        folderInputRef.current.click();
      }
    } catch (err) {
      if (folderInputRef.current) {
        folderInputRef.current.click();
      }
    }
  };

  // Filter findings
  const filteredFindings = useMemo(() => {
    if (!scanResult?.findings) return [];
    return scanResult.findings.filter((f) => {
      if (selectedCategory !== 'all' && f.category !== selectedCategory) return false;
      if (selectedSeverity !== 'all' && f.severity !== selectedSeverity) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          f.title?.toLowerCase().includes(q) ||
          f.rule_id?.toLowerCase().includes(q) ||
          f.evidence?.toLowerCase().includes(q) ||
          (f.location && f.location.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [scanResult, selectedCategory, selectedSeverity, searchQuery]);

  return (
    <div 
      className="min-h-screen flex flex-col font-sans transition-colors duration-150 relative"
      style={{
        backgroundColor: 'var(--bg-canvas)',
        color: 'var(--text-primary)',
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget.contains(e.relatedTarget as Node)) return;
        setIsDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.items) {
          handleFilesDropped(e.dataTransfer.items);
        }
      }}
    >
      {/* Hidden Folder Picker input */}
      <input 
        type="file" 
        ref={folderInputRef}
        onChange={handleFolderInput}
        // @ts-ignore
        webkitdirectory=""
        directory=""
        multiple
        className="hidden" 
      />

      {/* Top Header */}
      <Header
        scanResult={scanResult}
        onNativeBrowse={() => handleNativeBrowse('file')}
        onResetToHome={() => {
          setScanResult(null);
          setCurrentPath('');
          setError(null);
          setIsDemoMode(false);
        }}
        theme={theme}
        onToggleTheme={toggleTheme}
        hasBackend={hasBackend}
      />

      {/* Explicit Demo Mode Warning Banner */}
      {isDemoMode && (
        <div 
          className="w-full py-2 px-4 text-center font-mono font-bold text-xs flex items-center justify-center gap-3 shadow-sm border-b"
          style={{
            backgroundColor: 'var(--accent)',
            color: '#FFFFFF',
            letterSpacing: '0.03em',
            borderColor: 'rgba(0,0,0,0.15)',
          }}
        >
          <span>⚠️ DEMO MODE — Viewing synthetic sample dataset</span>
          <button
            onClick={() => {
              setIsDemoMode(false);
              setScanResult(null);
              setCurrentPath('');
            }}
            className="px-2.5 py-0.5 rounded text-[11px] font-bold transition hover:opacity-90"
            style={{
              backgroundColor: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.4)',
              color: '#FFFFFF',
              cursor: 'pointer',
            }}
          >
            Exit Demo
          </button>
        </div>
      )}

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar (Visible when report is loaded) */}
        {scanResult && (
          <Sidebar
            activeTab={activeTab}
            onSelectTab={setActiveTab}
            findingsCount={scanResult.findings?.length || 0}
            tablesCount={scanResult.tables?.length || 0}
            measuresCount={scanResult.measures?.length || 0}
            pagesCount={scanResult.pages?.length || 0}
            onNewScan={() => {
              setScanResult(null);
              setCurrentPath('');
            }}
          />
        )}

        {/* Main Content Area */}
        <main 
          className="flex-1 overflow-y-auto p-6"
          style={{ backgroundColor: 'var(--bg-canvas)' }}
        >
          {error && (
            <div 
              className="max-w-4xl mx-auto mb-6 p-4 rounded border text-xs flex items-center justify-between font-mono"
              style={{
                backgroundColor: 'var(--severity-critical-bg)',
                borderColor: 'var(--severity-critical-border)',
                color: 'var(--severity-critical)',
              }}
            >
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span><strong>Scan Error:</strong> {error}</span>
              </div>
              <button
                onClick={() => {
                  if (folderInputRef.current) folderInputRef.current.click();
                }}
                className="underline font-bold ml-4 text-xs"
              >
                Select Folder
              </button>
            </div>
          )}

          {loading ? (
            <div className="h-full flex flex-col items-center justify-center py-28 text-center gap-3 font-mono">
              <RefreshCw className="w-7 h-7 animate-spin" style={{ color: 'var(--accent)' }} />
              <div className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                Analyzing Power BI Artifacts in Memory...
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Running 11 static model, DAX, and layout diagnostic rules
              </div>
            </div>
          ) : scanResult ? (
            /* Active Project Audit Dashboard */
            <div className="max-w-6xl mx-auto space-y-5">
              {/* Tab 1: Dashboard Overview */}
              {activeTab === 'dashboard' && (
                <div className="space-y-5">
                  <HealthScorecard
                    scores={scanResult.scores}
                    warningsCount={scanResult.warnings?.length || 0}
                  />

                  <FindingFilterBar
                    searchQuery={searchQuery}
                    onSearchChange={setSearchQuery}
                    selectedCategory={selectedCategory}
                    onCategoryChange={setSelectedCategory}
                    selectedSeverity={selectedSeverity}
                    onSeverityChange={setSelectedSeverity}
                    totalCount={scanResult.findings?.length || 0}
                    filteredCount={filteredFindings.length}
                  />

                  {/* Findings List */}
                  <div className="space-y-2.5">
                    <div className="text-xs font-mono font-medium uppercase tracking-wider px-1" style={{ color: 'var(--text-muted)' }}>
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
                      <div 
                        className="p-12 rounded border text-center space-y-2 font-mono"
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          borderColor: 'var(--border-hairline)',
                        }}
                      >
                        <CheckCircle2 className="w-7 h-7 mx-auto" style={{ color: 'var(--accent)' }} />
                        <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                          No issues found matching filters
                        </h4>
                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {scanResult.findings?.length === 0
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
                    tables={scanResult.tables || []}
                    relationships={scanResult.relationships || []}
                  />
                </div>
              )}

              {/* Tab 3: DAX Measures */}
              {activeTab === 'dax-explorer' && (
                <div>
                  <DaxExplorer
                    measures={scanResult.measures || []}
                    calcCols={scanResult.calculated_columns || []}
                    findings={scanResult.findings || []}
                  />
                </div>
              )}

              {/* Tab 4: Visual Pages */}
              {activeTab === 'pages' && (
                <div>
                  <PagesViewer
                    pages={scanResult.pages || []}
                    findings={scanResult.findings || []}
                  />
                </div>
              )}

              {/* Tab 5: Scan Comparison / Diff */}
              {activeTab === 'diff' && (
                <div>
                  <DiffViewer
                    initialBaselinePath={currentPath}
                    initialCurrentPath=""
                  />
                </div>
              )}

              {/* Tab 6: Safe Automated Remediation */}
              {activeTab === 'remediation' && (
                <div>
                  <RemediationPanel
                    projectPath={currentPath}
                    currentScore={scanResult.scores?.overall || 100}
                    findings={scanResult.findings || []}
                    hasBackend={hasBackend}
                    onProjectRefreshed={() => scanPath(currentPath, true)}
                  />
                </div>
              )}

              {/* Tab 7: Agent / MCP Integration */}
              {activeTab === 'agent' && (
                <div>
                  <AgentIntegrationPanel hasBackend={hasBackend} />
                </div>
              )}
            </div>
          ) : activeTab === 'diff' ? (
            /* Standalone Diff Screen (when no single scan is active) */
            <div className="space-y-4">
              <div className="max-w-5xl mx-auto flex items-center justify-between font-mono text-xs">
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className="px-3 py-1.5 rounded border flex items-center gap-1.5 transition"
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    borderColor: 'var(--border-hairline)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <ArrowRight className="w-3.5 h-3.5 rotate-180" />
                  <span>Return to Scanner Home</span>
                </button>
              </div>

              <DiffViewer />
            </div>
          ) : (
            /* Clean Landing Screen */
            <div className="max-w-2xl mx-auto py-12 text-center space-y-6">
              <div 
                className="w-12 h-12 rounded border flex items-center justify-center mx-auto shadow-sm"
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--accent)',
                }}
              >
                <FileText className="w-6 h-6" />
              </div>

              <div>
                <h2 
                  className="text-xl font-bold font-mono tracking-tight"
                  style={{ color: 'var(--text-primary)' }}
                >
                  Power BI Semantic Model &amp; DAX Diagnostic Engine
                </h2>
                <p 
                  className="text-xs mt-1.5 max-w-lg mx-auto leading-relaxed"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Drop your <span className="font-mono font-bold" style={{ color: 'var(--accent)' }}>.pbip</span> folder, compare historical scans, or select a test report below. 
                  <br />
                  <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    🔒 100% In-Browser &amp; Private — zero files uploaded to any server.
                  </span>
                </p>
              </div>

              {/* Interactive Drag & Drop Box */}
              <div 
                className="p-8 rounded border text-center space-y-4 transition-all duration-200 cursor-pointer"
                style={{
                  backgroundColor: isDragging ? 'var(--accent-muted)' : 'var(--bg-surface)',
                  borderColor: isDragging ? 'var(--accent)' : 'var(--border-strong)',
                  borderStyle: 'dashed',
                  borderWidth: '2px',
                }}
                onClick={() => {
                  handleNativeBrowse('folder');
                }}
              >
                <div className="flex flex-col items-center gap-2">
                  <div 
                    className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: 'var(--bg-canvas)',
                      color: 'var(--accent)',
                    }}
                  >
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <div className="font-mono font-bold text-xs" style={{ color: 'var(--text-primary)' }}>
                    Drag &amp; Drop .pbip folder here, or click to browse
                  </div>
                  <div className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    Reads TMDL/BIM definitions, PBIR layouts, and DAX measures locally
                  </div>
                </div>

                <div className="flex items-center justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleNativeBrowse('folder');
                    }}
                    className="py-2 px-4 rounded font-mono font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-sm"
                    style={{
                      backgroundColor: 'var(--accent)',
                      color: 'var(--bg-canvas)',
                    }}
                  >
                    <FolderOpen className="w-4 h-4" />
                    <span>Select Local .pbip Folder</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveTab('diff');
                    }}
                    className="py-2 px-4 rounded font-mono font-bold text-xs flex items-center justify-center gap-1.5 transition border"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'var(--border-strong)',
                      color: 'var(--text-primary)',
                    }}
                  >
                    <GitCompare className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                    <span>Compare Two Scans (Diff)</span>
                  </button>
                </div>
              </div>

              {/* Sample Projects for Instant Netlify Demo */}
              <div 
                className="pt-4 border-t text-left space-y-2.5 font-mono"
                style={{ borderColor: 'var(--border-hairline)' }}
              >
                <div className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Interactive Test Reports (1-Click Demo)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <button
                    onClick={() => loadExplicitDemo('bananas')}
                    className="p-3 rounded border text-left transition flex flex-col justify-between hover:border-[var(--accent)]"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'var(--border-hairline)',
                    }}
                  >
                    <div>
                      <div className="font-bold text-xs flex items-center justify-between" style={{ color: 'var(--text-primary)' }}>
                        <span>world is going bananas.pbip</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded border font-bold" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)' }}>
                          Score: 98
                        </span>
                      </div>
                      <div className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                        15 tables · 6 measures · 3 findings (TMDL)
                      </div>
                    </div>
                    <div className="mt-2 text-[10px] font-bold flex items-center gap-1" style={{ color: 'var(--accent)' }}>
                      <span>Launch Interactive Demo</span>
                      <ArrowRight className="w-3 h-3" />
                    </div>
                  </button>

                  <button
                    onClick={() => loadExplicitDemo('enterprise')}
                    className="p-3 rounded border text-left transition flex flex-col justify-between hover:border-[var(--accent)]"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'var(--border-hairline)',
                    }}
                  >
                    <div>
                      <div className="font-bold text-xs flex items-center justify-between" style={{ color: 'var(--text-primary)' }}>
                        <span>Enterprise Sales &amp; Margin.pbip</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded border font-bold" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-strong)', color: 'var(--severity-warning)' }}>
                          Score: 82
                        </span>
                      </div>
                      <div className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                        12 tables · 24 measures · 5 findings (Time Intelligence)
                      </div>
                    </div>
                    <div className="mt-2 text-[10px] font-bold flex items-center gap-1" style={{ color: 'var(--accent)' }}>
                      <span>Launch Interactive Audit</span>
                      <ArrowRight className="w-3 h-3" />
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* In-App File Browser Modal Fallback */}
      <FileBrowserModal
        isOpen={isBrowserOpen}
        onClose={() => setIsBrowserOpen(false)}
        onSelectProject={(path) => scanPath(path)}
      />
    </div>
  );
};
