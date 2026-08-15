import React from 'react';
import { 
  FolderOpen, 
  Play, 
  RefreshCw, 
  FileText, 
  ExternalLink,
  ChevronRight,
  ArrowLeft
} from 'lucide-react';
import { ScanResult } from '../types';

interface HeaderProps {
  scanResult: ScanResult | null;
  currentPath: string;
  onPathChange: (path: string) => void;
  loading: boolean;
  onRunScan: (path: string) => void;
  onNativeBrowse: () => void;
  onResetToHome: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scanResult,
  currentPath,
  onPathChange,
  loading,
  onRunScan,
  onNativeBrowse,
  onResetToHome,
}) => {
  return (
    <header className="h-14 border-b border-studio-border bg-studio-sidebar px-5 flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Breadcrumb */}
      <div className="flex items-center gap-3 shrink-0">
        <button 
          onClick={onResetToHome}
          className="flex items-center gap-2.5 hover:opacity-85 transition text-left"
          title="Return to Home"
        >
          <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-sm">
            PB
          </div>
          <div>
            <span className="font-semibold text-sm tracking-tight text-white font-sans">
              pbiscan Studio
            </span>
          </div>
        </button>

        {scanResult && (
          <div className="flex items-center gap-2 text-xs text-studio-textMuted ml-2 border-l border-studio-border pl-3">
            <span className="font-mono text-slate-400 max-w-[200px] truncate">
              {scanResult.report_name}
            </span>
          </div>
        )}
      </div>

      {/* Center: File Input & Quick Run (Active when viewing report or typing) */}
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
            className="w-full pl-3 pr-20 py-1.5 bg-studio-bg border border-studio-border rounded-md text-xs text-studio-text placeholder-studio-subtle focus:outline-none focus:border-blue-500 font-mono transition"
          />
          <button
            onClick={onNativeBrowse}
            className="absolute right-1 px-2 py-0.5 rounded bg-studio-card hover:bg-studio-cardHover text-slate-300 border border-studio-border text-[11px] font-medium flex items-center gap-1 transition"
          >
            <FolderOpen className="w-3 h-3 text-blue-400" />
            <span>Browse</span>
          </button>
        </div>

        <button
          onClick={() => onRunScan(currentPath)}
          disabled={loading || !currentPath.trim()}
          className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center gap-1.5 transition disabled:opacity-40 disabled:cursor-not-allowed shrink-0 shadow-sm"
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-white" />
          )}
          <span>{loading ? 'Analyzing...' : 'Scan'}</span>
        </button>
      </div>

      {/* Right Tools */}
      <div className="flex items-center gap-3 shrink-0 text-xs">
        <a
          href="https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner"
          target="_blank"
          rel="noopener noreferrer"
          className="text-studio-subtle hover:text-studio-text transition flex items-center gap-1"
          title="GitHub Repository"
        >
          <span>Docs &amp; GitHub</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </header>
  );
};
