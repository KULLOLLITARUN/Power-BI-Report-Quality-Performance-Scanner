import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { sevMeta } from '../lib/severity';
import { animate } from '../lib/motion';

/** Severity encoded by shape and colour, so it still reads without colour. */
export const SevMarker: React.FC<{ sev: string; size?: number }> = ({ sev, size = 12 }) => {
  const m = sevMeta(sev);
  const c = `var(${m.token})`;
  const h = size / 2;
  const shape = {
    diamond: <path d={`M${h} 0.5 L${size - 0.5} ${h} L${h} ${size - 0.5} L0.5 ${h} Z`} fill={c} />,
    tri: <path d={`M${h} 1 L${size - 1} ${size - 1.5} L1 ${size - 1.5} Z`} fill={c} />,
    square: <rect x="2" y="2" width={size - 4} height={size - 4} fill={c} />,
    circle: <circle cx={h} cy={h} r={h - 1.5} fill={c} />,
    ring: <circle cx={h} cy={h} r={h - 2} fill="none" stroke={c} strokeWidth="2" />,
    dash: <rect x="1.5" y={h - 1.5} width={size - 3} height="3" fill={c} />,
  }[m.shape];
  return <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" style={{ flex: 'none' }}>{shape}</svg>;
};

export const SevTag: React.FC<{ sev: string }> = ({ sev }) => (
  <span className="sev-tag" style={{ color: `var(${sevMeta(sev).token})` }}>{(sev || '').toUpperCase()}</span>
);

export const Confidence: React.FC<{ value: number; label?: boolean }> = ({ value, label }) => (
  <span className="conf" title="Confidence">
    {label ? `confidence ${Math.round(value)}%` : `${Math.round(value)}%`}
    <i style={{ ['--w' as any]: `${Math.max(0, Math.min(100, value))}%` }} />
  </span>
);

/** The pbiscan cube mark. */
export const Cube: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2.5 21 7.5v9L12 21.5 3 16.5v-9z" fill="var(--t-fact)" />
    <path d="M12 12.2 21 7.5M12 12.2 3 7.5M12 12.2v9.3" stroke="var(--panel)" strokeWidth="1.4" fill="none" />
    <path d="M12 2.5 21 7.5 12 12.2 3 7.5z" fill="var(--t-dim)" />
  </svg>
);

/** 20 blocks of 5 points; the last one fills partially. */
export const Blocks: React.FC<{ value: number; target?: number; label: string }> = ({ value, target, label }) => (
  <div className="blocks" role="img" aria-label={`${label} ${value.toFixed(1)} of 100`}>
    {Array.from({ length: 20 }, (_, k) => {
      const fill = Math.max(0, Math.min(1, (value - k * 5) / 5));
      return fill >= 1 ? <i key={k} className="on" />
        : fill > 0 ? <i key={k} className="part" style={{ ['--p' as any]: `${Math.round(fill * 100)}%` }} />
        : <i key={k} />;
    })}
    {target !== undefined && <span className="target" style={{ ['--t' as any]: `${target}%` }} />}
  </div>
);

// ---------------------------------------------------------------- toasts
interface ToastItem { id: number; text: string; kind: 'info' | 'error' }
const ToastCtx = createContext<(text: string, kind?: 'info' | 'error') => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((text: string, kind: 'info' | 'error' = 'info') => {
    const id = Date.now() + Math.random();
    setItems((list) => [...list.slice(-2), { id, text, kind }]);
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), kind === 'error' ? 5200 : 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <ToastView key={t.id} item={t} />)}
      </div>
    </ToastCtx.Provider>
  );
};

const ToastView: React.FC<{ item: ToastItem }> = ({ item }) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    animate({ targets: ref.current, translateY: [12, 0], opacity: [0, 1], duration: 260, easing: 'easeOutQuad' });
  }, []);
  return <div ref={ref} className={`toast${item.kind === 'error' ? ' error' : ''}`}>{item.text}</div>;
};

// ---------------------------------------------------------------- media query
export function useMedia(query: string): boolean {
  const [match, setMatch] = useState(() => {
    try { return window.matchMedia(query).matches; } catch { return false; }
  });
  useEffect(() => {
    const mq = window.matchMedia(query);
    const fn = () => setMatch(mq.matches);
    fn();
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, [query]);
  return match;
}
export const useMobile = () => useMedia('(max-width: 860px)');

// ---------------------------------------------------------------- bottom sheet (phones)
/** On phones, children slide up as a bottom sheet; on wider screens they render in place. */
export const Sheet: React.FC<{
  open: boolean; onClose: () => void; label: string; className?: string; children: React.ReactNode;
}> = ({ open, onClose, label, className = '', children }) => {
  const mobile = useMobile();
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<number | null>(null);

  useEffect(() => {
    if (!mobile || !open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    ref.current?.scrollTo({ top: 0 });
    ref.current?.querySelector<HTMLButtonElement>('.sheet-grip button')?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => { document.body.style.overflow = prev; document.removeEventListener('keydown', onKey); };
  }, [mobile, open, onClose]);

  if (!mobile) return <div className={className}>{children}</div>;
  const onDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    drag.current = e.clientY;
    if (ref.current) ref.current.style.transition = 'none';
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    if (drag.current !== null && ref.current) ref.current.style.transform = `translateY(${Math.max(0, e.clientY - drag.current)}px)`;
  };
  const onUp = (e: React.PointerEvent) => {
    if (drag.current === null) return;
    const dy = e.clientY - drag.current;
    drag.current = null;
    if (ref.current) { ref.current.style.transition = ''; ref.current.style.transform = ''; }
    if (dy > 90) onClose();
  };
  return (
    <>
      <div className={`sheet-backdrop${open ? ' open' : ''}`} onClick={onClose} />
      <div ref={ref} className={`${className} sheet${open ? ' open' : ''}`} role="dialog" aria-modal={open} aria-label={label} aria-hidden={!open}>
        <div className="sheet-grip" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
          <span />
          <button type="button" onClick={onClose} aria-label="Close">×</button>
        </div>
        {children}
      </div>
    </>
  );
};

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
