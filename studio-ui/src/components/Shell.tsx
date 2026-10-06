import React, { useEffect, useRef, useState } from 'react';
import {
  Boxes, Download, FileStack, FolderOpen, GitCompareArrows, LayoutGrid, Moon, MoreHorizontal, Plug, RefreshCw, Sigma, Sun, Wrench,
} from 'lucide-react';
import type { ScanResult } from '../types';
import { Cube, Sheet } from './ui';

export type TabId = 'overview' | 'model' | 'measures' | 'pages' | 'fixes' | 'compare' | 'agent';

export const TABS: { id: TabId; label: string; icon: React.FC<any>; mobile?: boolean }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid, mobile: true },
  { id: 'model', label: 'Model', icon: Boxes, mobile: true },
  { id: 'measures', label: 'Measures', icon: Sigma, mobile: true },
  { id: 'pages', label: 'Report pages', icon: FileStack, mobile: true },
  { id: 'fixes', label: 'Fixes', icon: Wrench },
  { id: 'compare', label: 'Compare scans', icon: GitCompareArrows },
  { id: 'agent', label: 'Agent & MCP', icon: Plug },
];

export type Counts = Partial<Record<TabId, number | null>>;

export const Rail: React.FC<{
  tab: TabId; onTab: (t: TabId) => void; counts: Counts; hasBackend: boolean; onHome: () => void; ruleCount: number | null;
}> = ({ tab, onTab, counts, hasBackend, onHome, ruleCount }) => (
  <aside className="rail">
    <button className="brand" onClick={onHome} aria-label="pbiscan Studio home">
      <Cube /><b>pbiscan</b><span>studio</span>
    </button>
    <nav className="nav" aria-label="Studio sections">
      {TABS.map((t, i) => (
        <React.Fragment key={t.id}>
          {i === 4 && <div className="nav-sep" />}
          <button aria-current={tab === t.id ? 'page' : undefined} onClick={() => onTab(t.id)}>
            <t.icon aria-hidden="true" />{t.label}<span className="count">{counts[t.id] ?? ''}</span>
          </button>
        </React.Fragment>
      ))}
    </nav>
    <div className="rail-foot">
      {hasBackend ? (
        <><div><span className="dot" />Local engine connected</div><div>{location.host}{ruleCount ? ` · ${ruleCount} rules` : ''}</div></>
      ) : (
        <><div><span className="dot off" />Browser-only mode</div><div>Files never leave this tab</div></>
      )}
    </div>
  </aside>
);

export const TopBar: React.FC<{
  scan: ScanResult | null; path: string; mode: 'local' | 'browser' | 'demo' | null; scannedAt: string | null;
  hasBackend: boolean; loading: boolean; theme: 'light' | 'dark';
  onOpen: () => void; onRescan: () => void; onExport: (fmt: string) => void; onToggleTheme: () => void; onHome: () => void;
}> = ({ scan, path, mode, scannedAt, hasBackend, loading, theme, onOpen, onRescan, onExport, onToggleTheme, onHome }) => {
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [menu]);
  const canRescan = hasBackend && mode === 'local';
  return (
    <header className="topbar">
      <button className="btn-ghost m-brand" onClick={onHome} aria-label="Home" style={{ border: 0, background: 'none', padding: 0 }}><Cube className="m-brand" /></button>
      <div className="project">
        <h1>
          <span className="name">{scan ? scan.report_name.replace(/\.pbip$/i, '') : 'pbiscan Studio'}</span>
          {mode === 'demo' && <span className="chip">Sample project</span>}
          {mode === 'browser' && <span className="chip">Scanned in browser</span>}
        </h1>
        <div className="path">{scan ? (path || scan.source_path) : 'Power BI model and report checks'}</div>
      </div>
      <div className="top-actions">
        {scannedAt && <span className="meta">Scanned {scannedAt}</span>}
        <button className="btn d-only" onClick={onOpen}><FolderOpen aria-hidden="true" />Open project</button>
        {canRescan && (
          <div className="menu d-only" ref={menuRef}>
            <button className="btn" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu((m) => !m)}><Download aria-hidden="true" />Export</button>
            {menu && (
              <div className="menu-list" role="menu">
                {[['html', 'HTML report', '.html'], ['json', 'Audit JSON', '.json'], ['sarif', 'SARIF for code scanning', '.sarif'], ['junit', 'JUnit for CI', '.xml']].map(([fmt, label, ext]) => (
                  <button key={fmt} role="menuitem" onClick={() => { setMenu(false); onExport(fmt); }}>{label}<small>{ext}</small></button>
                ))}
              </div>
            )}
          </div>
        )}
        {canRescan && (
          <button className="btn btn-primary" onClick={onRescan} disabled={loading} aria-label="Rescan">
            <RefreshCw className={loading ? 'spin' : ''} aria-hidden="true" /><span className="btn-text">Rescan</span>
          </button>
        )}
        <button className="btn btn-ghost icon-btn" onClick={onToggleTheme} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
          {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
};

export const TabBar: React.FC<{ tab: TabId; onTab: (t: TabId) => void; findings: number; onOpen: () => void }> = ({ tab, onTab, findings, onOpen }) => {
  const [more, setMore] = useState(false);
  const mobileTabs = TABS.filter((t) => t.mobile);
  const moreTabs = TABS.filter((t) => !t.mobile);
  const inMore = moreTabs.some((t) => t.id === tab);
  return (
    <>
      <nav className="tabbar" aria-label="Studio sections">
        {mobileTabs.map((t) => (
          <button key={t.id} aria-current={tab === t.id ? 'page' : undefined} onClick={() => onTab(t.id)}>
            {t.id === 'overview' && findings > 0 && <span className="badge">{findings}</span>}
            <t.icon aria-hidden="true" />{t.id === 'pages' ? 'Pages' : t.label}
          </button>
        ))}
        <button aria-current={inMore ? 'page' : undefined} aria-haspopup="dialog" onClick={() => setMore(true)}>
          <MoreHorizontal aria-hidden="true" />More
        </button>
      </nav>
      <Sheet open={more} onClose={() => setMore(false)} label="More sections" className="panel">
        <div className="more-list">
          {moreTabs.map((t) => (
            <button key={t.id} onClick={() => { setMore(false); onTab(t.id); }}><t.icon aria-hidden="true" />{t.label}</button>
          ))}
          <button onClick={() => { setMore(false); onOpen(); }}><FolderOpen aria-hidden="true" />Open another project</button>
        </div>
      </Sheet>
    </>
  );
};
