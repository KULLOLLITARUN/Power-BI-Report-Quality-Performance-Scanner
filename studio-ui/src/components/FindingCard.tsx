import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronRight,
  CheckCircle2,
  FileCode2,
  Sparkles
} from 'lucide-react';
import { AuditFinding } from '../types';
import { highlightDax } from '../utils/daxHighlighter';

interface FindingCardProps {
  finding: AuditFinding;
  index: number;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding }) => {
  const [expanded, setExpanded] = useState(false);

  const getSeverityStyle = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return {
          stripe: 'var(--severity-critical)',
          bg: 'var(--severity-critical-bg)',
          border: 'var(--severity-critical-border)',
          color: 'var(--severity-critical)',
        };
      case 'HIGH':
        return {
          stripe: 'var(--severity-high)',
          bg: 'var(--severity-high-bg)',
          border: 'var(--severity-high-border)',
          color: 'var(--severity-high)',
        };
      case 'MEDIUM':
        return {
          stripe: 'var(--severity-medium)',
          bg: 'var(--severity-medium-bg)',
          border: 'var(--severity-medium-border)',
          color: 'var(--severity-medium)',
        };
      case 'WARNING':
        return {
          stripe: 'var(--severity-warning)',
          bg: 'var(--severity-warning-bg)',
          border: 'var(--severity-warning-border)',
          color: 'var(--severity-warning)',
        };
      case 'ADVISORY':
      default:
        return {
          stripe: 'var(--severity-advisory)',
          bg: 'var(--severity-advisory-bg)',
          border: 'var(--severity-advisory-border)',
          color: 'var(--severity-advisory)',
        };
    }
  };

  const sevStyle = getSeverityStyle(finding.severity);
  const confidence = finding.confidence ?? 100;
  const isDax = (finding.category || '').toLowerCase() === 'dax';

  // Only extract real DAX formula snippet if rule flagged an actual code pattern
  let daxSnippet = '';
  if (finding.rule_id === 'DAX_SUSPICIOUS_PATTERN' || finding.rule_id === 'DAX_EXPENSIVE_PATTERN') {
    if (finding.evidence && finding.evidence.includes('=')) {
      const cand = finding.evidence.split('=').slice(1).join('=').trim();
      if (!cand.startsWith('[') && !cand.startsWith('not referenced')) {
        daxSnippet = cand;
      }
    }
  }

  return (
    <div 
      className="rounded border overflow-hidden transition-all duration-150"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
        borderLeftWidth: '4px',
        borderLeftColor: sevStyle.stripe,
      }}
    >
      {/* Header Row */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 cursor-pointer select-none"
        style={{
          borderBottom: expanded ? '1px solid var(--border-hairline)' : 'none',
        }}
      >
        {/* Left Side: Severity Badge, Rule ID, Location & Title */}
        <div className="flex items-start md:items-center gap-3 min-w-0 flex-1">
          {/* Severity Square Tag */}
          <span 
            className="px-1.5 py-0.5 rounded-sm font-mono text-[10px] font-bold tracking-wider uppercase shrink-0 border"
            style={{
              backgroundColor: sevStyle.bg,
              borderColor: sevStyle.border,
              color: sevStyle.color,
            }}
          >
            {finding.severity}
          </span>

          {/* Rule ID */}
          <span 
            className="font-mono text-xs font-semibold shrink-0"
            style={{ color: 'var(--text-primary)' }}
          >
            {finding.rule_id}
          </span>

          <span style={{ color: 'var(--border-strong)' }}>·</span>

          {/* Title & Target Location */}
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2 truncate">
              <span className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                {finding.title}
              </span>
              {finding.location && (
                <span className="font-mono text-[11px] truncate hidden lg:inline" style={{ color: 'var(--text-secondary)' }}>
                  [{finding.location}]
                </span>
              )}
            </div>

            {finding.location && (
              <div className="font-mono text-[11px] truncate lg:hidden mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                {finding.location}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Continuous Confidence Meter & Expand Toggle */}
        <div className="flex items-center gap-4 shrink-0 justify-between md:justify-end pt-1 md:pt-0">
          {/* Confidence Continuous Percentage Bar (Decoupled Flat Neutral) */}
          <div className="flex items-center gap-2">
            <span 
              className="text-[10px] font-mono font-medium tracking-wide uppercase"
              style={{ color: 'var(--text-muted)' }}
            >
              Confidence
            </span>

            {/* Continuous Progress Bar */}
            <div 
              className="w-16 h-1.5 rounded-sm overflow-hidden"
              style={{ backgroundColor: 'var(--confidence-track)' }}
              title={`${confidence}% Diagnostic Certainty`}
            >
              <div 
                className="h-full rounded-sm transition-all duration-300"
                style={{ 
                  width: `${confidence}%`,
                  backgroundColor: 'var(--confidence-meter)',
                }}
              />
            </div>

            <span 
              className="font-mono text-xs font-bold w-9 text-right"
              style={{ color: 'var(--text-secondary)' }}
            >
              {confidence}%
            </span>
          </div>

          <div style={{ color: 'var(--text-muted)' }}>
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Inline DAX Snippet (Domain-Specific Detail for DAX Findings) */}
      {isDax && daxSnippet && !expanded && (
        <div 
          className="px-4 py-2 border-t font-mono text-[11px] truncate flex items-center gap-2"
          style={{
            backgroundColor: 'var(--bg-code)',
            borderColor: 'var(--border-hairline)',
            color: 'var(--text-secondary)',
          }}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider shrink-0" style={{ color: 'var(--text-muted)' }}>
            DAX:
          </span>
          <span className="truncate">
            {daxSnippet}
          </span>
        </div>
      )}

      {/* Expanded 4-Part Diagnostic Inspection Body */}
      {expanded && (
        <div 
          className="p-4 space-y-4"
          style={{
            backgroundColor: 'var(--bg-canvas)',
          }}
        >
          {/* 1. Evidence / Raw Signal */}
          <div className="space-y-1.5">
            <div className="text-[11px] font-mono font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Evidence / Detected Signal
            </div>
            <div 
              className="p-3 rounded border font-mono text-xs overflow-x-auto leading-relaxed"
              style={{
                backgroundColor: 'var(--bg-code)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
              }}
            >
              {isDax && daxSnippet ? highlightDax(daxSnippet) : finding.evidence}
            </div>
          </div>

          {/* 2. Technical Impact & 3. Remediation Contract */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div 
              className="p-3.5 rounded border space-y-1"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div className="text-[11px] font-mono font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Architectural Impact
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {finding.impact}
              </p>
            </div>

            <div 
              className="p-3.5 rounded border space-y-1"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
                borderLeftWidth: '3px',
                borderLeftColor: 'var(--accent)',
              }}
            >
              <div className="text-[11px] font-mono font-medium uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                Remediation Guidance
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                {finding.recommendation}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
