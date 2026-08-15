import React from 'react';
import { 
  Sun,
  Moon,
  FolderOpen,
  RotateCcw
} from 'lucide-react';
import { ScanResult } from '../types';
import { Theme } from '../hooks/useTheme';

interface HeaderProps {
  scanResult: ScanResult | null;
  onNativeBrowse: () => void;
  onResetToHome: () => void;
  theme?: Theme;
  onToggleTheme?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scanResult,
  onNativeBrowse,
  onResetToHome,
  theme = 'dark',
  onToggleTheme,
}) => {
  return (
    <header 
      className="h-14 px-6 flex items-center justify-between sticky top-0 z-40 border-b select-none"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
      }}
    >
      {/* Brand & Subtitle */}
      <div className="flex items-center gap-3.5 shrink-0">
        <button 
          onClick={onResetToHome}
          className="flex items-center gap-3 hover:opacity-90 transition text-left"
          title="Return to Home"
        >
          <div 
            className="w-8 h-8 rounded-sm flex items-center justify-center font-bold text-xs font-mono shadow-sm"
            style={{
              backgroundColor: 'var(--accent)',
              color: 'var(--bg-canvas)',
            }}
          >
            PS
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span 
                className="font-mono font-bold text-sm tracking-tight"
                style={{ color: 'var(--text-primary)' }}
              >
                PBIP Sentinel
              </span>
              <span 
                className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded border hidden sm:inline"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-strong)',
                  color: 'var(--text-muted)',
                }}
              >
                v0.1.0
              </span>
            </div>
            <p 
              className="text-[11px] font-mono leading-none mt-0.5 hidden md:block"
              style={{ color: 'var(--text-muted)' }}
            >
              Power BI Semantic Model &amp; DAX Diagnostic Engine
            </p>
          </div>
        </button>
      </div>

      {/* Center / Right: Active Project Status & Controls */}
      <div className="flex items-center gap-3 shrink-0">
        {scanResult && (
          <div className="flex items-center gap-2 mr-2">
            <div 
              className="px-3 py-1 rounded border font-mono text-xs flex items-center gap-2"
              style={{
                backgroundColor: 'var(--bg-canvas)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
              <span className="font-semibold max-w-[240px] truncate" style={{ color: 'var(--text-primary)' }}>
                {scanResult.report_name}
              </span>
            </div>

            <button
              onClick={onResetToHome}
              className="px-2.5 py-1 rounded border font-mono text-xs flex items-center gap-1.5 transition"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-strong)',
                color: 'var(--text-secondary)',
              }}
              title="Open another report project"
            >
              <FolderOpen className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
              <span className="hidden sm:inline">Change Project</span>
            </button>
          </div>
        )}

        {/* Theme Toggle Button */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            className="px-2.5 py-1 rounded border transition flex items-center gap-1.5 font-mono text-xs"
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
                <span>Light</span>
              </>
            ) : (
              <>
                <Moon className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
                <span>Dark</span>
              </>
            )}
          </button>
        )}
      </div>
    </header>
  );
};
