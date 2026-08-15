import React from 'react';
import { ScoreData } from '../types';

interface HealthScorecardProps {
  scores: ScoreData;
  warningsCount: number;
}

export const HealthScorecard: React.FC<HealthScorecardProps> = ({
  scores,
}) => {
  const overall = scores?.overall !== undefined ? Math.round(scores.overall) : 100;
  const modelScore = Math.round(scores?.category_scores?.model ?? 100);
  const daxScore = Math.round(scores?.category_scores?.dax ?? 100);
  const reportScore = Math.round(scores?.category_scores?.report ?? 100);

  const getStatus = (score: number) => {
    if (score >= 90) return { label: 'PASSING', text: 'Model and DAX structures conform to production standards.' };
    if (score >= 70) return { label: 'REVIEW RECOMMENDED', text: 'Architectural or calculation warnings detected.' };
    return { label: 'ACTION REQUIRED', text: 'High-severity anti-patterns detected in model/DAX.' };
  };

  const status = getStatus(overall);

  return (
    <div 
      className="p-5 rounded border"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
      }}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Left Hero Section (60%): Dominant Overall Health Anchor */}
        <div className="lg:col-span-6 flex flex-col justify-between border-b lg:border-b-0 lg:border-r pb-5 lg:pb-0 lg:pr-6"
             style={{ borderColor: 'var(--border-hairline)' }}>
          <div className="flex items-center justify-between">
            <span 
              className="text-[11px] font-mono font-medium uppercase tracking-wider"
              style={{ color: 'var(--text-muted)' }}
            >
              Diagnostic Verdict
            </span>
            <span 
              className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border"
              style={{
                backgroundColor: 'var(--bg-canvas)',
                borderColor: 'var(--border-strong)',
                color: overall >= 90 ? 'var(--text-primary)' : 'var(--accent)',
              }}
            >
              {status.label}
            </span>
          </div>

          <div className="my-3 flex items-baseline gap-3">
            <span 
              className="text-5xl font-mono font-bold tracking-tight"
              style={{ color: 'var(--accent)' }}
            >
              {overall}
            </span>
            <span 
              className="text-sm font-mono"
              style={{ color: 'var(--text-muted)' }}
            >
              / 100
            </span>
          </div>

          <p 
            className="text-xs leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}
          >
            {status.text}
          </p>
        </div>

        {/* Right Secondary Section (40%): Compact Sub-Category Telemetry */}
        <div className="lg:col-span-6 space-y-3.5">
          <div className="text-[11px] font-mono font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Category Diagnostics
          </div>

          {/* Model Architecture Meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                Semantic Model
              </span>
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <span style={{ color: 'var(--text-muted)' }}>w: 35%</span>
                <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{modelScore}%</span>
              </div>
            </div>
            <div className="h-1.5 w-full rounded-sm overflow-hidden" style={{ backgroundColor: 'var(--bg-canvas)' }}>
              <div 
                className="h-full rounded-sm transition-all duration-300"
                style={{ 
                  width: `${modelScore}%`,
                  backgroundColor: 'var(--border-strong)',
                }}
              />
            </div>
          </div>

          {/* DAX Calculations Meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                DAX Calculations
              </span>
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <span style={{ color: 'var(--text-muted)' }}>w: 25%</span>
                <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{daxScore}%</span>
              </div>
            </div>
            <div className="h-1.5 w-full rounded-sm overflow-hidden" style={{ backgroundColor: 'var(--bg-canvas)' }}>
              <div 
                className="h-full rounded-sm transition-all duration-300"
                style={{ 
                  width: `${daxScore}%`,
                  backgroundColor: 'var(--border-strong)',
                }}
              />
            </div>
          </div>

          {/* Report Layout Meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                Report Canvas
              </span>
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <span style={{ color: 'var(--text-muted)' }}>w: 20%</span>
                <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{reportScore}%</span>
              </div>
            </div>
            <div className="h-1.5 w-full rounded-sm overflow-hidden" style={{ backgroundColor: 'var(--bg-canvas)' }}>
              <div 
                className="h-full rounded-sm transition-all duration-300"
                style={{ 
                  width: `${reportScore}%`,
                  backgroundColor: 'var(--border-strong)',
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
