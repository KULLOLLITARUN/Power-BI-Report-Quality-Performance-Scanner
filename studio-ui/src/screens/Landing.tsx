import React, { useEffect, useRef } from 'react';
import { ArrowRight, FolderOpen, FolderSearch, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { animate } from '../lib/motion';

interface Props {
  hasBackend: boolean;
  dragging: boolean;
  onOpen: () => void;
  onBrowse: () => void;
  onCompare: () => void;
  onDemo: (which: 'enterprise' | 'bananas') => void;
}

export const Landing: React.FC<Props> = ({ hasBackend, dragging, onOpen, onBrowse, onCompare, onDemo }) => {
  const isoRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    animate({
      targets: isoRef.current?.querySelectorAll('.b'),
      translateY: [26, 0],
      delay: (_: unknown, i: number) => 100 + i * 70, duration: 900, easing: 'easeOutElastic(1, .8)',
    });
  }, []);

  return (
    <>
      <div className="landing">
        <div>
          <h2>See what your Power BI model is costing you.</h2>
          <p className="lede">
            pbiscan reads a <span className="mono">.pbip</span> project: the semantic model, its DAX and the report pages.
            It scores the model, explains each problem, and proposes fixes you review before anything is written.
          </p>
          <div className="facts">
            <span className="chip"><ShieldCheck size={12} aria-hidden="true" />{hasBackend ? 'Runs on this machine' : 'Files stay in this browser tab'}</span>
            <span className="chip">TMDL · model.bim · PBIR · report.json</span>
          </div>
        </div>
        <IsoCity ref={isoRef} />
      </div>

      <div className={`dropzone${dragging ? ' dragging' : ''}`}>
        <h3>{dragging ? 'Drop to scan this project' : 'Open a .pbip project'}</h3>
        <p>
          {hasBackend
            ? 'Pick the project folder or its .pbip file. You can also drag the folder onto this page.'
            : 'Drag the project folder onto this page, or pick it below. It is read in this tab and never uploaded.'}
        </p>
        <div className="actions">
          <button className="btn btn-primary" onClick={onOpen}><FolderOpen aria-hidden="true" />Open project</button>
          {hasBackend && <button className="btn" onClick={onBrowse}><FolderSearch aria-hidden="true" />Browse folders</button>}
          <button className="btn" onClick={onCompare}><GitCompareArrows aria-hidden="true" />Compare two scans</button>
        </div>
      </div>

      <div>
        <div className="label" style={{ marginBottom: 10 }}>Or explore a sample project</div>
        <div className="demos">
          <button className="demo" onClick={() => onDemo('enterprise')}>
            <b>Enterprise Sales &amp; Margin</b>
            <span className="mono">Star schema · bidirectional filter · 18-visual page</span>
            <span className="go">Open sample <ArrowRight size={14} aria-hidden="true" /></span>
          </button>
          <button className="demo" onClick={() => onDemo('bananas')}>
            <b>World is going bananas</b>
            <span className="mono">15 tables · TMDL · mostly clean</span>
            <span className="go">Open sample <ArrowRight size={14} aria-hidden="true" /></span>
          </button>
        </div>
      </div>
    </>
  );
};

/** A small isometric star schema: one fact block, dimensions around it. Decorative. */
const IsoCity = React.forwardRef<SVGSVGElement>((_, ref) => {
  // [gridX, gridY, height, kind]
  const blocks: [number, number, number, 'fact' | 'dim' | 'date'][] = [
    [0, -3, 2, 'dim'], [-3, -1, 2.4, 'dim'], [3, -2, 1.6, 'date'],
    [0, 0, 4.2, 'fact'],
    [-3, 2, 1.8, 'dim'], [3, 1, 2.2, 'dim'], [0, 3, 1.4, 'dim'],
  ];
  const S = 26;
  const iso = (x: number, y: number, z: number) => [260 + (x - y) * S * 0.87, 150 + (x + y) * S * 0.5 - z * S * 0.62];
  const fill = { fact: 'var(--t-fact)', dim: 'var(--t-dim)', date: 'var(--t-date)' };
  const edge = { fact: 'var(--t-fact-edge)', dim: 'var(--t-dim-edge)', date: 'var(--t-date-edge)' };
  const order = [...blocks].sort((a, b) => a[0] + a[1] - (b[0] + b[1]));
  const box = ([x, y, h, k]: typeof blocks[number], i: number) => {
    const w = k === 'fact' ? 1.4 : 0.9;
    const P = (dx: number, dy: number, z: number) => iso(x + dx, y + dy, z).join(',');
    const top = [P(-w, -w, h), P(w, -w, h), P(w, w, h), P(-w, w, h)].join(' ');
    const left = [P(-w, w, 0), P(w, w, 0), P(w, w, h), P(-w, w, h)].join(' ');
    const right = [P(w, -w, 0), P(w, w, 0), P(w, w, h), P(w, -w, h)].join(' ');
    return (
      <g className="b" key={i}>
        <polygon points={left} fill={fill[k]} stroke={edge[k]} strokeWidth="1" style={{ filter: 'brightness(.82)' }} />
        <polygon points={right} fill={fill[k]} stroke={edge[k]} strokeWidth="1" style={{ filter: 'brightness(.68)' }} />
        <polygon points={top} fill={fill[k]} stroke={edge[k]} strokeWidth="1" />
      </g>
    );
  };
  const fact = iso(0, 0, 4.2);
  return (
    <svg ref={ref} className="iso" viewBox="0 0 520 300" role="img" aria-label="Illustration: tables drawn as blocks around a central fact table">
      {Array.from({ length: 9 }, (_, i) => i - 4).map((g) => (
        <g key={g} stroke="var(--rule)" strokeWidth="1">
          <line x1={iso(g, -4.5, 0)[0]} y1={iso(g, -4.5, 0)[1]} x2={iso(g, 4.5, 0)[0]} y2={iso(g, 4.5, 0)[1]} />
          <line x1={iso(-4.5, g, 0)[0]} y1={iso(-4.5, g, 0)[1]} x2={iso(4.5, g, 0)[0]} y2={iso(4.5, g, 0)[1]} />
        </g>
      ))}
      {blocks.filter((b) => b[3] !== 'fact').map(([x, y, h], i) => {
        const [ax, ay] = iso(x, y, h);
        const mx = (ax + fact[0]) / 2, my = Math.min(ay, fact[1]) - 26;
        return <path key={i} d={`M${ax} ${ay} Q${mx} ${my} ${fact[0]} ${fact[1]}`} fill="none" stroke="var(--rule-strong)" strokeWidth="1.4" />;
      })}
      {order.map(box)}
      <g className="b"><path d={`M${fact[0]} ${fact[1] - 34} l9 12 -9 12 -9 -12z`} fill="var(--sev-high)" /></g>
    </svg>
  );
});
IsoCity.displayName = 'IsoCity';
