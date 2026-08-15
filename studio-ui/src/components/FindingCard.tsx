import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  AlertTriangle, 
  AlertCircle, 
  Info, 
  CheckCircle,
  Lightbulb,
  Gauge,
  Tag
} from 'lucide-react';
import { AuditFinding } from '../types';

interface FindingCardProps {
  finding: AuditFinding;
  index: number;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding, index }) => {
  const [expanded, setExpanded] = useState(false);

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30', icon: AlertCircle };
      case 'HIGH':
        return { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30', icon: AlertTriangle };
      case 'MEDIUM':
        return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30', icon: AlertTriangle };
      case 'WARNING':
        return { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30', icon: AlertTriangle };
      case 'ADVISORY':
        return { bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/30', icon: Info };
      default:
        return { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/30', icon: Info };
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'model':
        return 'text-blue-400 border-blue-500/20 bg-blue-500/10';
      case 'dax':
        return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10';
      case 'report':
        return 'text-cyan-400 border-cyan-500/20 bg-cyan-500/10';
      default:
        return 'text-slate-400 border-slate-500/20 bg-slate-500/10';
    }
  };

  const sev = getSeverityBadge(finding.severity);
  const SevIcon = sev.icon;

  return (
    <div className="rounded-xl bg-obsidian-800/80 border border-obsidian-700/80 hover:border-obsidian-600 transition overflow-hidden shadow-sm">
      {/* Accordion Header */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-4 flex items-center justify-between gap-4 cursor-pointer hover:bg-obsidian-700/30 transition select-none"
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Severity Badge */}
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold tracking-wider uppercase border font-mono shrink-0 ${sev.bg} ${sev.text} ${sev.border}`}>
            <SevIcon className="w-3 h-3" />
            {finding.severity}
          </span>

          {/* Category Badge */}
          <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded border font-mono shrink-0 ${getCategoryBadge(finding.category)}`}>
            {finding.category}
          </span>

          {/* Title & Location */}
          <div className="min-w-0">
            <h4 className="text-xs sm:text-sm font-semibold text-slate-100 truncate">
              {finding.title}
            </h4>
            {finding.location && (
              <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                {finding.location}
              </p>
            )}
          </div>
        </div>

        {/* Right side status */}
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">
            Rule: {finding.rule_id}
          </span>
          <div className="text-slate-400 p-1 rounded-md hover:bg-obsidian-700">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Accordion Body */}
      {expanded && (
        <div className="px-5 pb-5 pt-2 border-t border-obsidian-700/60 bg-obsidian-900/40 space-y-4 animate-in fade-in duration-200">
          {/* Evidence Box */}
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-400 mb-1.5 flex items-center gap-1.5">
              <Tag className="w-3 h-3 text-blue-400" />
              <span>Evidence</span>
            </div>
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-700 font-mono text-xs text-emerald-300 break-all leading-relaxed">
              {finding.evidence}
            </div>
          </div>

          {/* Grid for Issue & Impact */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3.5 rounded-lg bg-obsidian-800 border border-obsidian-700/70">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-400 mb-1">
                Issue Description
              </div>
              <p className="text-xs text-slate-200 leading-relaxed">
                {finding.issue}
              </p>
            </div>

            <div className="p-3.5 rounded-lg bg-obsidian-800 border border-obsidian-700/70">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-400 mb-1">
                Technical Impact
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {finding.impact}
              </p>
            </div>
          </div>

          {/* Recommendation */}
          <div className="p-3.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-400 mb-1 flex items-center gap-1.5">
              <Lightbulb className="w-3.5 h-3.5 text-emerald-400" />
              <span>Remediation Guidance</span>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed">
              {finding.recommendation}
            </p>
          </div>

          {/* Footer stats: Confidence & Rule ID */}
          <div className="flex items-center justify-between pt-2 text-[11px] text-slate-400">
            <div className="flex items-center gap-2">
              <Gauge className="w-3.5 h-3.5 text-slate-400" />
              <span>Confidence: <strong className="text-white font-mono">{finding.confidence}%</strong></span>
            </div>
            <span className="font-mono text-slate-500 text-[10px]">
              ID: {finding.rule_id}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
