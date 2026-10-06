import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Maximize2, Minus, MoveRight, Plus, RotateCcw, X } from 'lucide-react';
import type { AuditFinding, PageInfo, ScanResult } from '../types';
import { ModelScene, type ReportLayer } from '../lib/scene';
import { classifyTables, findingTargets, isAutoDateTable, readingOrder, severityIndex, visualTables, VISUAL_LIMIT } from '../lib/model';
import { prefersReducedMotion } from '../lib/motion';

export interface MapFocus {
  tables: string[];
  rels: string[];
  caption?: string;
}

interface Props {
  scan: ScanResult;
  findings: AuditFinding[];           // open findings, used for colouring
  focus?: MapFocus | null;            // null = no focus
  marked?: string | null;
  onTableClick?: (name: string | null) => void;
  page?: PageInfo | null;             // show the report layer for this page
  selectedVisual?: number | null;
  onVisualClick?: (index: number | null) => void;
  title?: string;
  tall?: boolean;
  showLegend?: boolean;
}

/** React wrapper around the three.js ModelScene, with labels, tooltip, tools and legend. */
export const ModelMap: React.FC<Props> = ({
  scan, findings, focus = null, marked = null, onTableClick, page = null, selectedVisual = null, onVisualClick,
  title = 'Model', tall = false, showLegend = true,
}) => {
  const stageRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<ModelScene | null>(null);
  const cbRef = useRef({ onTableClick, onVisualClick });
  cbRef.current = { onTableClick, onVisualClick };
  const [flow, setFlow] = useState(() => !prefersReducedMotion());
  const [expanded, setExpanded] = useState(false);
  const [failed, setFailed] = useState(() => !ModelScene.supported());

  const tables = useMemo(() => (scan.tables || []).filter((t) => !isAutoDateTable(t.name)), [scan.tables]);
  const autoDateCount = (scan.tables || []).length - tables.length;
  const relationships = useMemo(() => {
    const names = new Set(tables.map((t) => t.name));
    return (scan.relationships || []).filter((r) => names.has(r.from_table) && names.has(r.to_table));
  }, [scan.relationships, tables]);

  const sceneData = useMemo(() => {
    const roles = classifyTables(tables, relationships);
    const sev = severityIndex(scan, findings);
    const counts = new Map<string, number>();
    for (const f of findings) for (const t of findingTargets(f, scan).tables) counts.set(t, (counts.get(t) ?? 0) + 1);
    let report: ReportLayer | null = null;
    if (page) {
      const visuals = page.visuals || [];
      const order = readingOrder(visuals);
      const over = new Set<number>();
      if (visuals.length > VISUAL_LIMIT) order.slice(VISUAL_LIMIT).forEach((v) => over.add(visuals.indexOf(v)));
      report = { page, visualTables: visuals.map((v) => visualTables(v, scan)), overLimit: over };
    }
    return { tables, relationships, roles, tableSeverity: sev.tables, relSeverity: sev.rels, findingCounts: counts, report };
  }, [scan, tables, relationships, findings, page]);

  const flagged = sceneData.relSeverity.size;

  // Build / rebuild the scene when its data changes
  useEffect(() => {
    if (failed || !stageRef.current || !labelsRef.current || !tipRef.current || !tables.length) return;
    let scene: ModelScene;
    try {
      scene = new ModelScene(stageRef.current, labelsRef.current, tipRef.current, sceneData, {
        onTableClick: (n) => cbRef.current.onTableClick?.(n),
        onVisualClick: (i) => cbRef.current.onVisualClick?.(i),
      });
    } catch (err) {
      console.error('3D map failed to start', err);
      setFailed(true);
      return;
    }
    sceneRef.current = scene;
    scene.setFlow(flow);
    return () => { scene.dispose(); sceneRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneData, failed]);

  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    if (focus) s.setFocus(focus.tables, focus.rels); else s.setFocus(null);
  }, [focus, sceneData]);
  useEffect(() => { sceneRef.current?.setMarked(marked); }, [marked, sceneData]);
  useEffect(() => { sceneRef.current?.setSelectedVisual(selectedVisual); }, [selectedVisual, sceneData]);
  useEffect(() => { sceneRef.current?.setFlow(flow); }, [flow]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setExpanded(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [expanded]);

  const summary = `${tables.length} tables · ${relationships.length} relationships${flagged ? ` · ${flagged} flagged` : ''}${autoDateCount ? ` · ${autoDateCount} auto date tables hidden` : ''}`;

  return (
    <>
      {expanded && <div className="backdrop" onClick={() => setExpanded(false)} />}
      <div className={`map panel${expanded ? ' expanded' : ''}`}>
        <div className="map-head">
          <h2>{title}</h2>
          <span>{summary}</span>
        </div>
        <div ref={stageRef} className={`map-stage${tall ? ' tall' : ''}`}>
          {failed ? (
            <div className="nogl">This browser has WebGL turned off, so the 3D map is unavailable. The table list still works.</div>
          ) : !tables.length ? (
            <div className="nogl">This project has no model tables to draw.</div>
          ) : null}
          <div ref={labelsRef} className="map-labels" />
          <div ref={tipRef} className="tip" hidden role="tooltip" />
          {!failed && tables.length > 0 && (
            <div className="map-tools">
              <button type="button" aria-pressed={flow} title="Show filter direction" aria-label="Show filter direction" onClick={() => setFlow((f) => !f)}><MoveRight /></button>
              <button type="button" title="Zoom in" aria-label="Zoom in" onClick={() => sceneRef.current?.zoom(1)}><Plus /></button>
              <button type="button" title="Zoom out" aria-label="Zoom out" onClick={() => sceneRef.current?.zoom(-1)}><Minus /></button>
              <button type="button" title="Reset view" aria-label="Reset view" onClick={() => sceneRef.current?.reset()}><RotateCcw /></button>
              <button type="button" aria-pressed={expanded} title={expanded ? 'Close large map' : 'Open large map'} aria-label={expanded ? 'Close large map' : 'Open large map'} onClick={() => setExpanded((x) => !x)}>
                {expanded ? <X /> : <Maximize2 />}
              </button>
            </div>
          )}
          {focus?.caption && <div className="map-caption">{focus.caption}</div>}
        </div>
        {showLegend && (
          <div className="map-foot">
            <span><Swatch v="--t-fact" />fact</span>
            <span><Swatch v="--t-dim" />dimension</span>
            <span><Swatch v="--t-date" />date</span>
            {page && <span><Swatch v="--t-slicer" />slicer</span>}
            <span><svg viewBox="0 0 24 24"><path d="M12 3 19 12 12 21 5 12z" fill="var(--sev-high)" /></svg>worst finding</span>
            <span><svg className="line" viewBox="0 0 22 6"><line x1="0" y1="3" x2="22" y2="3" stroke="var(--sev-high)" strokeWidth="2" strokeDasharray="4 3" /></svg>many-to-many / inactive</span>
            <span>box size = columns · dots = filter direction{page ? ' · threads = tables a visual reads' : ''}</span>
          </div>
        )}
      </div>
    </>
  );
};

const Swatch: React.FC<{ v: string }> = ({ v }) => (
  <svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" fill={`var(${v})`} stroke={`var(${v}-edge, var(--rule-strong))`} strokeWidth="1.5" /></svg>
);
