import React, { useState } from 'react';
import { 
  Zap, 
  FolderOpen, 
  Play, 
  RefreshCw, 
  FileText, 
  ExternalLink,
  Moon,
  Sun,
  HardDrive,
  CheckCircle2
} from 'lucide-react';
import { ScanResult } from '../types';

interface HeaderProps {
  scanResult: ScanResult | null;
  currentPath: string;
  onPathChange: (path: string) => void;
  loading: boolean;
  onRunScan: (path: string) => void;
  onOpenBrowserModal: () => void;
  onNativeBrowse: () => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scanResult,
  currentPath,
  onPathChange,
  loading,
  onRunScan,
  onOpenBrowserModal,
  onNativeBrowse,
  theme,
  onToggleTheme,
}) => {
  return (
    <header className="h-16 border-b border-slate-700/80 bg-slate-900/95 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-md shadow-blue-500/20">
          <Zap className="w-4 h-4 text-white fill-white" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-bold text-base tracking-tight text-white font-sans">pbiscan</span>
          <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Studio
          </span>
        </div>
      </div>

      {/* Center: File Browse & Run Controls (Direct from UI) */}
      <div className="flex-1 max-w-2xl mx-6 flex items-center gap-2">
        <div className="relative flex-1 flex items-center">
          <div className="absolute left-3 text-slate-400">
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <input
            type="text"
            value={currentPath}
            onChange={(e) => onPathChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && currentPath.trim()) {
                onRunScan(currentPath);
              }
            }}
            placeholder="Select or enter path to .pbip report project..."
            className="w-full pl-9 pr-24 py-1.5 bg-slate-950/80 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono transition"
          />
          {/* Quick Browse button inside input */}
          <button
            onClick={onNativeBrowse}
            className="absolute right-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 text-[11px] font-medium flex items-center gap-1 transition"
            title="Browse folder from your computer"
          >
            <FolderOpen className="w-3 h-3 text-blue-400" />
            <span>Browse</span>
          </button>
        </div>

        {/* Run Audit Button */}
        <button
          onClick={() => onRunScan(currentPath)}
          disabled={loading || !currentPath.trim()}
          className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center gap-1.5 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-white" />
          )}
          <span>{loading ? 'Scanning...' : 'Run Audit'}</span>
        </button>
      </div>

      {/* Right Tools */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onOpenBrowserModal}
          className="px-2.5 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-medium flex items-center gap-1.5 transition hidden lg:flex"
          title="Open in-app folder explorer"
        >
          <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
          <span>Explorer</span>
        </button>

        <a
          href="https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner"
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
          title="GitHub Repository"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </header>
  );
};
