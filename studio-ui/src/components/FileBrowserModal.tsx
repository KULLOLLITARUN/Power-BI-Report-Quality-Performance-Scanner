import React, { useState, useEffect } from 'react';
import { 
  Folder, 
  FileText, 
  ChevronRight, 
  ArrowLeft, 
  X, 
  Check, 
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
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-obsidian-900 border border-obsidian-700 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-4 border-b border-obsidian-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white">Select Power BI Project (.pbip)</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-obsidian-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Path Navigation Bar */}
        <div className="p-3 bg-obsidian-950 border-b border-obsidian-700 flex items-center gap-2">
          {browseData?.parent_path && (
            <button
              onClick={() => fetchDirectory(browseData.parent_path!)}
              className="p-1.5 rounded bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 border border-obsidian-700"
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
            className="flex-1 px-3 py-1.5 bg-obsidian-900 border border-obsidian-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
          />

          <button
            onClick={() => fetchDirectory(manualPath)}
            className="px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded text-xs font-medium"
          >
            Go
          </button>
        </div>

        {/* Directory & PBIP List */}
        <div className="p-3 max-h-[380px] overflow-y-auto space-y-1">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-400 text-xs gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
              <span>Browsing filesystem...</span>
            </div>
          ) : (
            <>
              {/* PBIP Project Candidates */}
              {browseData?.pbip_projects && browseData.pbip_projects.length > 0 && (
                <div className="space-y-1 mb-3">
                  <div className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider px-2 py-1">
                    Power BI Projects Found
                  </div>
                  {browseData.pbip_projects.map((proj) => (
                    <div
                      key={proj.path}
                      onClick={() => {
                        onSelectProject(proj.path);
                        onClose();
                      }}
                      className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 cursor-pointer transition flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="font-bold text-white truncate">{proj.name}</span>
                      </div>
                      <span className="text-[11px] font-medium text-emerald-300 shrink-0 flex items-center gap-1">
                        <span>Scan Project</span>
                        <ChevronRight className="w-3 h-3" />
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Subdirectories */}
              {browseData?.directories && browseData.directories.length > 0 ? (
                <div className="space-y-0.5">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-2 py-1">
                    Folders
                  </div>
                  {browseData.directories.map((dir) => (
                    <div
                      key={dir.path}
                      onClick={() => fetchDirectory(dir.path)}
                      className="p-2 rounded-md hover:bg-obsidian-800 cursor-pointer transition flex items-center justify-between text-xs text-slate-300"
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <Folder className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        <span className="truncate">{dir.name}</span>
                      </div>
                      <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-xs text-slate-500">No subfolders</div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-obsidian-700 bg-obsidian-950 flex items-center justify-between text-xs text-slate-400">
          <span>Click any project to load into Studio</span>
          <button
            onClick={() => {
              if (currentPath) {
                onSelectProject(currentPath);
                onClose();
              }
            }}
            className="px-3 py-1.5 bg-obsidian-800 hover:bg-obsidian-700 text-white rounded border border-obsidian-700 font-medium transition"
          >
            Scan Current Folder
          </button>
        </div>
      </div>
    </div>
  );
};
