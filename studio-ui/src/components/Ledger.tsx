import React, { useEffect, useRef } from 'react';
import type { AuditFinding, ScoreData } from '../types';
import { SEV_ORDER, grade, sevMeta, type Severity } from '../lib/severity';
import { animate } from '../lib/motion';
import { shortDate, type HistoryPoint } from '../lib/history';
import { ScoreBar, SevMarker } from './ui';

const TARGET = 80;

interface Props {
  scores: ScoreData;
  findings: AuditFinding[];      // open (unsuppressed) findings
  suppressedCount: number;
  history: HistoryPoint[];       // oldest first; last item is this scan when recorded
  sev: Severity | null;
  onSev: (s: Severity | null) => void;
}

export const Ledger: React.FC<Props> = ({ scores, findings, suppressedCount, history, sev, onSev }) => {
  const scoreRef = useRef<HTMLDivElement>(null);
  const catsRef = useRef<HTMLDivElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const overall = scores?.overall ?? 0;
  const prev = history.length >= 2 ? history[history.length - 2] : null;
  const delta = prev ? overall - prev.overall : null;
  const counts = Object.fromEntries(SEV_ORDER.map((s) => [s, findings.filter((f) => f.severity === s).length])) as Record<Severity, number>;
  const shown = SEV_ORDER.filter((s) => counts[s] > 0 || ['HIGH', 'MEDIUM', 'WARNING', 'ADVISORY'].includes(s));

  useEffect(() => {
    const el = scoreRef.current;
    const o = { v: 0 };
    animate({ targets: o, v: overall, duration: 1100, easing: 'easeOutExpo', update: () => { if (el) el.textContent = o.v.toFixed(1); } });
    animate({ targets: catsRef.current?.querySelectorAll('.bar > b'), scaleX: [0, 1], delay: (_: unknown, i: number) => 150 + i * 90, duration: 700, easing: 'easeOutQuart' });
    animate({ targets: stripRef.current?.querySelectorAll('button'), scaleX: [0, 1], delay: (_: unknown, i: number) => 300 + i * 70, duration: 600, easing: 'easeOutQuart' });
  }, [overall]);

  const cats: [string, number][] = [
    ['Model', scores?.category_scores?.model ?? 100],
    ['DAX', scores?.category_scores?.dax ?? 100],
    ['Report', scores?.category_scores?.report ?? 100],
  ];
  const g = grade(overall);

  return (
    <div className="ledger">
      <section className="panel" aria-label="Overall score">
        <h2 className="card-label">Model health</h2>
        <div className="score-row">
          <div className="score"><span ref={scoreRef}>{overall.toFixed(1)}</span><small> / 100</small></div>
          <div className="grade" title={`Grade ${g}: ${g === 'A' ? '90 and above' : g === 'B' ? '80 to 89' : g === 'C' ? '70 to 79' : g === 'D' ? '60 to 69' : 'below 60'}`}>{g}</div>
        </div>
        {delta !== null && prev ? (
          <div className={`delta ${delta > 0 ? 'up' : delta < 0 ? 'down' : ''}`}>
            <b>{delta > 0 ? '▲' : delta < 0 ? '▼' : '='} {Math.abs(delta).toFixed(1)}</b> since {shortDate(prev.t)} scan
          </div>
        ) : (
          <div className="delta">First scan of this project here</div>
        )}
      </section>
      <section className="panel" aria-label="Category scores">
        <h2 className="card-label">By area</h2>
        <div className="cats" ref={catsRef}>
          {cats.map(([name, v]) => (
            <div className="cat" key={name}>
              <span className="cat-name">{name}</span>
              <ScoreBar value={v} target={TARGET} label={name} />
              <b className="num">{Math.round(v)}</b>
            </div>
          ))}
        </div>
        <div className="cat-note"><i />Target {TARGET}</div>
      </section>
      <section className="panel" aria-label="Score history">
        <h2 className="card-label">{history.length >= 2 ? `Last ${history.length} scans` : 'Score trend'}</h2>
        <Sparkline history={history} />
      </section>
      <section className="panel" aria-label="Findings by severity">
        <h2 className="card-label">{findings.length} open finding{findings.length === 1 ? '' : 's'}{suppressedCount ? `, ${suppressedCount} suppressed` : ''}</h2>
        <div className="sevstrip" ref={stripRef}>
          {findings.length === 0 ? <span className="none" title="No open findings" /> :
            SEV_ORDER.filter((s) => counts[s]).map((s) => (
              <button key={s} style={{ flex: counts[s], background: `var(${sevMeta(s).token})` }} aria-label={`Show ${sevMeta(s).label} findings (${counts[s]})`} onClick={() => onSev(sev === s ? null : s)} />
            ))}
        </div>
        <div className="sevlegend">
          {shown.map((s) => (
            <button key={s} aria-pressed={sev === s} disabled={!counts[s]} onClick={() => onSev(sev === s ? null : s)}>
              <SevMarker sev={s} size={11} />{sevMeta(s).label}<b>{counts[s]}</b>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
};

const Sparkline: React.FC<{ history: HistoryPoint[] }> = ({ history }) => {
  const lineRef = useRef<SVGPathElement>(null);
  useEffect(() => {
    const el = lineRef.current;
    if (!el) return;
    const len = el.getTotalLength?.() || 600;
    el.style.strokeDasharray = `${len}`;
    const a = animate({ targets: el, strokeDashoffset: [len, 0], duration: 1300, easing: 'easeInOutSine', complete: () => { el.style.strokeDasharray = ''; } });
    if (!a) el.style.strokeDasharray = '';
  }, [history.length]);

  if (history.length < 2) {
    return (
      <div className="spark-empty">
        <span>The trend appears after your next scan.</span>
        <span style={{ fontSize: 12 }}>Scores are kept in this browser only.</span>
      </div>
    );
  }
  const W = 240, x0 = 6, x1 = 228, yTop = 22, yBot = 58;
  const vals = history.map((h) => h.overall);
  let lo = Math.floor((Math.min(...vals) - 2) / 5) * 5;
  let hi = Math.ceil((Math.max(...vals) + 2) / 5) * 5;
  if (hi - lo < 10) { hi = Math.min(100, lo + 10); lo = hi - 10; }
  const X = (i: number) => x0 + (i / (history.length - 1)) * (x1 - x0);
  const Y = (v: number) => yBot - ((v - lo) / (hi - lo)) * (yBot - yTop);
  const pts = vals.map((v, i) => [X(i), Y(v)]);
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const area = `${line} L${x1} ${yBot} L${x0} ${yBot} Z`;
  const last = pts[pts.length - 1];
  return (
    <svg className="spark" viewBox={`0 0 ${W} 72`} role="img" aria-label={`Overall score went from ${vals[0].toFixed(1)} to ${vals[vals.length - 1].toFixed(1)} over ${vals.length} scans`}>
      <path d={area} fill="var(--accent-soft)" />
      <path ref={lineRef} d={line} fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="3.5" fill="var(--accent)" />
      <text x={x0} y={Math.max(11, pts[0][1] - 8)} fontFamily="var(--f-body)" fontSize="11" fontWeight="500" fill="var(--muted)">{vals[0].toFixed(1)}</text>
      <text x={x1} y={Math.max(11, last[1] - 9)} textAnchor="end" fontFamily="var(--f-body)" fontSize="11" fontWeight="600" fill="var(--ink)">{vals[vals.length - 1].toFixed(1)}</text>
      <text x={x0} y="71" fontFamily="var(--f-body)" fontSize="10.5" fill="var(--muted)">{shortDate(history[0].t)}</text>
      <text x={x1} y="71" textAnchor="end" fontFamily="var(--f-body)" fontSize="10.5" fill="var(--muted)">{shortDate(history[history.length - 1].t)}</text>
    </svg>
  );
};
