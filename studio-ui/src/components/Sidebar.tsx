import React from 'react';
import { 
  LayoutDashboard, 
  Network, 
  Code2, 
  FileSpreadsheet, 
  AlertTriangle,
  Layers
} from 'lucide-react';

export type TabType = 'dashboard' | 'model-map' | 'dax-explorer' | 'pages';

interface SidebarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  findingsCount: number;
  tablesCount: number;
  measuresCount: number;
  pagesCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  findingsCount,
  tablesCount,
  measuresCount,
  pagesCount,
}) => {
  const navItems = [
    {
      id: 'dashboard' as TabType,
      label: 'Audit Dashboard',
      icon: LayoutDashboard,
      badge: findingsCount > 0 ? findingsCount : undefined,
      badgeColor: findingsCount > 0 ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : undefined,
    },
    {
      id: 'model-map' as TabType,
      label: 'Semantic Model Map',
      icon: Network,
      badge: tablesCount > 0 ? `${tablesCount} tables` : undefined,
      badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    },
    {
      id: 'dax-explorer' as TabType,
      label: 'DAX Explorer',
      icon: Code2,
      badge: measuresCount > 0 ? `${measuresCount} measures` : undefined,
      badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    },
    {
      id: 'pages' as TabType,
      label: 'Report Pages',
      icon: Layers,
      badge: pagesCount > 0 ? `${pagesCount} pages` : undefined,
      badgeColor: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    },
  ];

  return (
    <aside className="w-64 border-r border-obsidian-700/80 bg-obsidian-900/60 p-4 flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)]">
      <div className="space-y-1">
        <div className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase px-3 mb-2">
          Workspace
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-obsidian-800 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${
                    item.badgeColor || 'bg-obsidian-800 text-slate-400 border-obsidian-700'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="p-3 rounded-lg bg-obsidian-800/80 border border-obsidian-700 text-[11px] text-slate-400 space-y-1">
        <div className="flex items-center justify-between">
          <span>Engine</span>
          <span className="font-mono text-emerald-400 font-medium">v0.1.0</span>
        </div>
        <div className="flex items-center justify-between text-slate-500">
          <span>Mode</span>
          <span>Static Offline</span>
        </div>
      </div>
    </aside>
  );
};
