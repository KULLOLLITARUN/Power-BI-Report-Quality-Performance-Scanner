import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, Folder, FileBox, X } from 'lucide-react';
import type { BrowseResult } from '../types';
import { apiFetch } from '../utils/api';

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
}

/** Folder browser backed by the local engine's /api/browse. */
export const FileBrowserModal: React.FC<Props> = ({ open, onClose, onSelect }) => {
  const [data, setData] = useState<BrowseResult | null>(null);
  const [path, setPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const go = async (target?: string) => {
    setLoading(true); setError(null);
    try {
      const res = await apiFetch('/api/browse', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: target }) });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Could not open that folder (${res.status}).`);
      setData(body); setPath(body.current_path);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (open) go(); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    dialogRef.current?.querySelector<HTMLInputElement>('input')?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Open a .pbip project" ref={dialogRef}>
        <div className="panel-head">
          <h3>Open a .pbip project</h3><span className="spacer" />
          <button className="btn btn-ghost icon-btn" onClick={onClose} aria-label="Close"><X aria-hidden="true" /></button>
        </div>
        <form className="filters" onSubmit={(e) => { e.preventDefault(); go(path); }}>
          <button type="button" className="btn icon-btn" disabled={!data?.parent_path || loading} onClick={() => data?.parent_path && go(data.parent_path)} aria-label="Up one folder"><ArrowUp aria-hidden="true" /></button>
          <label className="sr-only" htmlFor="fb-path">Folder path</label>
          <input id="fb-path" className="input mono" style={{ flex: 1 }} value={path} onChange={(e) => setPath(e.target.value)} />
          <button className="btn" type="submit" disabled={loading}>Go</button>
        </form>
        <div style={{ overflowY: 'auto', flex: 1, minHeight: 200 }}>
          {error && <div className="notice error" style={{ margin: 12 }}><span className="grow">{error}</span></div>}
          {loading && !data ? <div className="empty">Loading…</div> : data && (
            <>
              {data.pbip_projects.map((p) => (
                <button key={p.path} className="fb-row project" onClick={() => { onSelect(p.path); onClose(); }}>
                  <FileBox aria-hidden="true" />{p.name}<span className="mono">open</span>
                </button>
              ))}
              {data.directories.map((d) => (
                <button key={d.path} className="fb-row" onClick={() => go(d.path)}><Folder aria-hidden="true" />{d.name}</button>
              ))}
              {!data.pbip_projects.length && !data.directories.length && <div className="empty">This folder is empty.</div>}
            </>
          )}
        </div>
        <div className="list-foot"><span className="muted" style={{ fontSize: 12.5 }}>Projects (.pbip) are listed first. Pick one to scan it.</span></div>
      </div>
    </div>
  );
};
