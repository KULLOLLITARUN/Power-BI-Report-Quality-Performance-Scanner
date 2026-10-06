import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, CircleX } from 'lucide-react';
import type { AuditFinding, ScanResult } from './types';
import { apiFetch } from './utils/api';
import { useTheme } from './hooks/useTheme';
import { parseDroppedPbip } from './engine/clientScanner';
import { SAMPLE_BANANAS_REPORT, SAMPLE_ENTERPRISE_REPORT, sampleHistory } from './data/sampleReports';
import { readDataTransfer, readFileList, type ReadFolderResult } from './lib/files';
import { recordScan, shortTime, type HistoryPoint } from './lib/history';
import { Rail, TabBar, TopBar, TABS, type TabId } from './components/Shell';
import { FileBrowserModal } from './components/FileBrowserModal';
import { ToastProvider, useToast } from './components/ui';
import { Landing } from './screens/Landing';
import { Overview } from './screens/Overview';
import { ModelScreen } from './screens/ModelScreen';
import { MeasuresScreen } from './screens/MeasuresScreen';
import { PagesScreen } from './screens/PagesScreen';
import { FixesScreen } from './screens/FixesScreen';
import { CompareScreen } from './screens/CompareScreen';
import { AgentScreen } from './screens/AgentScreen';

type Mode = 'local' | 'browser' | 'demo';
const TAB_IDS = new Set<string>(TABS.map((t) => t.id));
const tabFromHash = (): TabId => {
  const h = window.location.hash.replace('#', '');
  return (TAB_IDS.has(h) ? h : 'overview') as TabId;
};

export const App: React.FC = () => (
  <ToastProvider>
    <Studio />
  </ToastProvider>
);

const Studio: React.FC = () => {
  const toast = useToast();
  const { theme, toggleTheme } = useTheme();
  const [hasBackend, setHasBackend] = useState(false);
  const [healthChecked, setHealthChecked] = useState(false);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [path, setPath] = useState('');
  const [mode, setMode] = useState<Mode | null>(null);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTabState] = useState<TabId>(tabFromHash);
  const [dragging, setDragging] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [measureTarget, setMeasureTarget] = useState<string | null>(null);
  const [pageTarget, setPageTarget] = useState<string | null>(null);
  const [ruleCount, setRuleCount] = useState<number | null>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);

  const setTab = useCallback((t: TabId) => {
    setTabState(t);
    if (window.location.hash !== `#${t}`) history_replace(`#${t}`);
    window.scrollTo({ top: 0 });
  }, []);
  useEffect(() => {
    const onHash = () => setTabState(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // ---- local engine detection
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/health');
        const ok = res.ok && (res.headers.get('content-type') || '').includes('application/json') && (await res.json())?.status === 'ok';
        setHasBackend(!!ok);
      } catch {
        setHasBackend(false);
      } finally {
        setHealthChecked(true);
      }
    })();
  }, []);

  useEffect(() => {
    if (!hasBackend) return;
    apiFetch('/api/mcp/rules').then((r) => (r.ok ? r.json() : null)).then((d) => d?.rules && setRuleCount(Object.keys(d.rules).length)).catch(() => {});
  }, [hasBackend]);

  const finishScan = useCallback((result: ScanResult, where: string, how: Mode, keepTab: boolean) => {
    setScan(result);
    setPath(where);
    setMode(how);
    setScannedAt(shortTime(new Date().toISOString()));
    setHistory(how === 'demo' ? sampleHistory(result) : recordScan(where, result));
    setError(null);
    if (!keepTab) setTab('overview');
  }, [setTab]);

  const scanPath = useCallback(async (target: string, keepTab = false) => {
    const p = target.trim();
    if (!p) return;
    setLoading(true); setError(null);
    try {
      const res = await apiFetch('/api/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `The scan failed (${res.status}).`);
      if (!data) throw new Error('The local engine did not return a scan result.');
      finishScan(data, p, 'local', keepTab);
    } catch (e: any) {
      setError(e.message || 'The scan failed.');
    } finally {
      setLoading(false);
    }
  }, [finishScan]);

  const scanFiles = useCallback((read: ReadFolderResult) => {
    if (!read.files.length) {
      setError('That folder has no Power BI project files (.pbip, .tmdl, .bim or report JSON). Pick the folder that contains the .pbip file.');
      return;
    }
    try {
      const result = parseDroppedPbip(read.files, read.projectName);
      finishScan(result, read.projectName, 'browser', false);
    } catch (e: any) {
      setError(`Could not read this project: ${e.message}`);
    }
  }, [finishScan]);

  const loadDemo = (which: 'enterprise' | 'bananas', keepTab = false) => {
    const data = which === 'bananas' ? SAMPLE_BANANAS_REPORT : SAMPLE_ENTERPRISE_REPORT;
    finishScan(data, data.source_path, 'demo', keepTab);
  };

  // ---- initial URL. ?demo= loads at once; ?path= waits for the engine check, then scans.
  useEffect(() => {
    const demo = new URLSearchParams(window.location.search).get('demo');
    if (demo) loadDemo(demo.includes('banana') ? 'bananas' : 'enterprise', true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const booted = useRef(false);
  useEffect(() => {
    if (!healthChecked || booted.current) return;
    booted.current = true;
    const params = new URLSearchParams(window.location.search);
    const initialPath = params.get('path');
    if (initialPath && !params.get('demo')) {
      if (hasBackend) scanPath(initialPath, true);
      else setError('Scanning a path needs the local engine. Start Studio with `pbiscan studio <path>`, or open the folder here instead.');
    }
  }, [healthChecked, hasBackend, scanPath]);

  const goHome = () => { setScan(null); setMode(null); setPath(''); setError(null); setTab('overview'); };

  // ---- opening projects
  const openProject = async () => {
    if (!hasBackend) { folderInput.current?.click(); return; }
    try {
      const res = await apiFetch('/api/native-dialog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'folder' }) });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.path && !data.canceled) { scanPath(data.path); return; }
      if (res.ok && data.canceled) return;
      setBrowserOpen(true); // no native dialog on this machine: use the in-app browser
    } catch {
      setBrowserOpen(true);
    }
  };

  const onFolderPicked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (!list?.length) return;
    setLoading(true);
    try {
      scanFiles(await readFileList(list));
    } catch (err: any) {
      setError(`Could not read the folder: ${err.message}`);
    } finally {
      setLoading(false);
      e.target.value = '';
    }
  };

  // ---- drag and drop anywhere on the page
  useEffect(() => {
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes('Files');
    const enter = (e: DragEvent) => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth.current++; setDragging(true); };
    const over = (e: DragEvent) => { if (hasFiles(e)) e.preventDefault(); };
    const leave = () => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDragging(false); };
    const drop = async (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepth.current = 0; setDragging(false);
      if (!e.dataTransfer?.items) return;
      setLoading(true);
      try {
        scanFiles(await readDataTransfer(e.dataTransfer.items));
      } catch (err: any) {
        setError(`Could not read the dropped folder: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };
    window.addEventListener('dragenter', enter);
    window.addEventListener('dragover', over);
    window.addEventListener('dragleave', leave);
    window.addEventListener('drop', drop);
    return () => {
      window.removeEventListener('dragenter', enter);
      window.removeEventListener('dragover', over);
      window.removeEventListener('dragleave', leave);
      window.removeEventListener('drop', drop);
    };
  }, [scanFiles]);

  // ---- actions on a loaded scan
  const suppress = async (f: AuditFinding) => {
    try {
      const res = await apiFetch('/api/suppress', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: path, rule_id: f.rule_id, location: f.location || '', reason: 'Suppressed in pbiscan Studio' }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Suppressing failed (${res.status}).`);
      toast(`Suppressed ${f.rule_id}. ${data.message ?? ''}`.trim());
      await scanPath(path, true);
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const exportAs = async (format: string) => {
    try {
      const res = await apiFetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_path: path, format }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Export failed (${res.status}).`);
      const url = URL.createObjectURL(new Blob([data.content], { type: data.mime || 'text/plain' }));
      const a = document.createElement('a');
      a.href = url; a.download = data.filename || `pbiscan.${format}`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(`Saved ${a.download}.`);
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const openFinding = useCallback(() => setTab('overview'), [setTab]);
  const openMeasure = useCallback((name: string) => { setMeasureTarget(name); setTab('measures'); }, [setTab]);
  const openPage = useCallback((name: string) => { setPageTarget(name); setTab('pages'); }, [setTab]);

  const openFindings = useMemo(() => (scan?.findings || []).filter((f) => !f.suppressed), [scan]);
  const counts = scan ? {
    overview: openFindings.length,
    model: (scan.tables || []).length,
    measures: (scan.measures || []).length,
    pages: (scan.pages || []).length,
  } : {};

  useEffect(() => {
    document.title = scan ? `${scan.report_name.replace(/\.pbip$/i, '')} · pbiscan Studio` : 'pbiscan Studio';
  }, [scan]);

  const standalone = !scan && (tab === 'compare' || tab === 'agent');

  let body: React.ReactNode;
  if (loading) {
    body = (
      <div className="loading" role="status">
        <div className="bars" aria-hidden="true"><i /><i /><i /><i /></div>
        <strong>Reading the model, DAX and report pages…</strong>
        <span className="muted">Large models can take a few seconds.</span>
      </div>
    );
  } else if (standalone) {
    body = (
      <>
        <div><button className="btn btn-ghost" onClick={() => setTab('overview')}><ArrowLeft aria-hidden="true" />Back</button></div>
        {tab === 'compare' ? <CompareScreen hasBackend={hasBackend} /> : <AgentScreen hasBackend={hasBackend} onRuleCount={setRuleCount} />}
      </>
    );
  } else if (!scan) {
    body = <Landing hasBackend={hasBackend} dragging={dragging} onOpen={openProject} onBrowse={() => setBrowserOpen(true)} onCompare={() => setTab('compare')} onDemo={(w) => loadDemo(w)} />;
  } else {
    const isLocal = mode === 'local';
    body = {
      overview: <Overview scan={scan} history={history} canSuppress={hasBackend && isLocal} onSuppress={suppress}
                          onOpenFixes={() => setTab('fixes')} onOpenMeasure={openMeasure} onOpenPage={openPage} />,
      model: <ModelScreen scan={scan} findings={openFindings} onOpenFinding={openFinding} onOpenMeasure={openMeasure} />,
      measures: <MeasuresScreen scan={scan} findings={openFindings} initial={measureTarget} onOpenFinding={openFinding} onOpenPage={openPage} />,
      pages: <PagesScreen scan={scan} findings={openFindings} initial={pageTarget} onOpenFinding={openFinding} />,
      fixes: <FixesScreen projectPath={path} findings={openFindings} hasBackend={hasBackend} isLocal={isLocal} onApplied={() => scanPath(path, true)} />,
      compare: <CompareScreen hasBackend={hasBackend} initialBaseline={isLocal ? path : ''} />,
      agent: <AgentScreen hasBackend={hasBackend} onRuleCount={setRuleCount} />,
    }[tab];
  }

  return (
    <div className={`shell${scan ? '' : ' no-rail'}`}>
      <input ref={folderInput} type="file" className="sr-only" tabIndex={-1} aria-hidden="true" onChange={onFolderPicked}
             {...({ webkitdirectory: '', directory: '' } as any)} multiple />
      {scan && <Rail tab={tab} onTab={setTab} counts={counts} hasBackend={hasBackend} onHome={goHome} ruleCount={ruleCount} />}
      <div className="main-col">
        {mode === 'demo' && (
          <div className="demo-banner">Sample project with made-up data. Open your own project to scan it.
            <button className="btn" onClick={goHome}>Close sample</button>
          </div>
        )}
        <TopBar scan={scan} path={path} mode={mode} scannedAt={scannedAt} hasBackend={hasBackend} loading={loading} theme={theme}
                onOpen={openProject} onRescan={() => scanPath(path, true)} onExport={exportAs} onToggleTheme={toggleTheme} onHome={goHome} />
        <main className="content" id="main">
          {error && (
            <div className="notice error" role="alert">
              <CircleX aria-hidden="true" />
              <span className="grow"><strong>Scan failed.</strong> {error}</span>
              <button className="btn btn-sm" onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}
          {body}
        </main>
      </div>
      {scan && <TabBar tab={tab} onTab={setTab} findings={openFindings.length} onOpen={openProject} />}
      <FileBrowserModal open={browserOpen} onClose={() => setBrowserOpen(false)} onSelect={(p) => scanPath(p)} />
    </div>
  );
};

function history_replace(hash: string) {
  try {
    window.history.replaceState(window.history.state, '', hash);
  } catch {
    window.location.hash = hash;
  }
}

