import React from 'react';
import { Database, Code2, Layout, ShieldCheck } from 'lucide-react';
import { ScoreData } from '../types';

interface HealthScorecardProps {
  scores: ScoreData;
  warningsCount: number;
}

export const HealthScorecard: React.FC<HealthScorecardProps> = ({
  scores,
  warningsCount,
}) => {
  const overall = Math.round(scores.overall);
  const modelScore = scores.category_scores.model ?? 100;
  const daxScore = scores.category_scores.dax ?? 100;
  const reportScore = scores.category_scores.report ?? 100;

  const getScoreBadge = (score: number) => {
    if (score >= 90) return { text: 'text-emerald-400', label: 'Healthy', bg: 'bg-emerald-500/10 border-emerald-500/20' };
    if (score >= 70) return { text: 'text-amber-400', label: 'Review', bg: 'bg-amber-500/10 border-amber-500/20' };
    return { text: 'text-red-400', label: 'Critical', bg: 'bg-red-500/10 border-red-500/20' };
  };

  const overallBadge = getScoreBadge(overall);

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-3.5">
      {/* Overall Score */}
      <div className="p-4 rounded-lg bg-studio-card border border-studio-border flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-studio-textMuted uppercase tracking-wider">
            Overall Health
          </span>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border font-mono ${overallBadge.bg} ${overallBadge.text}`}>
            {overallBadge.label}
          </span>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-bold font-mono text-white">{overall}</span>
          <span className="text-xs text-studio-subtle font-mono">/ 100</span>
        </div>
        <div className="w-full bg-studio-bg h-1.5 rounded-full mt-3 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${overall >= 90 ? 'bg-emerald-500' : overall >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${overall}%` }}
          />
        </div>
      </div>

      {/* Model Score */}
      <div className="p-4 rounded-lg bg-studio-card border border-studio-border flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span>Semantic Model</span>
          </div>
          <span className="text-[10px] text-studio-subtle font-mono">35%</span>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono text-white">{modelScore}</span>
          <span className="text-xs text-studio-subtle font-mono">/ 100</span>
        </div>
        <div className="w-full bg-studio-bg h-1.5 rounded-full mt-3 overflow-hidden">
          <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${modelScore}%` }} />
        </div>
      </div>

      {/* DAX Score */}
      <div className="p-4 rounded-lg bg-studio-card border border-studio-border flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
            <Code2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>DAX Calculations</span>
          </div>
          <span className="text-[10px] text-studio-subtle font-mono">25%</span>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono text-white">{daxScore}</span>
          <span className="text-xs text-studio-subtle font-mono">/ 100</span>
        </div>
        <div className="w-full bg-studio-bg h-1.5 rounded-full mt-3 overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${daxScore}%` }} />
        </div>
      </div>

      {/* Report Canvas Score */}
      <div className="p-4 rounded-lg bg-studio-card border border-studio-border flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
            <Layout className="w-3.5 h-3.5 text-purple-400" />
            <span>Report Canvas</span>
          </div>
          <span className="text-[10px] text-studio-subtle font-mono">20%</span>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono text-white">{reportScore}</span>
          <span className="text-xs text-studio-subtle font-mono">/ 100</span>
        </div>
        <div className="w-full bg-studio-bg h-1.5 rounded-full mt-3 overflow-hidden">
          <div className="h-full bg-purple-500 rounded-full transition-all duration-500" style={{ width: `${reportScore}%` }} />
        </div>
      </div>
    </div>
  );
};
