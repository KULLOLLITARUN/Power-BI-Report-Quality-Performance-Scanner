import React, { useState, useEffect } from 'react';
import { 
  Folder, 
  FileText, 
  ChevronRight, 
  ArrowLeft, 
  X, 
  HardDrive,
  RefreshCw
} from 'lucide-react';
import { BrowseResult } from '../types';

interface FileBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectProject: (path: string) => void;
}

export const FileBrowserModal: React.FC<FileBrowserModalProps> = ({
  isOpen,
  onClose,
  onSelectProject,
}) => {
  const [currentPath, setCurrentPath] = useState<string>('');
  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [manualPath, setManualPath] = useState('');

  const fetchDirectory = async (path?: string) => {
    setLoading(true);
    try {
      const res = await fetch('/api/browse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      if (res.ok) {
        const data: BrowseResult = await res.json();
        setBrowseData(data);
        setCurrentPath(data.current_path);
        setManualPath(data.current_path);
      }
    } catch (err) {
      console.error('Failed to browse path:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDirectory();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div 
        className="border rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150"
        style={{
          backgroundColor: 'var(--bg-surface-raised)',
          borderColor: 'var(--border-hairline)',
          color: 'var(--text-primary)',
          boxShadow: 'var(--shadow-raised)',
        }}
      >
        {/* Modal Header */}
        <div 
          className="p-4 border-b flex items-center justify-between"
          style={{ borderColor: 'var(--border-hairline)' }}
        >
          <div className="flex items-center gap-2.5">
            <HardDrive className="w-4 h-4" style={{ color: 'var(--accent)' }} />
            <h3 className="text-sm font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
              Select Power BI Project (.pbip)
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded transition"
            style={{ color: 'var(--text-muted)' }}
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Path Navigation Bar */}
        <div 
          className="p-3 border-b flex items-center gap-2"
          style={{ 
            backgroundColor: 'var(--bg-canvas)',
            borderColor: 'var(--border-hairline)',
          }}
        >
          {browseData?.parent_path && (
            <button
              onClick={() => fetchDirectory(browseData.parent_path!)}
              className="p-1.5 rounded border transition"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-strong)',
                color: 'var(--text-secondary)',
              }}
              title="Up one level"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
            </button>
          )}

          <input
            type="text"
            value={manualPath}
            onChange={(e) => setManualPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') fetchDirectory(manualPath);
            }}
            placeholder="Type or paste path..."
            className="flex-1 px-3 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
            style={{
              backgroundColor: 'var(--bg-surface)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-primary)',
            }}
          />

          <button
            onClick={() => fetchDirectory(manualPath)}
            className="px-3 py-1.5 rounded font-mono font-bold text-xs transition"
            style={{
              backgroundColor: 'var(--accent)',
              color: 'var(--bg-canvas)',
            }}
          >
            Go
          </button>
        </div>

        {/* Directory Listing Area */}
        <div 
          className="p-4 max-h-96 overflow-y-auto space-y-4"
          style={{ backgroundColor: 'var(--bg-surface)' }}
        >
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              <RefreshCw className="w-5 h-5 animate-spin" style={{ color: 'var(--accent)' }} />
              <span>Reading filesystem...</span>
            </div>
          ) : (
            <>
              {/* Found .pbip Projects */}
              {browseData?.pbip_projects && browseData.pbip_projects.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[10px] font-mono font-bold uppercase tracking-wider px-1" style={{ color: 'var(--accent)' }}>
                    Power BI Projects Found
                  </div>
                  <div className="space-y-1">
                    {browseData.pbip_projects.map((proj) => (
                      <div
                        key={proj.path}
                        onClick={() => {
                          onSelectProject(proj.path);
                          onClose();
                        }}
                        className="p-2.5 rounded border transition flex items-center justify-between cursor-pointer"
                        style={{
                          backgroundColor: 'var(--accent-muted)',
                          borderColor: 'var(--accent)',
                          color: 'var(--text-primary)',
                        }}
                      >
                        <div className="flex items-center gap-2 font-mono font-bold text-xs truncate">
                          <FileText className="w-4 h-4 shrink-0" style={{ color: 'var(--accent)' }} />
                          <span className="truncate">{proj.name}</span>
                        </div>
                        <span className="text-[11px] font-mono font-bold shrink-0" style={{ color: 'var(--accent)' }}>
                          Scan Project &rarr;
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Subfolders */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-mono font-medium uppercase tracking-wider px-1" style={{ color: 'var(--text-muted)' }}>
                  Folders
                </div>
                <div className="space-y-0.5">
                  {browseData?.directories.map((dir) => (
                    <div
                      key={dir.path}
                      onClick={() => fetchDirectory(dir.path)}
                      className="px-2.5 py-1.5 rounded transition flex items-center justify-between cursor-pointer text-xs font-mono"
                      style={{ color: 'var(--text-secondary)' }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--bg-canvas)';
                        e.currentTarget.style.color = 'var(--text-primary)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = 'var(--text-secondary)';
                      }}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Folder className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} />
                        <span className="truncate">{dir.name}</span>
                      </div>
                      <ChevronRight className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--text-muted)' }} />
                    </div>
                  ))}
                  {browseData?.directories.length === 0 && (!browseData.pbip_projects || browseData.pbip_projects.length === 0) && (
                    <div className="text-center py-6 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                      Folder is empty
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div 
          className="p-3 border-t flex items-center justify-between font-mono text-xs"
          style={{ 
            backgroundColor: 'var(--bg-canvas)',
            borderColor: 'var(--border-hairline)',
          }}
        >
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            Click any project to load into Sentinel
          </span>
          <button
            onClick={() => {
              if (currentPath) {
                onSelectProject(currentPath);
                onClose();
              }
            }}
            className="px-3 py-1 rounded border font-mono font-medium text-xs transition"
            style={{
              backgroundColor: 'var(--bg-surface)',
              borderColor: 'var(--border-strong)',
              color: 'var(--text-primary)',
            }}
          >
            Scan Current Folder
          </button>
        </div>
      </div>
    </div>
  );
};
