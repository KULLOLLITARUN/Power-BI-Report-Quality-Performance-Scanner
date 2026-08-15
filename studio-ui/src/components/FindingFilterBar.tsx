import React from 'react';
import { Search, X } from 'lucide-react';

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
    <div 
      className="p-3 rounded border space-y-2.5"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
      }}
    >
      <div className="flex flex-col sm:flex-row items-center gap-2.5">
        <div className="relative flex-1 w-full">
          <Search 
            className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2" 
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            placeholder="Filter by rule, table, measure, or keyword..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-primary)',
            }}
          />
        </div>

        <div className="text-xs font-mono shrink-0 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
          <span>
            {filteredCount} of {totalCount} findings
          </span>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-[11px] hover:underline font-mono"
              style={{ color: 'var(--accent)' }}
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      <div 
        className="flex flex-wrap items-center gap-1.5 pt-1 border-t text-xs font-mono"
        style={{ borderColor: 'var(--border-hairline)' }}
      >
        <span className="text-[10px] font-medium mr-1 uppercase" style={{ color: 'var(--text-muted)' }}>
          Category:
        </span>
        {categories.map((cat) => {
          const isActive = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => onCategoryChange(cat)}
              className="px-2 py-0.5 rounded text-[10px] font-mono transition border"
              style={{
                backgroundColor: isActive ? 'var(--accent-muted)' : 'transparent',
                borderColor: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: isActive ? 'bold' : 'normal',
              }}
            >
              {cat.toUpperCase()}
            </button>
          );
        })}

        <div className="h-3 w-px mx-1 hidden sm:block" style={{ backgroundColor: 'var(--border-strong)' }} />

        <span className="text-[10px] font-medium mr-1 uppercase" style={{ color: 'var(--text-muted)' }}>
          Severity:
        </span>
        {severities.map((sev) => {
          const isActive = selectedSeverity === sev;
          return (
            <button
              key={sev}
              onClick={() => onSeverityChange(sev)}
              className="px-2 py-0.5 rounded text-[10px] font-mono transition border"
              style={{
                backgroundColor: isActive ? 'var(--accent-muted)' : 'transparent',
                borderColor: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: isActive ? 'bold' : 'normal',
              }}
            >
              {sev}
            </button>
          );
        })}
      </div>
    </div>
  );
};
