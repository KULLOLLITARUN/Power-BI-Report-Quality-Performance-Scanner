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
  Key,
  X
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
      className="w-[240px] rounded border text-left transition-all duration-150 shadow-sm"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: selected 
          ? 'var(--accent)' 
          : isFocused 
          ? 'var(--border-strong)' 
          : 'var(--border-hairline)',
        borderWidth: selected ? '2px' : '1px',
      }}
    >
      {/* ReactFlow Connection Handles */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-2.5 h-2.5 rounded-full"
        style={{
          backgroundColor: 'var(--accent)',
          borderColor: 'var(--bg-canvas)',
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-2.5 h-2.5 rounded-full"
        style={{
          backgroundColor: 'var(--accent)',
          borderColor: 'var(--bg-canvas)',
        }}
      />

      {/* Node Header */}
      <div 
        className="p-2.5 border-b flex items-center justify-between font-mono"
        style={{
          backgroundColor: isDate ? 'var(--accent-muted)' : 'var(--bg-canvas)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Database 
            className="w-3.5 h-3.5 shrink-0" 
            style={{ color: isDate ? 'var(--accent)' : 'var(--text-secondary)' }} 
          />
          <span 
            className="font-bold text-xs truncate" 
            style={{ color: 'var(--text-primary)' }}
            title={data.name}
          >
            {data.name}
          </span>
        </div>

        {isHidden && (
          <span 
            className="text-[9px] font-mono px-1 py-0.2 rounded border"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-muted)',
            }}
          >
            hidden
          </span>
        )}
      </div>

      {/* Node Summary Stats */}
      <div className="p-2.5 text-[11px] font-mono space-y-1" style={{ color: 'var(--text-secondary)' }}>
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--text-muted)' }}>Columns</span>
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{data.column_count || 0}</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--text-muted)' }}>Measures</span>
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{data.measures_count || 0}</span>
        </div>
        {data.calc_cols_count > 0 && (
          <div className="flex items-center justify-between">
            <span style={{ color: 'var(--text-muted)' }}>Calc Columns</span>
            <span className="font-semibold" style={{ color: 'var(--accent)' }}>{data.calc_cols_count}</span>
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

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 250, height: 110 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: Position.Top,
      sourcePosition: Position.Bottom,
      position: {
        x: nodeWithPosition.x - 125,
        y: nodeWithPosition.y - 55,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

export const ModelMap: React.FC<ModelMapProps> = ({ tables, relationships }) => {
  const [hideDateTables, setHideDateTables] = useState(true);
  const [hideHiddenTables, setHideHiddenTables] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null);

  // Filter visible tables
  const visibleTables = useMemo(() => {
    return tables.filter((t) => {
      const isDate =
        t.is_date_table ||
        t.name.toLowerCase().includes('localdatetable') ||
        t.name.toLowerCase().includes('datetabletemplate');

      if (hideDateTables && isDate) return false;
      if (hideHiddenTables && t.hidden) return false;
      if (searchFilter.trim()) {
        const matchesName = t.name.toLowerCase().includes(searchFilter.toLowerCase());
        const matchesCol = t.columns?.some((c) =>
          c.name.toLowerCase().includes(searchFilter.toLowerCase())
        );
        return matchesName || matchesCol;
      }
      return true;
    });
  }, [tables, hideDateTables, hideHiddenTables, searchFilter]);

  const visibleTableNames = useMemo(
    () => new Set(visibleTables.map((t) => t.name)),
    [visibleTables]
  );

  // Build raw nodes
  const initialNodes: Node[] = useMemo(() => {
    return visibleTables.map((t) => ({
      id: t.name,
      type: 'tableNode',
      data: {
        ...t,
        column_count: t.columns?.length || 0,
        calc_cols_count: t.calculated_columns_count || 0,
      },
      position: { x: 0, y: 0 },
    }));
  }, [visibleTables]);

  // Build raw edges
  const initialEdges: Edge[] = useMemo(() => {
    return relationships
      .filter((r) => visibleTableNames.has(r.from_table) && visibleTableNames.has(r.to_table))
      .map((r, idx) => {
        const isBidi = r.cross_filtering_behavior === 'BothDirections';
        return {
          id: `e-${r.from_table}-${r.to_table}-${idx}`,
          source: r.to_table,
          target: r.from_table,
          type: 'smoothstep',
          animated: isBidi,
          style: {
            stroke: isBidi ? 'var(--severity-warning)' : 'var(--border-strong)',
            strokeWidth: isBidi ? 2 : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: isBidi ? 'var(--severity-warning)' : 'var(--border-strong)',
          },
        };
      });
  }, [relationships, visibleTableNames]);

  // Apply Dagre auto-layout
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => {
    return computeDagreLayout(initialNodes, initialEdges, 'TB');
  }, [initialNodes, initialEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      const matched = tables.find((t) => t.name === node.id);
      if (matched) {
        setSelectedTable(matched);
      }
    },
    [tables]
  );

  return (
    <div className="flex flex-col gap-3 h-[calc(100vh-8.5rem)]">
      {/* Top Filter Bar */}
      <div 
        className="p-3 border rounded flex flex-wrap items-center justify-between gap-3 text-xs font-mono"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Filter tables or columns..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded text-xs font-mono focus:outline-none transition border"
              style={{
                backgroundColor: 'var(--bg-canvas)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
              }}
            />
          </div>
        </div>

        {/* Toggles */}
        <div className="flex items-center gap-4" style={{ color: 'var(--text-secondary)' }}>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={hideDateTables}
              onChange={(e) => setHideDateTables(e.target.checked)}
              className="rounded"
            />
            <span>Hide Auto-Date Tables</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={hideHiddenTables}
              onChange={(e) => setHideHiddenTables(e.target.checked)}
              className="rounded"
            />
            <span>Hide System Tables</span>
          </label>

          <span style={{ color: 'var(--text-muted)' }}>
            Showing {visibleTables.length} / {tables.length} tables
          </span>
        </div>
      </div>

      {/* Main Canvas & Detail Drawer */}
      <div className="flex-1 flex gap-3 min-h-0">
        {/* ReactFlow Canvas */}
        <div 
          className="flex-1 border rounded overflow-hidden relative"
          style={{
            backgroundColor: 'var(--bg-canvas)',
            borderColor: 'var(--border-hairline)',
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            attributionPosition="bottom-right"
          >
            <Background gap={18} size={1} variant={BackgroundVariant.Dots} />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>

        {/* Table Column Details Drawer */}
        {selectedTable && (
          <div 
            className="w-72 border rounded p-4 flex flex-col justify-between shrink-0 overflow-hidden shadow-lg animate-in slide-in-from-right duration-150"
            style={{
              backgroundColor: 'var(--bg-surface)',
              borderColor: 'var(--border-hairline)',
            }}
          >
            <div className="space-y-3 flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border-hairline)' }}>
                <div className="min-w-0">
                  <h4 className="font-bold text-xs font-mono truncate" style={{ color: 'var(--text-primary)' }}>
                    {selectedTable.name}
                  </h4>
                  <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    {selectedTable.columns?.length || 0} Columns · {selectedTable.measures_count || 0} Measures
                  </p>
                </div>
                <button
                  onClick={() => setSelectedTable(null)}
                  className="p-1 rounded transition"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Column List */}
              <div className="flex-1 overflow-y-auto space-y-1 pr-1 min-h-0">
                <div className="text-[10px] font-mono font-medium uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                  Columns Schema
                </div>
                {selectedTable.columns && selectedTable.columns.length > 0 ? (
                  selectedTable.columns.map((col) => (
                    <div
                      key={col.name}
                      className="p-2 rounded border text-xs flex items-center justify-between font-mono"
                      style={{
                        backgroundColor: 'var(--bg-canvas)',
                        borderColor: 'var(--border-hairline)',
                      }}
                    >
                      <div className="min-w-0">
                        <div className="truncate flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                          {col.in_relationship && <Key className="w-3 h-3 shrink-0" style={{ color: 'var(--accent)' }} />}
                          <span className="truncate">{col.name}</span>
                        </div>
                        <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>
                          {col.data_type || 'string'}
                        </div>
                      </div>

                      {col.is_unique && (
                        <span 
                          className="text-[9px] font-mono px-1 py-0.2 rounded border shrink-0 font-bold"
                          style={{
                            backgroundColor: 'var(--accent-muted)',
                            borderColor: 'var(--accent)',
                            color: 'var(--accent)',
                          }}
                        >
                          PK
                        </span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-6 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    No columns in table
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
