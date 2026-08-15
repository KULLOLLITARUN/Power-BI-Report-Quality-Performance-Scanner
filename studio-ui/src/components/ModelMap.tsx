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
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { TableInfo, RelationshipInfo } from '../types';
import { 
  Database, 
  Layers, 
  Code2, 
  Search, 
  Eye, 
  EyeOff, 
  CheckSquare, 
  Square,
  AlertTriangle,
  ZoomIn,
  RefreshCw
} from 'lucide-react';

interface ModelMapProps {
  tables: TableInfo[];
  relationships: RelationshipInfo[];
}

// Custom Node Component for Power BI Tables
const TableNode: React.FC<{ data: any; selected: boolean }> = ({ data, selected }) => {
  const isDate = data.is_date_table;
  const isHidden = data.hidden;
  const isFocused = data.isNeighborhoodFocus;

  return (
    <div
      className={`w-[250px] rounded-xl border transition-all duration-200 shadow-lg ${
        selected
          ? 'ring-2 ring-emerald-500 border-emerald-400 bg-obsidian-800'
          : isFocused
          ? 'ring-1 ring-blue-500 border-blue-400 bg-obsidian-800'
          : 'border-obsidian-700 bg-obsidian-900/95 hover:border-obsidian-600'
      }`}
    >
      {/* Node Header */}
      <div className={`p-3 border-b flex items-center justify-between rounded-t-xl ${
        isDate 
          ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' 
          : 'bg-obsidian-800 border-obsidian-700 text-slate-100'
      }`}>
        <div className="flex items-center gap-2 min-w-0">
          <Database className={`w-3.5 h-3.5 shrink-0 ${isDate ? 'text-amber-400' : 'text-blue-400'}`} />
          <span className="font-semibold text-xs truncate font-mono" title={data.name}>
            {data.name}
          </span>
        </div>

        {isHidden && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            hidden
          </span>
        )}
      </div>

      {/* Node Meta Stats */}
      <div className="p-3 text-[11px] space-y-1.5 font-mono text-slate-400">
        <div className="flex items-center justify-between">
          <span>Columns</span>
          <span className="text-slate-200 font-semibold">{data.column_count}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Measures</span>
          <span className="text-emerald-400 font-semibold">{data.measures_count}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Calculated Cols</span>
          <span className="text-purple-400 font-semibold">{data.calc_cols_count}</span>
        </div>
      </div>
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

// Dagre Layout Engine Helper
const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = 'TB'
) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 60,
    ranksep: 80,
  });

  const nodeWidth = 250;
  const nodeHeight = 130;

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
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
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

export const ModelMap: React.FC<ModelMapProps> = ({ tables, relationships }) => {
  const [collapseDateTables, setCollapseDateTables] = useState(true);
  const [hideDisconnected, setHideDisconnected] = useState(false);
  const [searchTable, setSearchTable] = useState('');
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);

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
  const { initialNodes, initialEdges } = useMemo(() => {
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
    if (selectedTableId) {
      neighborhoodTableSet.add(selectedTableId.toLowerCase());
      relationships.forEach((rel) => {
        if (rel.from_table.toLowerCase() === selectedTableId.toLowerCase()) {
          neighborhoodTableSet.add(rel.to_table.toLowerCase());
        }
        if (rel.to_table.toLowerCase() === selectedTableId.toLowerCase()) {
          neighborhoodTableSet.add(rel.from_table.toLowerCase());
        }
      });
    }

    const nodes: Node[] = visibleTables.map((table) => {
      const isFocused = selectedTableId ? neighborhoodTableSet.has(table.name.toLowerCase()) : false;
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

    const edges: Edge[] = [];
    relationships.forEach((rel, idx) => {
      const fromLower = rel.from_table.toLowerCase();
      const toLower = rel.to_table.toLowerCase();

      if (!visibleTableSet.has(fromLower) || !visibleTableSet.has(toLower)) {
        return;
      }

      const isBiDir = rel.cross_filter_direction.toLowerCase().includes('both');
      const isM2M = rel.cardinality.toLowerCase().includes('manys') || rel.cardinality.toLowerCase().includes('manytomany');

      const isEdgeHighlighted = selectedTableId
        ? fromLower === selectedTableId.toLowerCase() || toLower === selectedTableId.toLowerCase()
        : true;

      edges.push({
        id: `e-${rel.from_table}-${rel.to_table}-${idx}`,
        source: rel.to_table, // Filter propagation direction: Dimension -> Fact
        target: rel.from_table,
        animated: isBiDir,
        label: `${rel.from_column} ↔ ${rel.to_column}`,
        style: {
          stroke: isBiDir ? '#F59E0B' : isEdgeHighlighted ? '#3B82F6' : '#374151',
          strokeWidth: isBiDir || isM2M ? 2.5 : 1.5,
          opacity: isEdgeHighlighted ? 1 : 0.2,
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

    return getLayoutedElements(nodes, edges);
  }, [tables, relationships, collapseDateTables, hideDisconnected, searchTable, selectedTableId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync layout when props or filters change
  useEffect(() => {
    const layouted = getLayoutedElements(initialNodes, initialEdges);
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedTableId((prev) => (prev === node.id ? null : node.id));
  }, []);

  return (
    <div className="h-full flex flex-col space-y-3">
      {/* Map Control Strip */}
      <div className="p-3 rounded-xl bg-obsidian-800/80 border border-obsidian-700 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          {/* Table Search */}
          <div className="relative w-48 sm:w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search table in map..."
              value={searchTable}
              onChange={(e) => setSearchTable(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-obsidian-950 border border-obsidian-700 rounded-md text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition font-mono"
            />
          </div>

          {/* Toggle Date Tables */}
          <button
            onClick={() => setCollapseDateTables(!collapseDateTables)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition ${
              collapseDateTables
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-obsidian-900 text-slate-400 border-obsidian-700 hover:text-white'
            }`}
            title="Collapse hidden auto-generated date tables"
          >
            {collapseDateTables ? <CheckSquare className="w-3.5 h-3.5 text-emerald-400" /> : <Square className="w-3.5 h-3.5" />}
            <span>Hide Auto Date Tables</span>
          </button>

          {/* Toggle Disconnected Tables */}
          <button
            onClick={() => setHideDisconnected(!hideDisconnected)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition ${
              hideDisconnected
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-obsidian-900 text-slate-400 border-obsidian-700 hover:text-white'
            }`}
          >
            {hideDisconnected ? <CheckSquare className="w-3.5 h-3.5 text-emerald-400" /> : <Square className="w-3.5 h-3.5" />}
            <span>Hide Disconnected</span>
          </button>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
            <span>Single Direction</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span>Bi-directional (Warning)</span>
          </div>
          {selectedTableId && (
            <button
              onClick={() => setSelectedTableId(null)}
              className="text-emerald-400 hover:underline font-sans text-xs"
            >
              Clear Focus ({selectedTableId})
            </button>
          )}
        </div>
      </div>

      {/* ReactFlow Canvas */}
      <div className="flex-1 w-full rounded-xl border border-obsidian-700/80 bg-obsidian-950 overflow-hidden relative shadow-inner min-h-[500px]">
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
          <Background color="#1F2937" gap={16} size={1} variant={BackgroundVariant.Dots} />
          <Controls className="bg-obsidian-800 border-obsidian-700 text-slate-100 fill-slate-100" />
          <MiniMap
            nodeColor={() => '#3B82F6'}
            className="bg-obsidian-900 border border-obsidian-700 rounded-lg overflow-hidden"
          />
        </ReactFlow>
      </div>
    </div>
  );
};
