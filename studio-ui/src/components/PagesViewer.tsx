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
    <div className="space-y-4 font-mono">
      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        Review visual layout density and slicer counts across all report pages. Pages with &gt;15 visuals or &gt;6 slicers trigger performance warnings.
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {pages.map((page, idx) => {
          const hasVisualBloat = visualBloatFindings.some((f) => f.location?.includes(page.display_name));
          const hasSlicerBloat = slicerBloatFindings.some((f) => f.location?.includes(page.display_name));

          return (
            <div
              key={page.name || idx}
              className="p-5 rounded border transition shadow-sm"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: hasVisualBloat || hasSlicerBloat 
                  ? 'var(--severity-warning)' 
                  : 'var(--border-hairline)',
              }}
            >
              {/* Header */}
              <div 
                className="flex items-center justify-between pb-3 border-b"
                style={{ borderColor: 'var(--border-hairline)' }}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Layout className="w-4 h-4 shrink-0" style={{ color: 'var(--accent)' }} />
                  <h4 className="font-bold text-sm truncate" style={{ color: 'var(--text-primary)' }} title={page.display_name}>
                    {page.display_name}
                  </h4>
                </div>

                {page.is_hidden ? (
                  <span 
                    className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border"
                    style={{
                      backgroundColor: 'var(--bg-canvas)',
                      borderColor: 'var(--border-hairline)',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <EyeOff className="w-2.5 h-2.5" />
                    <span>hidden</span>
                  </span>
                ) : (
                  <span 
                    className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border"
                    style={{
                      backgroundColor: 'var(--bg-canvas)',
                      borderColor: 'var(--border-strong)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <Eye className="w-2.5 h-2.5" />
                    <span>visible</span>
                  </span>
                )}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div 
                  className="p-3 rounded border text-center"
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    borderColor: 'var(--border-hairline)',
                  }}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-wider flex items-center justify-center gap-1" style={{ color: 'var(--text-muted)' }}>
                    <BarChart2 className="w-3 h-3" />
                    <span>Visuals</span>
                  </div>
                  <div className="text-xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                    {page.visual_count}
                  </div>
                  <div className="text-[10px] mt-0.5" style={{ color: hasVisualBloat ? 'var(--severity-warning)' : 'var(--text-muted)' }}>
                    {hasVisualBloat ? '⚠️ >15 Bloat' : 'Optimal'}
                  </div>
                </div>

                <div 
                  className="p-3 rounded border text-center"
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    borderColor: 'var(--border-hairline)',
                  }}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-wider flex items-center justify-center gap-1" style={{ color: 'var(--text-muted)' }}>
                    <Filter className="w-3 h-3" />
                    <span>Slicers</span>
                  </div>
                  <div className="text-xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                    {page.slicer_count}
                  </div>
                  <div className="text-[10px] mt-0.5" style={{ color: hasSlicerBloat ? 'var(--severity-warning)' : 'var(--text-muted)' }}>
                    {hasSlicerBloat ? '⚠️ >6 Slicers' : 'Optimal'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
