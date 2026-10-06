import type { HistoryPoint } from '../lib/history';
import type { ScanResult, VisualInfo } from '../types';

export const SAMPLE_BANANAS_REPORT: ScanResult = {
  report_name: "world is going bananas.pbip",
  source_path: "pbip_project/world is going bananas.pbip",
  scores: {
    overall: 97.8,
    category_scores: {
      model: 100,
      dax: 93.3,
      report: 100,
    },
  },
  findings: [
    {
      rule_id: "DAX_DUPLICATE_MEASURE",
      category: "dax",
      severity: "MEDIUM",
      title: "Duplicate measure logic detected",
      issue: "Banana Exports[Primary Value (M)] and Banana Exports[Total Value] contain identical normalized DAX expressions.",
      evidence: "SUM('Banana Exports'[primaryValue])",
      impact: "Redundant measures create maintenance confusion and multiple cache footprints for identical calculations.",
      recommendation: "Consolidate duplicate logic into a single authoritative base measure and reference it downstream.",
      confidence: 90,
      location: "Banana Exports[Primary Value (M)], Banana Exports[Total Value]",
    },
    {
      rule_id: "DAX_UNUSED_MEASURE",
      category: "dax",
      severity: "ADVISORY",
      title: "Potentially unused measure",
      issue: "Measure 'Total Value (Display)' is defined in the model but never referenced in report visuals or other measures.",
      evidence: "Measure 'Total Value (Display)' in Banana Exports: 0 downstream references found across report visuals and measures.",
      impact: "Unreferenced measures bloat the semantic model field list and add cognitive load for report authors.",
      recommendation: "Verify if this measure is needed for ad-hoc Excel analyze-in-Excel queries; if not, remove or hide it.",
      confidence: 95,
      location: "Banana Exports[Total Value (Display)]",
    },
    {
      rule_id: "DAX_UNUSED_MEASURE",
      category: "dax",
      severity: "ADVISORY",
      title: "Potentially unused measure",
      issue: "Measure 'Avg Starch Label' is defined in the model but never referenced in report visuals or other measures.",
      evidence: "Measure 'Avg Starch Label' in Ripening Changes: 0 downstream references found across report visuals and measures.",
      impact: "Unreferenced measures bloat the semantic model field list.",
      recommendation: "Remove or mark as hidden if strictly reserved for backend calculations.",
      confidence: 95,
      location: "Ripening Changes[Avg Starch Label]",
    },
  ],
  tables: [
    {
      name: "Banana Exports",
      hidden: false,
      is_date_table: false,
      column_count: 8,
      measures_count: 3,
      calc_cols_count: 0,
      columns: [
        { name: "ExportID", data_type: "int64", is_unique: true, in_relationship: true, hidden: false },
        { name: "Country", data_type: "string", is_unique: false, in_relationship: true, hidden: false },
        { name: "Year", data_type: "int64", is_unique: false, in_relationship: false, hidden: false },
        { name: "primaryValue", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
        { name: "VolumeMT", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "Ripening Changes",
      hidden: false,
      is_date_table: false,
      column_count: 6,
      measures_count: 2,
      calc_cols_count: 0,
      columns: [
        { name: "StageID", data_type: "int64", is_unique: true, in_relationship: false, hidden: false },
        { name: "StageName", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
        { name: "StarchIndex", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
        { name: "SugarPct", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "Countries",
      hidden: false,
      is_date_table: false,
      column_count: 4,
      measures_count: 1,
      calc_cols_count: 0,
      columns: [
        { name: "Country", data_type: "string", is_unique: true, in_relationship: true, hidden: false },
        { name: "Region", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
        { name: "Continent", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "Global Metrics",
      hidden: false,
      is_date_table: false,
      column_count: 3,
      measures_count: 0,
      calc_cols_count: 0,
      columns: [
        { name: "MetricKey", data_type: "string", is_unique: true, in_relationship: false, hidden: false },
        { name: "Value", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
  ],
  relationships: [
    {
      from_table: "Banana Exports",
      from_column: "Country",
      to_table: "Countries",
      to_column: "Country",
      cardinality: "manyToOne",
      cross_filter_direction: "single",
      is_active: true,
    },
  ],
  measures: [
    {
      name: "Primary Value (M)",
      table: "Banana Exports",
      expression: "SUM('Banana Exports'[primaryValue])",
      hidden: false,
    },
    {
      name: "Total Value",
      table: "Banana Exports",
      expression: "SUM('Banana Exports'[primaryValue])",
      hidden: false,
    },
    {
      name: "Total Value (Display)",
      table: "Banana Exports",
      expression: "FORMAT([Primary Value (M)], \"$#,##0.00 M\")",
      hidden: false,
    },
    {
      name: "Avg Starch Label",
      table: "Ripening Changes",
      expression: "\"Average Starch: \" & FORMAT(AVERAGE('Ripening Changes'[StarchIndex]), \"0.0%\")",
      hidden: false,
    },
    {
      name: "Avg Sugar Content",
      table: "Ripening Changes",
      expression: "AVERAGE('Ripening Changes'[SugarPct])",
      hidden: false,
    },
    {
      name: "Country Count",
      table: "Countries",
      expression: "DISTINCTCOUNT(Countries[Country])",
      hidden: false,
    },
  ],
  calculated_columns: [],
  pages: [
    { name: "ReportSection1", display_name: "Global Banana Overview", is_hidden: false, visual_count: 7, slicer_count: 2 },
    { name: "ReportSection2", display_name: "Export Price Trends", is_hidden: false, visual_count: 6, slicer_count: 2 },
    { name: "ReportSection3", display_name: "Ripening & Starch Chemistry", is_hidden: false, visual_count: 5, slicer_count: 1 },
    { name: "ReportSection4", display_name: "Regional Trade Flow", is_hidden: false, visual_count: 4, slicer_count: 1 },
    { name: "ReportSection5", display_name: "Data Definitions & Notes", is_hidden: true, visual_count: 2, slicer_count: 0 },
  ],
  warnings: [],
  summary: {
    total_findings: 3,
    table_count: 15,
    relationship_count: 9,
    measure_count: 6,
    page_count: 5,
  },
};

export const SAMPLE_ENTERPRISE_REPORT: ScanResult = {
  report_name: "Enterprise Sales & Margin Analytics.pbip",
  source_path: "pbip_project/Enterprise Sales.pbip",
  scores: {
    overall: 82.4,
    category_scores: {
      model: 80.0,
      dax: 82.5,
      report: 85.0,
    },
  },
  findings: [
    {
      rule_id: "MODEL_BIDIRECTIONAL",
      category: "model",
      severity: "WARNING",
      title: "Bidirectional relationship detected",
      issue: "Relationship between FactSales[CustomerID] and DimCustomer[CustomerID] is set to BothDirections.",
      evidence: "FactSales[CustomerID] <-> DimCustomer[CustomerID] (BothDirections)",
      impact: "Bidirectional relationships propagate filters ambiguity and can cause severe DAX context transition slowdowns.",
      recommendation: "Change cross-filtering behavior to Single direction (DimCustomer -> FactSales) or use CROSSFILTER() in DAX.",
      confidence: 100,
      location: "FactSales[CustomerID] <-> DimCustomer[CustomerID]",
    },
    {
      rule_id: "DAX_SUSPICIOUS_PATTERN",
      category: "dax",
      severity: "ADVISORY",
      title: "Suspicious FILTER(ALL(...)) scan pattern",
      issue: "Measure 'Expensive Sales Filter' uses FILTER(ALL(FactSales)) table scan.",
      evidence: "CALCULATE(SUM(FactSales[Amount]), FILTER(ALL(FactSales), FactSales[Amount] > 1000))",
      impact: "FILTER(ALL(Table)) triggers full table materialization in the Formula Engine, bypassing Storage Engine optimizations.",
      recommendation: "Replace with KEEPFILTERS() or column-level filter: CALCULATE(SUM(FactSales[Amount]), KEEPFILTERS(FactSales[Amount] > 1000)).",
      confidence: 65,
      location: "FactSales[Expensive Sales Filter]",
    },
    {
      rule_id: "DAX_EXCESSIVE_CALC_COLUMNS",
      category: "dax",
      severity: "MEDIUM",
      title: "Excessive calculated columns on table",
      issue: "FactSales contains 6 calculated columns, exceeding the optimal threshold of 4.",
      evidence: "FactSales has 6 calculated columns: NetPrice, MarginPct, TaxAmt, PromoDiscount, RegionKey, TierCode.",
      impact: "Calculated columns are computed during data refresh and consume uncompressed VertiPaq RAM memory.",
      recommendation: "Push row-level calculation transformations upstream to Power Query (M) or SQL warehouse ETL.",
      confidence: 100,
      location: "Table: FactSales",
    },
    {
      rule_id: "REPORT_VISUAL_BLOAT",
      category: "report",
      severity: "MEDIUM",
      title: "Visual bloat detected on page",
      issue: "Page 'Executive Summary' contains 18 visuals, exceeding the recommended limit of 15.",
      evidence: "Page 'Executive Summary' (ReportSection1) contains 18 visuals.",
      impact: "Every visual generates concurrent DAX queries. More than 15 visuals causes visual rendering latency and queue spikes.",
      recommendation: "Split the page into focused drill-through tabs, or use modern multi-row KPI card visuals.",
      confidence: 100,
      location: "Page: Executive Summary",
    },
    {
      rule_id: "DAX_UNUSED_MEASURE",
      category: "dax",
      severity: "ADVISORY",
      title: "Potentially unused measure",
      issue: "Measure 'Legacy Discount Rate' is never referenced across visuals or downstream formulas.",
      evidence: "Measure 'Legacy Discount Rate' in DimProduct: 0 downstream references found.",
      impact: "Clutters the semantic model field list.",
      recommendation: "Review and delete if decommissioned.",
      confidence: 95,
      location: "DimProduct[Legacy Discount Rate]",
    },
  ],
  tables: [
    {
      name: "FactSales",
      hidden: false,
      is_date_table: false,
      column_count: 16,
      measures_count: 12,
      calc_cols_count: 6,
      columns: [
        { name: "SalesID", data_type: "int64", is_unique: true, in_relationship: false, hidden: false },
        { name: "DateKey", data_type: "int64", is_unique: false, in_relationship: true, hidden: false },
        { name: "CustomerID", data_type: "int64", is_unique: false, in_relationship: true, hidden: false },
        { name: "ProductID", data_type: "int64", is_unique: false, in_relationship: true, hidden: false },
        { name: "Amount", data_type: "double", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "DimCustomer",
      hidden: false,
      is_date_table: false,
      column_count: 10,
      measures_count: 2,
      calc_cols_count: 0,
      columns: [
        { name: "CustomerID", data_type: "int64", is_unique: true, in_relationship: true, hidden: false },
        { name: "CustomerName", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
        { name: "Segment", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "DimProduct",
      hidden: false,
      is_date_table: false,
      column_count: 8,
      measures_count: 4,
      calc_cols_count: 0,
      columns: [
        { name: "ProductID", data_type: "int64", is_unique: true, in_relationship: true, hidden: false },
        { name: "ProductName", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
        { name: "Category", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
    {
      name: "DimDate",
      hidden: false,
      is_date_table: true,
      column_count: 12,
      measures_count: 3,
      calc_cols_count: 0,
      columns: [
        { name: "DateKey", data_type: "int64", is_unique: true, in_relationship: true, hidden: false },
        { name: "Date", data_type: "dateTime", is_unique: true, in_relationship: false, hidden: false },
        { name: "Year", data_type: "int64", is_unique: false, in_relationship: false, hidden: false },
        { name: "Quarter", data_type: "string", is_unique: false, in_relationship: false, hidden: false },
      ],
    },
  ],
  relationships: [
    {
      from_table: "FactSales",
      from_column: "CustomerID",
      to_table: "DimCustomer",
      to_column: "CustomerID",
      cardinality: "manyToOne",
      cross_filter_direction: "both",
      is_active: true,
    },
    {
      from_table: "FactSales",
      from_column: "ProductID",
      to_table: "DimProduct",
      to_column: "ProductID",
      cardinality: "manyToOne",
      cross_filter_direction: "single",
      is_active: true,
    },
    {
      from_table: "FactSales",
      from_column: "DateKey",
      to_table: "DimDate",
      to_column: "DateKey",
      cardinality: "manyToOne",
      cross_filter_direction: "single",
      is_active: true,
    },
  ],
  measures: [
    {
      name: "Total Sales",
      table: "FactSales",
      expression: "SUM(FactSales[Amount])",
      hidden: false,
    },
    {
      name: "Sales YTD",
      table: "FactSales",
      expression: "TOTALYTD([Total Sales], DimDate[Date])",
      hidden: false,
    },
    {
      name: "Sales SPLY",
      table: "FactSales",
      expression: "CALCULATE([Total Sales], SAMEPERIODLASTYEAR(DimDate[Date]))",
      hidden: false,
    },
    {
      name: "Expensive Sales Filter",
      table: "FactSales",
      expression: "CALCULATE(SUM(FactSales[Amount]), FILTER(ALL(FactSales), FactSales[Amount] > 1000))",
      hidden: false,
    },
    {
      name: "Legacy Discount Rate",
      table: "DimProduct",
      expression: "AVERAGE(DimProduct[BaseDiscount])",
      hidden: false,
    },
  ],
  calculated_columns: [
    { name: "NetPrice", table: "FactSales", expression: "FactSales[Amount] * 0.9", data_type: "double" },
    { name: "MarginPct", table: "FactSales", expression: "DIVIDE(FactSales[Margin], FactSales[Amount])", data_type: "double" },
    { name: "TaxAmt", table: "FactSales", expression: "FactSales[Amount] * 0.08", data_type: "double" },
    { name: "PromoDiscount", table: "FactSales", expression: "IF(FactSales[Amount] > 500, 50, 0)", data_type: "double" },
    { name: "RegionKey", table: "FactSales", expression: "RELATED(DimCustomer[RegionKey])", data_type: "int64" },
    { name: "TierCode", table: "FactSales", expression: "IF(FactSales[Amount] > 1000, \"GOLD\", \"SILVER\")", data_type: "string" },
  ],
  pages: [
    { name: "ReportSection1", display_name: "Executive Summary", is_hidden: false, visual_count: 18, slicer_count: 4 },
    { name: "ReportSection2", display_name: "Customer Lifetime Value", is_hidden: false, visual_count: 8, slicer_count: 3 },
    { name: "ReportSection3", display_name: "Product Profitability", is_hidden: false, visual_count: 10, slicer_count: 2 },
  ],
  warnings: [],
  summary: {
    total_findings: 5,
    table_count: 12,
    relationship_count: 14,
    measure_count: 24,
    page_count: 3,
  },
};

// ---------------------------------------------------------------------------
// Sample visual layouts and score history (made up, for the demo projects only)
// ---------------------------------------------------------------------------

const CHART_TYPES = ['card', 'clusteredColumnChart', 'lineChart', 'tableEx', 'donutChart', 'matrix', 'barChart', 'areaChart'];

/** Lay each sample page out like a typical report: slicers on top, KPI cards, then a chart grid. */
function addSampleLayout(report: ScanResult): void {
  const unused = new Set(
    report.findings.filter((f) => f.rule_id === 'DAX_UNUSED_MEASURE').map((f) => (/\[([^\]]+)\]/.exec(f.location || '')?.[1] ?? '').toLowerCase()),
  );
  const measures = report.measures.filter((m) => !unused.has(m.name.toLowerCase()));
  const factNames = new Set(report.measures.map((m) => m.table));
  const dims = report.tables.map((t) => t.name).filter((n) => !factNames.has(n));
  const pick = <T,>(list: T[], i: number): T | undefined => (list.length ? list[i % list.length] : undefined);

  report.pages.forEach((page, p) => {
    const W = 1280, H = 720, gap = 12, pad = 16;
    const visuals: VisualInfo[] = [];
    const slicers = page.slicer_count;
    const rest = page.visual_count - slicers;
    for (let i = 0; i < slicers; i++) {
      const dim = pick(dims, i + p) ?? '';
      visuals.push({ visual_type: 'slicer', x: pad + i * 196, y: pad, width: 184, height: 56, measure_refs: [], fields_used: [], table_refs: dim ? [dim] : [], is_slicer: true, hidden: false });
    }
    const top = slicers ? pad + 56 + gap : pad;
    const cards = Math.min(4, Math.max(0, rest - 2));
    const cw = (W - pad * 2 - gap * (cards - 1)) / Math.max(1, cards);
    for (let i = 0; i < cards; i++) {
      const m = pick(measures, i + p);
      visuals.push({ visual_type: 'card', x: pad + i * (cw + gap), y: top, width: cw, height: 96, measure_refs: m ? [m.name] : [], fields_used: m ? [m.name] : [], table_refs: m ? [m.table] : [], is_slicer: false, hidden: false });
    }
    const charts = rest - cards;
    const cols = charts > 6 ? 4 : 3;
    const rows = Math.max(1, Math.ceil(charts / cols));
    const gridTop = top + (cards ? 96 + gap : 0);
    const chH = (H - gridTop - pad - gap * (rows - 1)) / rows;
    const chW = (W - pad * 2 - gap * (cols - 1)) / cols;
    for (let i = 0; i < charts; i++) {
      const m = pick(measures, i + 2 + p);
      const dim = pick(dims, i + p);
      const tables = [...new Set([m?.table, dim].filter(Boolean) as string[])];
      visuals.push({
        visual_type: CHART_TYPES[(i + p) % CHART_TYPES.length].replace(/^card$/, 'clusteredColumnChart'),
        x: pad + (i % cols) * (chW + gap), y: gridTop + Math.floor(i / cols) * (chH + gap), width: chW, height: chH,
        measure_refs: m ? [m.name] : [], fields_used: m ? [m.name] : [], table_refs: tables, is_slicer: false, hidden: false,
      });
    }
    page.width = W;
    page.height = H;
    page.visuals = visuals;
  });
}

addSampleLayout(SAMPLE_BANANAS_REPORT);
addSampleLayout(SAMPLE_ENTERPRISE_REPORT);

/** A made-up trend that ends at the sample's current score. */
export function sampleHistory(report: ScanResult): HistoryPoint[] {
  const end = report.scores.overall;
  const steps = [-11.2, -9.4, -7.6, -8.3, -4.9, -3.1, -3.1, 0];
  const day = 24 * 3600 * 1000;
  const now = Date.now();
  return steps.map((d, i) => ({
    t: new Date(now - (steps.length - 1 - i) * 16 * day).toISOString(),
    overall: Math.max(0, Math.min(100, +(end + d).toFixed(1))),
    findings: report.findings.length + Math.max(0, Math.round(-d / 2)),
  }));
}
