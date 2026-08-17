export interface ColumnInfo {
  name: string;
  data_type: string;
  is_unique: boolean;
  in_relationship: boolean;
  hidden: boolean;
}

export interface TableInfo {
  name: string;
  hidden: boolean;
  is_date_table: boolean;
  column_count: number;
  columns: ColumnInfo[];
  measures_count: number;
  calc_cols_count: number;
}

export interface RelationshipInfo {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  cardinality: string; // "manyToOne", "oneToMany", "oneToOne", "manyToMany"
  cross_filter_direction: string; // "single", "both", "oneDirection", "bothDirections"
  is_active: boolean;
}

export interface MeasureInfo {
  name: string;
  table: string;
  expression: string;
  hidden: boolean;
}

export interface CalculatedColumnInfo {
  name: string;
  table: string;
  expression: string;
  data_type: string;
}

export interface PageInfo {
  name: string;
  display_name: string;
  is_hidden: boolean;
  visual_count: number;
  slicer_count: number;
}

export interface AuditFinding {
  rule_id: string;
  category: 'model' | 'dax' | 'report' | 'security';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'WARNING' | 'ADVISORY' | 'LOW';
  title: string;
  issue: string;
  evidence: string;
  impact: string;
  recommendation: string;
  confidence: number;
  location?: string;
}

export interface ScoreData {
  overall: number;
  category_scores: {
    model: number;
    dax: number;
    report: number;
    security?: number;
  };
}

export interface ScanResult {
  report_name: string;
  source_path: string;
  scores: ScoreData;
  findings: AuditFinding[];
  tables: TableInfo[];
  relationships: RelationshipInfo[];
  measures: MeasureInfo[];
  calculated_columns: CalculatedColumnInfo[];
  pages: PageInfo[];
  warnings: string[];
  summary: {
    total_findings: number;
    table_count: number;
    relationship_count: number;
    measure_count: number;
    page_count: number;
  };
}

export interface BrowseResult {
  current_path: string;
  parent_path: string | null;
  directories: { name: string; path: string }[];
  pbip_projects: { name: string; path: string }[];
}

export interface FindingTransition {
  state: 'NEW' | 'RESOLVED' | 'PERSISTENT' | 'MODIFIED';
  finding_id: string;
  rule_id: string;
  category: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'WARNING' | 'ADVISORY' | 'LOW';
  baseline_severity?: string | null;
  title: string;
  location?: string | null;
  evidence: string;
}

export interface ScoreDrift {
  baseline_score: number;
  current_score: number;
  overall_delta: number;
  direction: 'IMPROVED' | 'DEGRADED' | 'UNCHANGED';
  category_deltas: Record<string, number>;
  baseline_categories: Record<string, number>;
  current_categories: Record<string, number>;
}

export interface QualityGateVerdict {
  passed: boolean;
  reasons: string[];
}

export interface QualityGatePolicy {
  fail_on_regression?: boolean;
  max_score_drop?: number | null;
  fail_on_new?: string | null;
  fail_on_category_regression?: string | null;
}

export interface DiffCounts {
  baseline_total: number;
  current_total: number;
  new: number;
  resolved: number;
  persistent: number;
  modified: number;
}

export interface DiffResult {
  baseline_name: string;
  current_name: string;
  score_drift: ScoreDrift;
  transitions: FindingTransition[];
  counts: DiffCounts;
  quality_gate: QualityGateVerdict;
  policy: QualityGatePolicy;
}

