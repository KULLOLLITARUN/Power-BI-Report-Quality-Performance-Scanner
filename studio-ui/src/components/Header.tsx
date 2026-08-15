import React from 'react';
import { 
  FolderOpen, 
  Play, 
  RefreshCw, 
  ExternalLink,
  Sun,
  Moon
} from 'lucide-react';
import { ScanResult } from '../types';
import { Theme } from '../hooks/useTheme';

interface HeaderProps {
  scanResult: ScanResult | null;
  currentPath: string;
  onPathChange: (path: string) => void;
  loading: boolean;
  onRunScan: (path: string) => void;
  onNativeBrowse: () => void;
  onResetToHome: () => void;
  theme?: Theme;
  onToggleTheme?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scanResult,
  currentPath,
  onPathChange,
  loading,
  onRunScan,
  onNativeBrowse,
  onResetToHome,
  theme = 'dark',
  onToggleTheme,
}) => {
  return (
    <header 
      className="h-14 px-5 flex items-center justify-between sticky top-0 z-40 border-b"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
      }}
    >
      {/* Brand & Breadcrumb */}
      <div className="flex items-center gap-3 shrink-0">
        <button 
          onClick={onResetToHome}
          className="flex items-center gap-2.5 hover:opacity-85 transition text-left"
          title="Return to Home"
        >
          <div 
            className="w-7 h-7 rounded-sm flex items-center justify-center font-bold text-xs font-mono"
            style={{
              backgroundColor: 'var(--accent)',
              color: 'var(--bg-canvas)',
            }}
          >
            PB
          </div>
          <div>
            <span 
              className="font-bold text-sm tracking-tight font-mono"
              style={{ color: 'var(--text-primary)' }}
            >
              pbiscan Studio
            </span>
          </div>
        </button>

        {scanResult && (
          <div 
            className="flex items-center gap-2 text-xs ml-2 border-l pl-3 font-mono"
            style={{ 
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-secondary)',
            }}
          >
            <span className="max-w-[200px] truncate">
              {scanResult.report_name}
            </span>
          </div>
        )}
      </div>

      {/* Center: File Input & Quick Run */}
      <div className="flex-1 max-w-xl mx-6 flex items-center gap-2">
        <div className="relative flex-1 flex items-center">
          <input
            type="text"
            value={currentPath}
            onChange={(e) => onPathChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && currentPath.trim()) {
                onRunScan(currentPath);
              }
            }}
            placeholder="Folder or path to .pbip project..."
            className="w-full pl-3 pr-20 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-primary)',
            }}
          />
          <button
            onClick={onNativeBrowse}
            className="absolute right-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium flex items-center gap-1 transition border"
            style={{
              backgroundColor: 'var(--bg-surface)',
              borderColor: 'var(--border-strong)',
              color: 'var(--text-secondary)',
            }}
          >
            <FolderOpen className="w-3 h-3" style={{ color: 'var(--text-primary)' }} />
            <span>Browse</span>
          </button>
        </div>

        <button
          onClick={() => onRunScan(currentPath)}
          disabled={loading || !currentPath.trim()}
          className="px-3.5 py-1.5 rounded font-mono font-bold text-xs flex items-center gap-1.5 transition disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
          style={{
            backgroundColor: 'var(--accent)',
            color: 'var(--bg-canvas)',
          }}
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-current" />
          )}
          <span>{loading ? 'Analyzing...' : 'Scan'}</span>
        </button>
      </div>

      {/* Right Tools: Theme Toggle & GitHub Link */}
      <div className="flex items-center gap-3 shrink-0 text-xs">
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded border transition flex items-center gap-1.5 font-mono text-[11px]"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-secondary)',
            }}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Theme`}
          >
            {theme === 'dark' ? (
              <>
                <Sun className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
                <span className="hidden sm:inline">Light</span>
              </>
            ) : (
              <>
                <Moon className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
                <span className="hidden sm:inline">Dark</span>
              </>
            )}
          </button>
        )}

        <a
          href="https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner"
          target="_blank"
          rel="noopener noreferrer"
          className="transition flex items-center gap-1 font-mono text-[11px]"
          style={{ color: 'var(--text-muted)' }}
          title="GitHub Repository"
        >
          <span className="hidden sm:inline">GitHub</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </header>
  );
};
