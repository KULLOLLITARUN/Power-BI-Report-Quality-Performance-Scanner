import React from 'react';
import { 
  LayoutDashboard, 
  Network, 
  Code2, 
  Layers,
  FolderOpen
} from 'lucide-react';

export type TabType = 'dashboard' | 'model-map' | 'dax-explorer' | 'pages';

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
      badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    },
    {
      id: 'model-map' as TabType,
      label: 'Model Architecture',
      icon: Network,
      badge: tablesCount > 0 ? `${tablesCount}` : undefined,
      badgeColor: 'bg-studio-border text-slate-400 border-studio-borderLight',
    },
    {
      id: 'dax-explorer' as TabType,
      label: 'DAX Measures',
      icon: Code2,
      badge: measuresCount > 0 ? `${measuresCount}` : undefined,
      badgeColor: 'bg-studio-border text-slate-400 border-studio-borderLight',
    },
    {
      id: 'pages' as TabType,
      label: 'Visual Pages',
      icon: Layers,
      badge: pagesCount > 0 ? `${pagesCount}` : undefined,
      badgeColor: 'bg-studio-border text-slate-400 border-studio-borderLight',
    },
  ];

  return (
    <aside className="w-56 border-r border-studio-border bg-studio-sidebar p-3 flex flex-col justify-between shrink-0 h-[calc(100vh-3.5rem)]">
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-studio-subtle uppercase tracking-wider px-2.5 py-1 mb-1">
          Navigation
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-2.5 py-2 rounded-md text-xs font-medium transition ${
                isActive
                  ? 'bg-blue-600/15 text-blue-300 border border-blue-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-studio-card border border-transparent'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="space-y-2 pt-3 border-t border-studio-border">
        <button
          onClick={onNewScan}
          className="w-full py-1.5 px-2.5 rounded-md bg-studio-card hover:bg-studio-cardHover text-slate-300 border border-studio-border text-xs flex items-center justify-center gap-1.5 transition"
        >
          <FolderOpen className="w-3.5 h-3.5 text-blue-400" />
          <span>Open Another PBIP</span>
        </button>

        <div className="px-1 text-[11px] text-studio-subtle flex items-center justify-between">
          <span>Engine v0.1.0</span>
          <span>Offline</span>
        </div>
      </div>
    </aside>
  );
};
