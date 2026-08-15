import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  AlertTriangle, 
  AlertCircle, 
  Info,
  Lightbulb,
  Tag
} from 'lucide-react';
import { AuditFinding } from '../types';

interface FindingCardProps {
  finding: AuditFinding;
  index: number;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding }) => {
  const [expanded, setExpanded] = useState(false);

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return { bg: 'bg-red-500/10 text-red-400 border-red-500/30', icon: AlertCircle };
      case 'HIGH':
        return { bg: 'bg-orange-500/10 text-orange-400 border-orange-500/30', icon: AlertTriangle };
      case 'MEDIUM':
        return { bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30', icon: AlertTriangle };
      case 'WARNING':
        return { bg: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30', icon: AlertTriangle };
      case 'ADVISORY':
        return { bg: 'bg-blue-500/10 text-blue-400 border-blue-500/30', icon: Info };
      default:
        return { bg: 'bg-slate-500/10 text-slate-400 border-slate-500/30', icon: Info };
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'model':
        return 'text-blue-400 border-blue-500/20 bg-blue-500/10';
      case 'dax':
        return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10';
      case 'report':
        return 'text-purple-400 border-purple-500/20 bg-purple-500/10';
      default:
        return 'text-slate-400 border-slate-500/20 bg-slate-500/10';
    }
  };

  const sev = getSeverityBadge(finding.severity);
  const SevIcon = sev.icon;

  return (
    <div className="rounded-lg bg-studio-card border border-studio-border hover:border-studio-borderLight transition overflow-hidden">
      {/* Header */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-3.5 flex items-center justify-between gap-4 cursor-pointer hover:bg-studio-cardHover transition select-none"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase border font-mono shrink-0 ${sev.bg}`}>
            <SevIcon className="w-3 h-3" />
            {finding.severity}
          </span>

          <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border font-mono shrink-0 ${getCategoryBadge(finding.category)}`}>
            {finding.category}
          </span>

          <div className="min-w-0">
            <h4 className="text-xs sm:text-sm font-semibold text-slate-200 truncate">
              {finding.title}
            </h4>
            {finding.location && (
              <p className="text-[11px] font-mono text-studio-subtle truncate mt-0.5">
                {finding.location}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="text-[11px] font-mono text-studio-subtle hidden sm:inline">
            {finding.rule_id}
          </span>
          <div className="text-studio-subtle">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 border-t border-studio-border bg-studio-bg/60 space-y-3.5">
          {/* Evidence */}
          <div>
            <div className="text-[10px] font-semibold uppercase text-studio-subtle mb-1 flex items-center gap-1">
              <Tag className="w-3 h-3 text-blue-400" />
              <span>Evidence Detail</span>
            </div>
            <div className="p-2.5 rounded bg-studio-bg border border-studio-border font-mono text-xs text-slate-200 leading-relaxed break-all">
              {finding.evidence}
            </div>
          </div>

          {/* Issue & Impact Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded bg-studio-card border border-studio-border">
              <div className="text-[10px] font-semibold uppercase text-studio-subtle mb-1">
                Issue Summary
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {finding.issue}
              </p>
            </div>

            <div className="p-3 rounded bg-studio-card border border-studio-border">
              <div className="text-[10px] font-semibold uppercase text-studio-subtle mb-1">
                Technical Impact
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {finding.impact}
              </p>
            </div>
          </div>

          {/* Remediation */}
          <div className="p-3 rounded bg-emerald-500/5 border border-emerald-500/20">
            <div className="text-[10px] font-semibold uppercase text-emerald-400 mb-1 flex items-center gap-1.5">
              <Lightbulb className="w-3.5 h-3.5 text-emerald-400" />
              <span>How to Fix</span>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed">
              {finding.recommendation}
            </p>
          </div>

          {/* Footer info */}
          <div className="flex items-center justify-between text-[11px] text-studio-subtle pt-1">
            <span>Confidence: <strong className="text-slate-300 font-mono">{finding.confidence}%</strong></span>
            <span className="font-mono text-[10px]">Rule ID: {finding.rule_id}</span>
          </div>
        </div>
      )}
    </div>
  );
};
