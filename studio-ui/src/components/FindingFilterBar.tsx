import React from 'react';
import { Search, Filter, X } from 'lucide-react';

interface FindingFilterBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedCategory: string;
  onCategoryChange: (cat: string) => void;
  selectedSeverity: string;
  onSeverityChange: (sev: string) => void;
  totalCount: number;
  filteredCount: number;
}

export const FindingFilterBar: React.FC<FindingFilterBarProps> = ({
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  selectedSeverity,
  onSeverityChange,
  totalCount,
  filteredCount,
}) => {
  const categories = ['all', 'model', 'dax', 'report'];
  const severities = ['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'WARNING', 'ADVISORY'];

  const hasActiveFilters = selectedCategory !== 'all' || selectedSeverity !== 'all' || searchQuery.trim() !== '';

  const clearFilters = () => {
    onSearchChange('');
    onCategoryChange('all');
    onSeverityChange('all');
  };

  return (
    <div className="p-3 rounded-lg bg-studio-card border border-studio-border space-y-2.5">
      <div className="flex flex-col sm:flex-row items-center gap-2.5">
        <div className="relative flex-1 w-full">
          <Search className="w-3.5 h-3.5 text-studio-subtle absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by rule, table, measure, or keyword..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-studio-bg border border-studio-border rounded-md text-xs text-studio-text placeholder-studio-subtle focus:outline-none focus:border-blue-500 font-mono transition"
          />
        </div>

        <div className="text-xs text-studio-subtle font-mono shrink-0 flex items-center gap-2">
          <span>
            {filteredCount} of {totalCount} findings
          </span>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-[11px] text-blue-400 hover:underline font-sans"
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-studio-border text-xs">
        <span className="text-[11px] font-medium text-studio-subtle mr-1">
          Category:
        </span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat)}
            className={`px-2 py-0.5 rounded text-[11px] font-mono transition ${
              selectedCategory === cat
                ? 'bg-blue-600/20 text-blue-300 border border-blue-500/40 font-semibold'
                : 'text-studio-subtle hover:text-slate-200 border border-transparent'
            }`}
          >
            {cat.toUpperCase()}
          </button>
        ))}

        <div className="h-3 w-px bg-studio-border mx-1 hidden sm:block" />

        <span className="text-[11px] font-medium text-studio-subtle mr-1">
          Severity:
        </span>
        {severities.map((sev) => (
          <button
            key={sev}
            onClick={() => onSeverityChange(sev)}
            className={`px-2 py-0.5 rounded text-[11px] font-mono transition ${
              selectedSeverity === sev
                ? 'bg-blue-600/20 text-blue-300 border border-blue-500/40 font-semibold'
                : 'text-studio-subtle hover:text-slate-200 border border-transparent'
            }`}
          >
            {sev}
          </button>
        ))}
      </div>
    </div>
  );
};
