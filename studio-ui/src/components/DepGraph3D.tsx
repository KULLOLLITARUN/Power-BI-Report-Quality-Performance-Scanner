import React, { useEffect, useRef, useState } from 'react';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { DepScene } from '../lib/depScene';
import type { DepLayout } from '../lib/depLayout';

interface Props {
  layout: DepLayout;
  selected: string | null;
  onSelect: (name: string | null) => void;
}

/** React wrapper around the three.js DepScene: stage, tools and legend. */
export const DepGraph3D: React.FC<Props> = ({ layout, selected, onSelect }) => {
  const stageRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<DepScene | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const cbRef = useRef(onSelect);
  cbRef.current = onSelect;
  const [failed, setFailed] = useState(() => !DepScene.supported());

  useEffect(() => {
    if (failed || !stageRef.current || !labelsRef.current || !tipRef.current) return;
    let scene: DepScene;
    try {
      scene = new DepScene(stageRef.current, labelsRef.current, tipRef.current, layout, { onSelect: (n) => cbRef.current(n) });
    } catch (err) {
      console.error('3D dependency graph failed to start', err);
      setFailed(true);
      return;
    }
    scene.select(selectedRef.current);
    sceneRef.current = scene;
    return () => { scene.dispose(); sceneRef.current = null; };
  }, [layout, failed]);

  useEffect(() => { sceneRef.current?.select(selected); }, [selected]);

  const summary = `${layout.nodes.length} nodes · ${layout.edges.length} references · ${layout.levels} levels deep`
    + (layout.unusedCount ? ` · ${layout.unusedCount} not reached by the report` : '');

  return (
    <div className="map panel dep-graph">
      <div className="map-head">
        <h2>Dependency graph</h2>
        <span>{summary}</span>
      </div>
      <div ref={stageRef} className="map-stage dep-stage">
        {failed && <div className="nogl">This browser has WebGL turned off, so the 3D graph is unavailable. The list below still works.</div>}
        <div ref={labelsRef} className="map-labels" />
        <div ref={tipRef} className="tip" hidden role="tooltip" />
        {!failed && (
          <div className="map-tools">
            <button type="button" title="Zoom in" aria-label="Zoom in" onClick={() => sceneRef.current?.zoom(1)}><Plus /></button>
            <button type="button" title="Zoom out" aria-label="Zoom out" onClick={() => sceneRef.current?.zoom(-1)}><Minus /></button>
            <button type="button" title="Reset view" aria-label="Reset view" onClick={() => sceneRef.current?.reset()}><RotateCcw /></button>
          </div>
        )}
      </div>
      <div className="map-foot">
        <span><Dot v="--t-fact" />used directly by the report</span>
        <span><Dot v="--t-dim" />used through other measures</span>
        <span><Dot v="--sev-medium" />not reached by the report</span>
        <span>height = dependency depth · lines = "uses" · click a node to light its chain</span>
      </div>
    </div>
  );
};

const Dot: React.FC<{ v: string }> = ({ v }) => (
  <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7" fill={`var(${v})`} /></svg>
);
