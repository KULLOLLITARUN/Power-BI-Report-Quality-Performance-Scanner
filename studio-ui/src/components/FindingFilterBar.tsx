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
    <div className="p-3.5 rounded-xl bg-obsidian-800/80 border border-obsidian-700 space-y-3">
      <div className="flex flex-col sm:flex-row items-center gap-3">
        {/* Search Box */}
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search findings by rule, table, measure, or keyword..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-obsidian-950 border border-obsidian-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
          />
        </div>

        {/* Count indicator */}
        <div className="text-xs text-slate-400 font-mono shrink-0 flex items-center gap-2">
          <span>
            Showing <strong className="text-white">{filteredCount}</strong> of <strong className="text-white">{totalCount}</strong>
          </span>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 font-sans font-medium"
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Badges */}
      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-obsidian-700/60">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mr-1 flex items-center gap-1">
          <Filter className="w-3 h-3" />
          Category:
        </span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat)}
            className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium transition ${
              selectedCategory === cat
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'bg-obsidian-900 text-slate-400 hover:text-slate-200 border border-obsidian-700'
            }`}
          >
            {cat.toUpperCase()}
          </button>
        ))}

        <div className="h-3.5 w-px bg-obsidian-700 mx-1 hidden sm:block" />

        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mr-1">
          Severity:
        </span>
        {severities.map((sev) => (
          <button
            key={sev}
            onClick={() => onSeverityChange(sev)}
            className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium transition ${
              selectedSeverity === sev
                ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                : 'bg-obsidian-900 text-slate-400 hover:text-slate-200 border border-obsidian-700'
            }`}
          >
            {sev}
          </button>
        ))}
      </div>
    </div>
  );
};
