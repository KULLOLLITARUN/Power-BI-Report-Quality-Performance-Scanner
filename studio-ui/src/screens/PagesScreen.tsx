import React, { useEffect, useMemo, useState } from 'react';
import { EyeOff, Layers, Square } from 'lucide-react';
import type { AuditFinding, PageInfo, ScanResult, VisualInfo } from '../types';
import { findingTargets, readingOrder, visualTables, VISUAL_LIMIT } from '../lib/model';
import { sortFindings } from '../lib/severity';
import { ModelMap } from '../components/ModelMap';
import { SevMarker, SevTag, useMobile } from '../components/ui';

export const PagesScreen: React.FC<{
  scan: ScanResult; findings: AuditFinding[]; initial: string | null; onOpenFinding: (f: AuditFinding) => void;
}> = ({ scan, findings, initial, onOpenFinding }) => {
  const mobile = useMobile();
  const pages = scan.pages || [];
  const [pageName, setPageName] = useState<string | null>(initial ?? pages[0]?.name ?? null);
  const [view, setView] = useState<'3d' | '2d'>(mobile ? '2d' : '3d');
  const [visual, setVisual] = useState<number | null>(null);
  const [table, setTable] = useState<string | null>(null);

  useEffect(() => { if (initial) setPageName(initial); }, [initial]);
  useEffect(() => { setVisual(null); setTable(null); }, [pageName]);

  const page = pages.find((p) => p.name === pageName) ?? pages[0] ?? null;
  const visuals = page?.visuals || [];
  const hasLayout = visuals.length > 0 && visuals.some((v) => v.width > 0 && v.height > 0);
  const over = useMemo(() => {
    const s = new Set<number>();
    if (visuals.length > VISUAL_LIMIT) readingOrder(visuals).slice(VISUAL_LIMIT).forEach((v) => s.add(visuals.indexOf(v)));
    return s;
  }, [visuals]);
  const pageFindings = useMemo(
    () => sortFindings(findings.filter((f) => f.category === 'report' && page && findingTargets(f, scan).page === page.name)),
    [findings, page, scan],
  );
  const findingsByPage = useMemo(() => {
    const m = new Map<string, AuditFinding[]>();
    for (const f of findings) {
      const p = f.category === 'report' ? findingTargets(f, scan).page : null;
      if (p) m.set(p, [...(m.get(p) ?? []), f]);
    }
    return m;
  }, [findings, scan]);
  const sel: VisualInfo | null = visual !== null ? visuals[visual] ?? null : null;
  const selTables = sel ? visualTables(sel, scan) : [];
  const orderedVisuals = useMemo(() => readingOrder(visuals), [visuals]);
  const selectedOrder = useMemo(() => {
    if (!sel) return null;
    const idx = orderedVisuals.indexOf(sel);
    return idx !== -1 ? idx + 1 : null;
  }, [sel, orderedVisuals]);

  const bloatInfo = useMemo(() => {
    if (!page) return null;
    const hasVisualBloat = pageFindings.some((f) => f.rule_id === 'REPORT_VISUAL_BLOAT') || page.visual_count > VISUAL_LIMIT;
    const hasSlicerBloat = pageFindings.some((f) => f.rule_id === 'REPORT_SLICER_BLOAT') || page.slicer_count > 6;
    if (!hasVisualBloat && !hasSlicerBloat) return null;
    return {
      hasVisualBloat,
      hasSlicerBloat,
      title: hasVisualBloat && hasSlicerBloat
        ? 'Visual & slicer bloat notice:'
        : hasSlicerBloat
        ? 'Slicer bloat notice:'
        : 'Visual bloat notice:',
      message: hasVisualBloat && hasSlicerBloat
        ? `Page has ${page.visual_count} visuals (limit ${VISUAL_LIMIT}) and ${page.slicer_count} slicers (limit 6).`
        : hasSlicerBloat
        ? `Page has ${page.slicer_count} slicers (exceeds limit of 6).`
        : `Page has ${page.visual_count} visuals (exceeds limit of ${VISUAL_LIMIT}).`,
    };
  }, [pageFindings, page]);

  if (!pages.length) {
    return (
      <>
        <div className="page-head"><div><h2>Report pages</h2></div></div>
        <div className="panel empty"><strong>No report pages</strong><span>This project has a semantic model but no report definition pbiscan could read.</span></div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Report pages</h2>
          <p>Each page floats above the model. Threads run from every visual down to the tables it queries, so you can see which pages lean on which tables.</p>
        </div>
        <div className="actions">
          <div className="seg" role="group" aria-label="View">
            <button aria-pressed={view === '3d'} onClick={() => setView('3d')}><Layers size={13} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 5 }} />Over the model</button>
            <button aria-pressed={view === '2d'} onClick={() => setView('2d')}><Square size={13} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 5 }} />Page layout</button>
          </div>
        </div>
      </div>

      <div className="split">
        <section className="panel" aria-label="Pages">
          <div className="panel-head"><h3>{pages.length} page{pages.length === 1 ? '' : 's'}</h3></div>
          <div className="side-list" role="listbox" aria-label="Pages">
            {pages.map((p) => {
              const fs = findingsByPage.get(p.name) ?? [];
              return (
                <div key={p.name} className="item" role="option" tabIndex={0} aria-selected={page?.name === p.name}
                     onClick={() => setPageName(p.name)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPageName(p.name); } }}>
                  <span>{fs.length ? <SevMarker sev={sortFindings(fs)[0].severity} size={11} /> : null}</span>
                  <span className="nm">{p.display_name}</span>
                  <span className="flags">{p.is_hidden && <EyeOff size={13} aria-label="hidden page" />}</span>
                  <span className="sub">{p.visual_count} visuals · {p.slicer_count} slicers{p.visual_count > VISUAL_LIMIT ? ` · over ${VISUAL_LIMIT}` : ''}</span>
                </div>
              );
            })}
          </div>
        </section>

        <div style={{ display: 'grid', gap: 14, minWidth: 0 }}>
          {page && !hasLayout && (
            <div className="notice"><Layers aria-hidden="true" /><span className="grow">
              {visuals.length === 0 && page.visual_count > 0
                ? 'This scan has no visual positions. Rescan with this version of pbiscan to draw the page.'
                : 'This page has no visuals to draw.'}
            </span></div>
          )}
          {page && view === '3d' && bloatInfo && hasLayout && (
            <div className="notice" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px' }}>
              <span style={{ fontSize: 13 }}>
                <strong>{bloatInfo.title}</strong> {bloatInfo.message}
              </span>
              <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => setView('2d')}>
                <Square size={12} aria-hidden="true" style={{ marginRight: 5 }} />
                See 2D layout
              </button>
            </div>
          )}
          {page && view === '3d' && (
            <ModelMap
              scan={scan} findings={findings} page={hasLayout ? page : null} title={page.display_name}
              selectedVisual={visual} onVisualClick={setVisual} marked={table} onTableClick={setTable} tall
            />
          )}
          {page && view === '2d' && hasLayout && <PageCanvas page={page} over={over} selected={visual} onSelect={setVisual} />}

          <div className="grid-2">
            <section className="panel" aria-label="Selected visual">
              <div className="panel-head">
                <h3>{sel ? sel.visual_type : 'Visual'}</h3>
                {selectedOrder !== null && <span className="chip" title="Layout position order (geometric top-to-bottom, left-to-right)">#{selectedOrder} in layout</span>}
                {sel?.is_slicer && <span className="chip">slicer</span>}
                {sel?.hidden && <span className="chip">hidden</span>}
                {visual !== null && over.has(visual) && <span className="chip warn">over limit</span>}
              </div>
              <div className="panel-body">
                {sel ? (
                  <dl className="kv">
                    <dt>reads</dt><dd>{selTables.length ? selTables.join(', ') : 'no model tables'}</dd>
                    <dt>measures</dt><dd className="mono" style={{ fontSize: 12 }}>{sel.measure_refs.length ? sel.measure_refs.join(', ') : 'none'}</dd>
                    {sel.fields_used && sel.fields_used.length > 0 && (
                      <><dt>fields</dt><dd className="mono" style={{ fontSize: 12 }}>{sel.fields_used.join(', ')}</dd></>
                    )}
                    <dt>position</dt><dd className="mono" style={{ fontSize: 12 }}>x {Math.round(sel.x)} · y {Math.round(sel.y)} · {Math.round(sel.width)} × {Math.round(sel.height)}</dd>
                    <dt>layout pos</dt><dd style={{ fontSize: 12 }}>#{selectedOrder} (geometric order: top-to-bottom, left-to-right)</dd>
                  </dl>
                ) : <p className="muted" style={{ margin: 0, fontSize: 13 }}>Click a visual to see which tables and measures it reads.</p>}
              </div>
            </section>
            <section className="panel" aria-label="Page findings">
              <div className="panel-head"><h3>Page findings</h3><span className="spacer" /><span className="label">{pageFindings.length}</span></div>
              <div className="panel-body">
                {pageFindings.length ? pageFindings.map((f, i) => (
                  <button key={i} className="btn btn-ghost" style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => onOpenFinding(f)}>
                    <SevMarker sev={f.severity} /><span style={{ flex: 1 }}>{f.title}</span><SevTag sev={f.severity} />
                  </button>
                )) : <p className="muted" style={{ margin: 0, fontSize: 13 }}>No findings on this page.</p>}
              </div>
            </section>
          </div>
        </div>
      </div>
    </>
  );
};

const SLICER_TYPES = new Set(['slicer', 'advancedslicer', 'hierarchyslicer', 'chicslicer']);
const CARD_TYPES = new Set(['card', 'multirowcard', 'kpi', 'gauge', 'cardvisual', 'scorecard']);
const TABLE_TYPES = new Set(['tableex', 'matrix', 'pivottable', 'table']);
const CONTAINER_TYPES = new Set(['textbox', 'shape', 'basicshape', 'actionbutton', 'image', 'group', 'line']);
const CHART_TYPES = new Set([
  'barchart', 'clusteredbarchart', 'hundredpercentstackedbarchart', 'stackedbarchart',
  'columnchart', 'clusteredcolumnchart', 'hundredpercentstackedcolumnchart', 'stackedcolumnchart',
  'linechart', 'areachart', 'stackedareachart', 'linestackedcolumncombochart', 'lineclusteredcolumncombochart',
  'piechart', 'donutchart', 'scatterchart', 'bubblechart',
  'treemap', 'waterfallchart', 'funnel', 'ribbonchart',
  'map', 'filledmap', 'shapemap', 'azuremap', 'esrimap',
  'decompositiontreevisual', 'keydriversvisual',
]);

function visualCategory(type: string, isSlicer?: boolean): string {
  if (isSlicer) return 'cat-slicer';
  const t = (type || '').toLowerCase().trim();
  if (SLICER_TYPES.has(t) || t.endsWith('slicer')) return 'cat-slicer';
  if (CARD_TYPES.has(t) || t.endsWith('card') || t.endsWith('kpi') || t.endsWith('gauge')) return 'cat-card';
  if (TABLE_TYPES.has(t) || t.endsWith('matrix') || t.endsWith('tableex')) return 'cat-table';
  if (CONTAINER_TYPES.has(t) || t.endsWith('shape') || t.endsWith('textbox') || t.endsWith('button') || t.endsWith('image')) return 'cat-container';
  if (CHART_TYPES.has(t) || t.endsWith('chart') || t.endsWith('map') || t.endsWith('treemap') || t.endsWith('waterfall') || t.endsWith('funnel')) return 'cat-chart';
  return 'cat-other';
}

const PageCanvas: React.FC<{ page: PageInfo; over: Set<number>; selected: number | null; onSelect: (i: number | null) => void }> = ({ page, over, selected, onSelect }) => {
  const W = page.width || 1280, H = page.height || 720;
  const visuals = page.visuals || [];
  const ordered = useMemo(() => readingOrder(visuals), [visuals]);
  const orderMap = useMemo(() => {
    const map = new Map<VisualInfo, number>();
    ordered.forEach((v, idx) => map.set(v, idx + 1));
    return map;
  }, [ordered]);

  return (
    <div className="panel" style={{ padding: 12 }}>
      <div className="canvas-meta">
        <span>Canvas: <strong>{W} × {H} px</strong> · {visuals.length} visuals · {page.slicer_count} slicers</span>
        <span className="meta-tags">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--v-slicer)' }} /> Slicer
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--v-card)' }} /> Card / KPI
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--v-table)' }} /> Table
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--v-chart)' }} /> Chart
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, border: '1px dashed var(--v-container)' }} /> Container / Shape
          </span>
        </span>
      </div>
      <svg className="canvas2d" viewBox={`-4 -4 ${W + 8} ${H + 8}`} role="img" aria-label={`Layout of ${page.display_name}: ${visuals.length} visuals`}>
        <rect className="frame" x="0" y="0" width={W} height={H} />
        {visuals.map((v, i) => {
          const category = visualCategory(v.visual_type, v.is_slicer);
          const cls = ['vis', category, over.has(i) && 'over', v.hidden && 'hidden', selected === i && 'sel'].filter(Boolean).join(' ');
          const pos = orderMap.get(v) ?? (i + 1);
          const badgeW = pos > 99 ? 34 : (pos > 9 ? 28 : 22);
          const badgeH = 16;
          const showBadge = v.width >= 32 && v.height >= 22;
          const fs = Math.max(10, Math.min(14, v.height / 5));
          const showTitle = v.width > 70 && v.height > 26;

          return (
            <g key={i} className={cls} tabIndex={0} role="button" aria-label={`Position #${pos}: ${v.visual_type}${over.has(i) ? ', over the visual limit' : ''}`}
               onClick={() => onSelect(selected === i ? null : i)}
               onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(selected === i ? null : i); } }}>
              <rect className="vis-box" x={v.x + 3} y={v.y + 3} width={Math.max(4, v.width - 6)} height={Math.max(4, v.height - 6)} />
              {showBadge && (
                <g className="badge-group">
                  <title>{`Layout order #${pos}`}</title>
                  <rect className="badge-bg" x={v.x + 6} y={v.y + 6} width={badgeW} height={badgeH} />
                  <text className="badge-txt" x={v.x + 6 + badgeW / 2} y={v.y + 6 + badgeH / 2} fontSize={10}>#{pos}</text>
                </g>
              )}
              {showTitle && (
                <text
                  className="vis-title"
                  x={v.height >= 46 || !showBadge ? v.x + 8 : v.x + badgeW + 12}
                  y={v.height >= 46 ? v.y + 12 + badgeH + fs : v.y + v.height / 2 + 4}
                  fontSize={fs}
                >
                  {v.visual_type}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};
