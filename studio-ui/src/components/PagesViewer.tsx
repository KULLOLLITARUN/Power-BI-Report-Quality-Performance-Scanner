import React from 'react';
import { PageInfo, AuditFinding } from '../types';
import { Layout, EyeOff, Eye, BarChart2, Filter, AlertTriangle } from 'lucide-react';

interface PagesViewerProps {
  pages: PageInfo[];
  findings: AuditFinding[];
}

export const PagesViewer: React.FC<PagesViewerProps> = ({ pages, findings }) => {
  const visualBloatFindings = findings.filter((f) => f.rule_id === 'REPORT_VISUAL_BLOAT');
  const slicerBloatFindings = findings.filter((f) => f.rule_id === 'REPORT_SLICER_BLOAT');

  return (
    <div className="space-y-4">
      <div className="text-xs text-slate-400">
        Review visual layout density and slicer counts across all report pages. Pages with &gt;15 visuals or &gt;6 slicers trigger performance warnings.
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {pages.map((page, idx) => {
          const hasVisualBloat = visualBloatFindings.some((f) => f.location?.includes(page.display_name));
          const hasSlicerBloat = slicerBloatFindings.some((f) => f.location?.includes(page.display_name));

          return (
            <div
              key={page.name || idx}
              className={`p-5 rounded-xl border transition shadow-sm ${
                hasVisualBloat || hasSlicerBloat
                  ? 'bg-amber-500/5 border-amber-500/30'
                  : 'bg-obsidian-800/80 border-obsidian-700/80'
              }`}
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-obsidian-700/60">
                <div className="flex items-center gap-2 min-w-0">
                  <Layout className="w-4 h-4 text-cyan-400 shrink-0" />
                  <h4 className="font-bold text-sm text-white truncate" title={page.display_name}>
                    {page.display_name}
                  </h4>
                </div>

                {page.is_hidden ? (
                  <span className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    <EyeOff className="w-2.5 h-2.5" />
                    <span>hidden</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Eye className="w-2.5 h-2.5" />
                    <span>visible</span>
                  </span>
                )}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-700 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-center gap-1">
                    <BarChart2 className="w-3 h-3 text-blue-400" />
                    <span>Visuals</span>
                  </div>
                  <div className={`text-xl font-bold font-mono mt-1 ${page.visual_count > 15 ? 'text-amber-400' : 'text-white'}`}>
                    {page.visual_count}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">threshold: 15</div>
                </div>

                <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-700 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-center gap-1">
                    <Filter className="w-3 h-3 text-emerald-400" />
                    <span>Slicers</span>
                  </div>
                  <div className={`text-xl font-bold font-mono mt-1 ${page.slicer_count > 6 ? 'text-amber-400' : 'text-white'}`}>
                    {page.slicer_count}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">threshold: 6</div>
                </div>
              </div>

              {/* Warnings if any */}
              {(hasVisualBloat || hasSlicerBloat) && (
                <div className="mt-3 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>
                    {hasVisualBloat && hasSlicerBloat
                      ? 'High visual & slicer density detected.'
                      : hasVisualBloat
                      ? 'Visual density exceeds recommended limit.'
                      : 'Slicer count exceeds recommended limit.'}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
