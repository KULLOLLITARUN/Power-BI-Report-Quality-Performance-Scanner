import React, { useMemo, useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Node,
  Edge,
  BackgroundVariant,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { TableInfo, RelationshipInfo } from '../types';
import { 
  Database, 
  Search, 
  CheckSquare, 
  Square,
  Key,
  Layers,
  Code2,
  Table as TableIcon,
  X,
  Eye,
  EyeOff
} from 'lucide-react';

interface ModelMapProps {
  tables: TableInfo[];
  relationships: RelationshipInfo[];
}

// Custom Node Component for Power BI Tables
const TableNode: React.FC<{ data: any; selected: boolean }> = ({ data, selected }) => {
  const isDate = data.is_date_table || data.name.toLowerCase().includes('localdatetable') || data.name.toLowerCase().includes('datetabletemplate');
  const isHidden = data.hidden;
  const isFocused = data.isNeighborhoodFocus;

  return (
    <div
      className={`w-[240px] rounded-lg border text-left transition-all duration-150 shadow-md ${
        selected
          ? 'border-blue-500 ring-2 ring-blue-500/30 bg-studio-card'
          : isFocused
          ? 'border-blue-400/80 bg-studio-card'
          : 'border-studio-border bg-studio-card hover:border-studio-borderLight'
      }`}
    >
      {/* ReactFlow Connection Handles */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-2.5 h-2.5 bg-blue-500 border-2 border-studio-bg rounded-full"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-2.5 h-2.5 bg-blue-500 border-2 border-studio-bg rounded-full"
      />

      {/* Node Header */}
      <div className={`p-2.5 border-b flex items-center justify-between rounded-t-lg ${
        isDate 
          ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' 
          : 'bg-studio-bg border-studio-border text-slate-200'
      }`}>
        <div className="flex items-center gap-2 min-w-0">
          <Database className={`w-3.5 h-3.5 shrink-0 ${isDate ? 'text-amber-400' : 'text-blue-400'}`} />
          <span className="font-semibold text-xs truncate font-mono" title={data.name}>
            {data.name}
          </span>
        </div>

        {isHidden && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-studio-border text-studio-subtle">
            hidden
          </span>
        )}
      </div>

      {/* Node Summary Stats */}
      <div className="p-2.5 text-[11px] font-mono text-studio-subtle space-y-1">
        <div className="flex items-center justify-between">
          <span>Columns</span>
          <span className="text-slate-200 font-semibold">{data.column_count || 0}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Measures</span>
          <span className="text-emerald-400 font-semibold">{data.measures_count || 0}</span>
        </div>
        {data.calc_cols_count > 0 && (
          <div className="flex items-center justify-between">
            <span>Calc Columns</span>
            <span className="text-purple-400 font-semibold">{data.calc_cols_count}</span>
          </div>
        )}
      </div>
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

// Dagre Layout Engine
const computeDagreLayout = (
  nodes: Node[],
  edges: Edge[],
  direction = 'TB'
): { nodes: Node[]; edges: Edge[] } => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 70,
  });

  const nodeWidth = 240;
  const nodeHeight = 110;

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  try {
    dagre.layout(dagreGraph);
  } catch (err) {
    console.error('Dagre layout error:', err);
  }

  const layoutedNodes = nodes.map((node, idx) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const x = nodeWithPosition ? nodeWithPosition.x - nodeWidth / 2 : (idx % 4) * 280;
    const y = nodeWithPosition ? nodeWithPosition.y - nodeHeight / 2 : Math.floor(idx / 4) * 160;

    return {
      ...node,
      targetPosition: Position.Top,
      sourcePosition: Position.Bottom,
      position: { x, y },
    };
  });

  return { nodes: layoutedNodes, edges };
};

export const ModelMap: React.FC<ModelMapProps> = ({ tables = [], relationships = [] }) => {
  const [collapseDateTables, setCollapseDateTables] = useState(true);
  const [hideDisconnected, setHideDisconnected] = useState(false);
  const [searchTable, setSearchTable] = useState('');
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null);

  // Compute connected table set
  const connectedTableNames = useMemo(() => {
    const set = new Set<string>();
    relationships.forEach((rel) => {
      set.add(rel.from_table.toLowerCase());
      set.add(rel.to_table.toLowerCase());
    });
    return set;
  }, [relationships]);

  // Build raw nodes & edges
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => {
    // Filter tables
    const visibleTables = tables.filter((t) => {
      const isDate = t.is_date_table || t.name.toLowerCase().includes('localdatetable') || t.name.toLowerCase().includes('datetabletemplate');
      if (collapseDateTables && isDate) return false;
      if (hideDisconnected && !connectedTableNames.has(t.name.toLowerCase())) return false;
      if (searchTable.trim()) {
        return t.name.toLowerCase().includes(searchTable.toLowerCase());
      }
      return true;
    });

    const visibleTableSet = new Set(visibleTables.map((t) => t.name.toLowerCase()));

    // Neighborhood isolation if table selected
    const neighborhoodTableSet = new Set<string>();
    if (selectedTable) {
      neighborhoodTableSet.add(selectedTable.name.toLowerCase());
      relationships.forEach((rel) => {
        if (rel.from_table.toLowerCase() === selectedTable.name.toLowerCase()) {
          neighborhoodTableSet.add(rel.to_table.toLowerCase());
        }
        if (rel.to_table.toLowerCase() === selectedTable.name.toLowerCase()) {
          neighborhoodTableSet.add(rel.from_table.toLowerCase());
        }
      });
    }

    const rawNodes: Node[] = visibleTables.map((table) => {
      const isFocused = selectedTable ? neighborhoodTableSet.has(table.name.toLowerCase()) : false;
      return {
        id: table.name,
        type: 'tableNode',
        data: {
          ...table,
          isNeighborhoodFocus: isFocused,
        },
        position: { x: 0, y: 0 },
      };
    });

    const rawEdges: Edge[] = [];
    relationships.forEach((rel, idx) => {
      const fromLower = rel.from_table.toLowerCase();
      const toLower = rel.to_table.toLowerCase();

      if (!visibleTableSet.has(fromLower) || !visibleTableSet.has(toLower)) {
        return;
      }

      const isBiDir = rel.cross_filter_direction.toLowerCase().includes('both');
      const isHighlighted = selectedTable
        ? fromLower === selectedTable.name.toLowerCase() || toLower === selectedTable.name.toLowerCase()
        : true;

      rawEdges.push({
        id: `e-${rel.from_table}-${rel.to_table}-${idx}`,
        source: rel.to_table, // Dimension -> Fact filter propagation
        target: rel.from_table,
        animated: isBiDir,
        label: `${rel.from_column} ↔ ${rel.to_column}`,
        style: {
          stroke: isBiDir ? '#F59E0B' : isHighlighted ? '#3B82F6' : '#2D3449',
          strokeWidth: isBiDir ? 2.5 : isHighlighted ? 1.5 : 1,
          opacity: isHighlighted ? 1 : 0.25,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isBiDir ? '#F59E0B' : '#3B82F6',
        },
        markerStart: isBiDir
          ? {
              type: MarkerType.ArrowClosed,
              color: '#F59E0B',
            }
          : undefined,
      });
    });

    return computeDagreLayout(rawNodes, rawEdges);
  }, [tables, relationships, collapseDateTables, hideDisconnected, searchTable, selectedTable, connectedTableNames]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Sync state when layout recalculates
  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    const tableObj = tables.find((t) => t.name === node.id);
    setSelectedTable((prev) => (prev?.name === node.id ? null : tableObj || null));
  }, [tables]);

  return (
    <div className="h-full flex flex-col space-y-3">
      {/* Control Strip */}
      <div className="p-3 rounded-lg bg-studio-card border border-studio-border flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          {/* Search Box */}
          <div className="relative w-48 sm:w-60">
            <Search className="w-3.5 h-3.5 text-studio-subtle absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search table in model..."
              value={searchTable}
              onChange={(e) => setSearchTable(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-studio-bg border border-studio-border rounded-md text-xs text-studio-text placeholder-studio-subtle focus:outline-none focus:border-blue-500 font-mono transition"
            />
          </div>

          {/* Toggle Auto Date Tables */}
          <button
            onClick={() => setCollapseDateTables(!collapseDateTables)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition ${
              collapseDateTables
                ? 'bg-blue-600/20 text-blue-300 border-blue-500/40'
                : 'bg-studio-bg text-studio-subtle border-studio-border hover:text-slate-200'
            }`}
          >
            {collapseDateTables ? <CheckSquare className="w-3.5 h-3.5 text-blue-400" /> : <Square className="w-3.5 h-3.5" />}
            <span>Hide Auto Date Tables</span>
          </button>

          {/* Toggle Disconnected */}
          <button
            onClick={() => setHideDisconnected(!hideDisconnected)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition ${
              hideDisconnected
                ? 'bg-blue-600/20 text-blue-300 border-blue-500/40'
                : 'bg-studio-bg text-studio-subtle border-studio-border hover:text-slate-200'
            }`}
          >
            {hideDisconnected ? <CheckSquare className="w-3.5 h-3.5 text-blue-400" /> : <Square className="w-3.5 h-3.5" />}
            <span>Hide Disconnected</span>
          </button>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-studio-subtle font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            <span>Single Direction</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Bi-directional (Warning)</span>
          </div>
          {selectedTable && (
            <button
              onClick={() => setSelectedTable(null)}
              className="text-blue-400 hover:underline font-sans text-xs flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              <span>Clear Focus ({selectedTable.name})</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Canvas & Detail Drawer Area */}
      <div className="flex-1 flex gap-3 min-h-[500px] h-[calc(100vh-14rem)]">
        {/* ReactFlow Canvas */}
        <div className="flex-1 rounded-lg border border-studio-border bg-studio-bg overflow-hidden relative shadow-inner">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-right"
          >
            <Background color="#1F2433" gap={18} size={1} variant={BackgroundVariant.Dots} />
            <Controls className="bg-studio-card border border-studio-border text-slate-200 fill-slate-200" />
            <MiniMap
              nodeColor={() => '#2563EB'}
              className="bg-studio-sidebar border border-studio-border rounded-md overflow-hidden"
            />
          </ReactFlow>
        </div>

        {/* Table Column Details Drawer (when a table is clicked) */}
        {selectedTable && (
          <div className="w-72 bg-studio-card border border-studio-border rounded-lg p-4 flex flex-col justify-between shrink-0 overflow-hidden shadow-lg animate-in slide-in-from-right duration-150">
            <div className="space-y-3 flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between pb-2 border-b border-studio-border">
                <div className="min-w-0">
                  <h4 className="font-bold text-xs text-white font-mono truncate">{selectedTable.name}</h4>
                  <p className="text-[10px] text-studio-subtle font-mono mt-0.5">
                    {selectedTable.columns?.length || 0} Columns · {selectedTable.measures_count || 0} Measures
                  </p>
                </div>
                <button
                  onClick={() => setSelectedTable(null)}
                  className="p-1 rounded text-studio-subtle hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Column List */}
              <div className="flex-1 overflow-y-auto space-y-1 pr-1 min-h-0">
                <div className="text-[10px] font-semibold text-studio-subtle uppercase tracking-wider mb-1">
                  Columns Schema
                </div>
                {selectedTable.columns && selectedTable.columns.length > 0 ? (
                  selectedTable.columns.map((col) => (
                    <div
                      key={col.name}
                      className="p-2 rounded bg-studio-bg border border-studio-border text-xs flex items-center justify-between"
                    >
                      <div className="min-w-0">
                        <div className="font-mono text-slate-200 truncate flex items-center gap-1.5">
                          {col.in_relationship && <Key className="w-3 h-3 text-blue-400 shrink-0" />}
                          <span className="truncate">{col.name}</span>
                        </div>
                        <div className="text-[10px] font-mono text-studio-subtle truncate">
                          {col.data_type || 'string'}
                        </div>
                      </div>

                      {col.is_unique && (
                        <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                          PK
                        </span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-6 text-xs text-studio-subtle">No columns in table</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
