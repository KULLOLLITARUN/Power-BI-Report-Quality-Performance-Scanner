import React from 'react';
import { 
  LayoutDashboard, 
  Network, 
  Code2, 
  Layers,
  FolderOpen,
  GitCompare
} from 'lucide-react';

export type TabType = 'dashboard' | 'model-map' | 'dax-explorer' | 'pages' | 'diff';

interface SidebarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  findingsCount: number;
  tablesCount: number;
  measuresCount: number;
  pagesCount: number;
  onNewScan: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  findingsCount,
  tablesCount,
  measuresCount,
  pagesCount,
  onNewScan,
}) => {
  const navItems = [
    {
      id: 'dashboard' as TabType,
      label: 'Audit Overview',
      icon: LayoutDashboard,
      badge: findingsCount > 0 ? findingsCount : undefined,
    },
    {
      id: 'model-map' as TabType,
      label: 'Model Architecture',
      icon: Network,
      badge: tablesCount > 0 ? `${tablesCount}` : undefined,
    },
    {
      id: 'dax-explorer' as TabType,
      label: 'DAX Measures',
      icon: Code2,
      badge: measuresCount > 0 ? `${measuresCount}` : undefined,
    },
    {
      id: 'pages' as TabType,
      label: 'Visual Pages',
      icon: Layers,
      badge: pagesCount > 0 ? `${pagesCount}` : undefined,
    },
    {
      id: 'diff' as TabType,
      label: 'Compare / Diff',
      icon: GitCompare,
    },
  ];

  return (
    <aside 
      className="w-56 border-r p-3 flex flex-col justify-between shrink-0 h-[calc(100vh-3.5rem)] select-none transition-colors duration-150"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border-hairline)',
      }}
    >
      <div className="space-y-1">
        <div 
          className="text-[11px] font-mono font-medium uppercase tracking-wider px-2.5 py-1 mb-1"
          style={{ color: 'var(--text-muted)' }}
        >
          Navigation
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className="w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-mono font-medium transition border"
              style={{
                backgroundColor: isActive ? 'var(--accent-muted)' : 'transparent',
                borderColor: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: isActive ? 'bold' : 'normal',
              }}
            >
              <div className="flex items-center gap-2.5">
                <Icon 
                  className="w-4 h-4" 
                  style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)' }} 
                />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span 
                  className="text-[10px] px-1.5 py-0.2 rounded border font-mono font-bold"
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    borderColor: 'var(--border-strong)',
                    color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer / Info */}
      <div 
        className="space-y-2 pt-3 border-t font-mono"
        style={{ borderColor: 'var(--border-hairline)' }}
      >
        <button
          onClick={onNewScan}
          className="w-full py-1.5 px-2.5 rounded border text-xs flex items-center justify-center gap-1.5 transition font-medium"
          style={{
            backgroundColor: 'var(--bg-canvas)',
            borderColor: 'var(--border-hairline)',
            color: 'var(--text-secondary)',
          }}
        >
          <FolderOpen className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
          <span>Open Another PBIP</span>
        </button>

        <div className="flex items-center justify-between text-[10px] px-1" style={{ color: 'var(--text-muted)' }}>
          <span>PBIP Sentinel Engine</span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
            Ready
          </span>
        </div>
      </div>
    </aside>
  );
};
