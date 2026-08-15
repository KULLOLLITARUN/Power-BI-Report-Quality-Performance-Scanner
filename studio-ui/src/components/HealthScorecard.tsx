import React from 'react';
import { ShieldCheck, Database, Code2, Layout, AlertCircle } from 'lucide-react';
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

  const getScoreColor = (score: number) => {
    if (score >= 90) return { text: 'text-emerald-400', stroke: '#10B981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' };
    if (score >= 70) return { text: 'text-amber-400', stroke: '#F59E0B', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
    return { text: 'text-red-400', stroke: '#EF4444', bg: 'bg-red-500/10', border: 'border-red-500/20' };
  };

  const overallStyle = getScoreColor(overall);
  const modelScore = scores.category_scores.model ?? 100;
  const daxScore = scores.category_scores.dax ?? 100;
  const reportScore = scores.category_scores.report ?? 100;

  // SVG Gauge calculations
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (overall / 100) * circumference;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Overall Health Gauge */}
      <div className="p-5 rounded-xl bg-obsidian-800/90 border border-obsidian-700 flex items-center justify-between shadow-sm">
        <div>
          <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Overall Health
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {overall >= 90 ? 'Production Ready' : overall >= 70 ? 'Review Recommended' : 'Action Required'}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className={`text-2xl font-bold font-mono ${overallStyle.text}`}>
              {overall}
            </span>
            <span className="text-xs text-slate-500">/ 100</span>
          </div>
        </div>

        {/* Circular Gauge */}
        <div className="relative w-20 h-20 flex items-center justify-center shrink-0">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
            <circle
              cx="60"
              cy="60"
              r={radius}
              className="text-obsidian-700 stroke-current"
              strokeWidth="10"
              fill="transparent"
            />
            <circle
              cx="60"
              cy="60"
              r={radius}
              stroke={overallStyle.stroke}
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <span className={`absolute text-base font-bold font-mono ${overallStyle.text}`}>
            {overall}
          </span>
        </div>
      </div>

      {/* Model Category Card */}
      <div className="p-5 rounded-xl bg-obsidian-800/90 border border-obsidian-700 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span>Semantic Model</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
            35% wt
          </span>
        </div>
        <div className="mt-4 flex items-baseline justify-between">
          <div className="text-3xl font-bold font-mono text-white">
            {modelScore}
          </div>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
        <div className="w-full h-1.5 bg-obsidian-700 rounded-full mt-3 overflow-hidden">
          <div 
            className="h-full bg-blue-500 rounded-full transition-all duration-700" 
            style={{ width: `${modelScore}%` }} 
          />
        </div>
      </div>

      {/* DAX Category Card */}
      <div className="p-5 rounded-xl bg-obsidian-800/90 border border-obsidian-700 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
            <Code2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>DAX Logic</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            25% wt
          </span>
        </div>
        <div className="mt-4 flex items-baseline justify-between">
          <div className="text-3xl font-bold font-mono text-white">
            {daxScore}
          </div>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
        <div className="w-full h-1.5 bg-obsidian-700 rounded-full mt-3 overflow-hidden">
          <div 
            className="h-full bg-emerald-500 rounded-full transition-all duration-700" 
            style={{ width: `${daxScore}%` }} 
          />
        </div>
      </div>

      {/* Report Canvas Category Card */}
      <div className="p-5 rounded-xl bg-obsidian-800/90 border border-obsidian-700 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
            <Layout className="w-3.5 h-3.5 text-cyan-400" />
            <span>Report Canvas</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            20% wt
          </span>
        </div>
        <div className="mt-4 flex items-baseline justify-between">
          <div className="text-3xl font-bold font-mono text-white">
            {reportScore}
          </div>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
        <div className="w-full h-1.5 bg-obsidian-700 rounded-full mt-3 overflow-hidden">
          <div 
            className="h-full bg-cyan-500 rounded-full transition-all duration-700" 
            style={{ width: `${reportScore}%` }} 
          />
        </div>
      </div>
    </div>
  );
};
