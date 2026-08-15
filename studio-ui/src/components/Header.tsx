import React from 'react';
import { 
  Zap, 
  FolderOpen, 
  RefreshCw, 
  FileText, 
  ExternalLink,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import { ScanResult } from '../types';

interface HeaderProps {
  scanResult: ScanResult | null;
  loading: boolean;
  onOpenBrowser: () => void;
  onRescan: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scanResult,
  loading,
  onOpenBrowser,
  onRescan,
}) => {
  return (
    <header className="h-16 border-b border-obsidian-700/80 bg-obsidian-900/90 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Active Report */}
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Zap className="w-4 h-4 text-white fill-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-white">pbiscan</span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Studio
              </span>
            </div>
          </div>
        </div>

        <div className="h-4 w-px bg-obsidian-700 hidden sm:block" />

        {/* Current Project Pill */}
        {scanResult ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-obsidian-800 border border-obsidian-700 text-xs text-slate-300 truncate max-w-md">
            <FileText className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="font-medium text-white truncate">{scanResult.report_name}</span>
            <span className="text-slate-500 text-[11px] truncate hidden md:inline">
              ({scanResult.source_path})
            </span>
          </div>
        ) : (
          <span className="text-xs text-slate-500 hidden sm:inline">No report loaded</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2.5">
        <button
          onClick={onOpenBrowser}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-obsidian-800 hover:bg-obsidian-700 text-slate-200 border border-obsidian-700 hover:border-slate-600 transition text-xs font-medium"
          title="Open a different .pbip project"
        >
          <FolderOpen className="w-3.5 h-3.5 text-emerald-400" />
          <span>Open Project</span>
        </button>

        {scanResult && (
          <button
            onClick={onRescan}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:border-emerald-500/50 transition text-xs font-medium disabled:opacity-50"
            title="Re-scan current project"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Re-scan</span>
          </button>
        )}

        <a
          href="https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner"
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-md text-slate-400 hover:text-white hover:bg-obsidian-800 transition"
          title="View on GitHub"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </header>
  );
};
