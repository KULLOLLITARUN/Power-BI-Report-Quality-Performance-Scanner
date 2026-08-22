import { ScanResult, AuditFinding, TableInfo, RelationshipInfo, MeasureInfo, CalculatedColumnInfo, PageInfo, ScoreData } from '../types';
import {
  SemanticReferenceIndex,
  CalcItem,
  extractCalcGroupReferences,
  extractFieldParamReferences,
  extractRlsTmdlReferences,
  extractRlsBimReferences,
  extractMeasureNamesFromExprTree,
} from './semanticReferences';
import { buildDaxGraph } from './daxGraph';

export interface DroppedFile {
  name: string;
  path: string;
  content: string;
}

interface CalcGroupEntry {
  table: string;
  items: CalcItem[];
}

export function parseDroppedPbip(files: DroppedFile[], projectName: string = "uploaded_report.pbip"): ScanResult {
  const tables: TableInfo[] = [];
  const relationships: RelationshipInfo[] = [];
  const measures: MeasureInfo[] = [];
  const calcCols: CalculatedColumnInfo[] = [];
  const pages: PageInfo[] = [];
  const mSources: { table: string; source: string }[] = [];
  const calcGroupEntries: CalcGroupEntry[] = [];
  const roleReferences: ReturnType<typeof extractRlsTmdlReferences> = [];

  // Filter out backup folders, git, and metadata
  const validFiles = files.filter(f => {
    const p = f.path.toLowerCase().replace(/\\/g, '/');
    return !p.includes('/backup/') && !p.startsWith('backup/') && !p.includes('/.git/') && !p.includes('/.pbi/');
  });

  // Check for model.bim or database.json
  const bimFile = validFiles.find(f => f.name.toLowerCase() === 'model.bim' || f.name.toLowerCase() === 'database.json');
  let bimRoles: any[] = [];
  if (bimFile) {
    bimRoles = parseModelBim(bimFile.content, tables, relationships, measures, calcCols, mSources, calcGroupEntries);
  }

  const reportJsonFiles: DroppedFile[] = [];
  const pageJsonFiles: DroppedFile[] = [];
  const visualJsonFiles: DroppedFile[] = [];

  // 1. Process TMDL files
  for (const file of validFiles) {
    const lowerPath = file.path.toLowerCase().replace(/\\/g, '/');

    // RLS role TMDL (definition/roles/*.tmdl) — must be checked before the
    // generic table-TMDL branch below, since role files don't start with `table `.
    if (lowerPath.endsWith('.tmdl') && lowerPath.includes('/roles/')) {
      const roleName = file.name.replace(/\.tmdl$/i, '');
      roleReferences.push(...extractRlsTmdlReferences(roleName, file.content, file.path));
      continue;
    }

    // Table TMDL
    if (lowerPath.endsWith('.tmdl') && (lowerPath.includes('/tables/') || lowerPath.includes('table '))) {
      parseTableTmdl(file.content, tables, measures, calcCols, mSources, calcGroupEntries);
    }

    // Relationships TMDL
    if (lowerPath.endsWith('relationships.tmdl') || (lowerPath.endsWith('.tmdl') && file.content.includes('relationship '))) {
      parseRelationshipsTmdl(file.content, relationships);
    }

    // Modern PBIR: page.json / visual.json are collected and grouped after this
    // loop (a visual.json's page isn't known until all files have been seen).
    // Legacy report.json is self-contained (sections + visualContainers) and
    // collected too, processed in the same post-pass.
    if (lowerPath.endsWith('page.json')) {
      pageJsonFiles.push(file);
    } else if (lowerPath.endsWith('visual.json')) {
      visualJsonFiles.push(file);
    } else if (lowerPath.endsWith('report.json')) {
      reportJsonFiles.push(file);
    }
  }

  // Post-process: compute in_relationship signal by matching columns to relationship
  // endpoints (mirrors pbiscan.canonical.builder.CanonicalBuilder._build_columns).
  // Runs after both the model.bim pass and the TMDL pass so it applies to either source.
  {
    const relColumnKeys = new Set<string>();
    for (const rel of relationships) {
      relColumnKeys.add(`${rel.from_table.toLowerCase()}|${rel.from_column.toLowerCase()}`);
      relColumnKeys.add(`${rel.to_table.toLowerCase()}|${rel.to_column.toLowerCase()}`);
    }
    for (const tbl of tables) {
      for (const col of tbl.columns) {
        col.in_relationship = relColumnKeys.has(`${tbl.name.toLowerCase()}|${col.name.toLowerCase()}`);
      }
    }
  }

  // Build the Unified Semantic Reference Index (mirrors
  // pbiscan.canonical.builder.CanonicalBuilder._build_semantic_references):
  // Calculation Group DAX, Field Parameter NAMEOF() bindings, and RLS
  // tablePermission expressions all activate DAX reachability roots the same
  // way a visual binding does.
  const semanticRefs = new SemanticReferenceIndex();

  for (const entry of calcGroupEntries) {
    semanticRefs.addMany(extractCalcGroupReferences(entry.table, entry.items, `${entry.table}.tmdl`));
  }

  const knownMeasureNames = new Set(measures.map((m) => m.name));
  const knownColumnNames = new Set(tables.flatMap((t) => t.columns.map((c: any) => c.name)));
  for (const src of mSources) {
    semanticRefs.addMany(
      extractFieldParamReferences(src.table, src.source, knownMeasureNames, knownColumnNames, `${src.table} partition`)
    );
  }

  semanticRefs.addMany(roleReferences);
  if (bimRoles.length) {
    semanticRefs.addMany(extractRlsBimReferences(bimRoles, 'model.bim'));
  }

  // Build page/visual data (measure refs + hidden-page-aware visual/slicer counts)
  // from whichever report format is present — legacy report.json or modern PBIR
  // page.json + visual.json files.
  const visualMeasureRefs = new Set<string>();
  processLegacyReportJson(reportJsonFiles, pages, visualMeasureRefs);
  processModernPbirPages(pageJsonFiles, visualJsonFiles, pages, visualMeasureRefs);

  // Build the DAX dependency graph (measures + calculated columns) for
  // multi-hop, cycle-safe D004 reachability — mirrors
  // pbiscan.canonical.dax_graph.build_dax_graph.
  const daxGraph = buildDaxGraph(
    measures.map((m) => ({ name: m.name, table: m.table, expression: m.expression })),
    calcCols.map((c) => ({ name: c.name, table: c.table, expression: c.expression }))
  );
  const activeRootMeasures = new Set<string>([...visualMeasureRefs, ...semanticRefs.activeRootMeasureNames()]);

  // 2. Run quality rules
  const findings: AuditFinding[] = [];

  // M001: Bidirectional
  for (const rel of relationships) {
    if (rel.cross_filter_direction?.toLowerCase().includes('both')) {
      findings.push({
        rule_id: 'MODEL_BIDIRECTIONAL',
        category: 'model',
        severity: 'WARNING',
        title: 'Bi-directional relationship detected',
        issue: `Relationship between ${rel.from_table}[${rel.from_column}] and ${rel.to_table}[${rel.to_column}] is bi-directional.`,
        evidence: `${rel.from_table}[${rel.from_column}] <-> ${rel.to_table}[${rel.to_column}] (BothDirections)`,
        impact: 'Bidirectional relationships create ambiguity in filter propagation and increase DAX context transition overhead.',
        recommendation: 'Change to single-directional cross-filtering or evaluate using CROSSFILTER() in DAX.',
        confidence: 100,
        location: `${rel.from_table}[${rel.from_column}] <-> ${rel.to_table}[${rel.to_column}]`,
      });
    }

    // M002: Many-to-Many
    if (rel.cardinality?.toLowerCase().includes('manytomany') || rel.cardinality?.toLowerCase().includes('both')) {
      findings.push({
        rule_id: 'MODEL_MANY_TO_MANY',
        category: 'model',
        severity: 'WARNING',
        title: 'Many-to-many relationship detected',
        issue: `Many-to-many cardinality between ${rel.from_table} and ${rel.to_table}.`,
        evidence: `${rel.from_table}[${rel.from_column}] *..* ${rel.to_table}[${rel.to_column}]`,
        impact: 'Many-to-many relationships rely on hash tables in memory and introduce filter ambiguity.',
        recommendation: 'Introduce a distinct bridge dimension table to resolve into two 1:N relationships.',
        confidence: 100,
        location: `${rel.from_table} -> ${rel.to_table}`,
      });
    }

  }

  // M005: Fact-to-fact relationships (mirrors pbiscan.rules.model.check_fact_to_fact)
  {
    const measureTables = new Set(measures.map((m) => m.table));
    const dimHints = ['dim', 'dimension', 'lookup', 'ref', 'reference', 'bridge'];
    for (const rel of relationships) {
      const fromHasMeasures = measureTables.has(rel.from_table);
      const toHasMeasures = measureTables.has(rel.to_table);
      if (!fromHasMeasures || !toHasMeasures) continue;

      const fromLooksLikeDim = dimHints.some((h) => rel.from_table.toLowerCase().includes(h));
      const toLooksLikeDim = dimHints.some((h) => rel.to_table.toLowerCase().includes(h));

      if (!fromLooksLikeDim && !toLooksLikeDim) {
        findings.push({
          rule_id: 'MODEL_FACT_TO_FACT',
          category: 'model',
          severity: 'ADVISORY',
          title: 'Potential fact-to-fact relationship detected',
          issue: `Both '${rel.from_table}' and '${rel.to_table}' contain measures and neither matches a dimension naming pattern.`,
          evidence: `${rel.from_table} -> ${rel.to_table}: both tables contain measures and neither matches a dimension naming pattern.`,
          impact: 'Direct relationships between transactional fact tables can produce inconsistent aggregation results.',
          recommendation: 'Introduce a shared dimension table to relate these facts, or confirm the relationship is intentional.',
          confidence: 60,
          location: `${rel.from_table} -> ${rel.to_table}`,
        });
      }
    }
  }

  // M003: No dedicated Date table (mirrors pbiscan.rules.model.check_no_date_table)
  if (tables.length > 0) {
    const dateNameHints = ['date', 'dim_date', 'dimdate', 'calendar', 'dim_calendar', 'time', 'dim_time'];
    const hasDateTable = tables.some(
      (t) => t.is_date_table || dateNameHints.some((h) => t.name.toLowerCase().includes(h))
    );
    if (!hasDateTable) {
      findings.push({
        rule_id: 'MODEL_NO_DATE_TABLE',
        category: 'model',
        severity: 'WARNING',
        title: 'No dedicated Date dimension table found',
        issue: 'No table is marked as a Date Table and no table matches date-dimension naming or data-category signals.',
        evidence: `Tables found: ${tables.map((t) => t.name).join(', ')}`,
        impact: 'Without a marked Date table, time-intelligence DAX functions (e.g. TOTALYTD, SAMEPERIODLASTYEAR) may behave unpredictably.',
        recommendation: 'Mark a dedicated table as the Date Table in Model view, or create one if missing.',
        confidence: 70,
        location: undefined,
      });
    }
  }

  // M004: High-cardinality columns (mirrors pbiscan.rules.model.check_high_cardinality)
  for (const tbl of tables) {
    for (const col of tbl.columns) {
      const dtype = (col.data_type || '').toLowerCase();
      if ((dtype === 'string' || dtype === 'text') && col.is_unique && !col.in_relationship) {
        findings.push({
          rule_id: 'MODEL_HIGH_CARDINALITY',
          category: 'model',
          severity: 'ADVISORY',
          title: 'Potential high-cardinality column',
          issue: `Column '${tbl.name}[${col.name}]' is a unique string/text column not used in any relationship.`,
          evidence: `${tbl.name}[${col.name}]: dataType=${col.data_type}, isUnique=${col.is_unique}, inRelationship=${col.in_relationship}`,
          impact: 'High-cardinality string columns inflate VertiPaq dictionary size and memory footprint.',
          recommendation: 'Consider removing, hashing, or splitting the column if it is not needed for reporting.',
          confidence: 87,
          location: `${tbl.name}[${col.name}]`,
        });
      }
    }
  }

  // M006: Hardcoded Data Sources (Power Query M)
  // Mirrors pbiscan.rules.model._LOCAL_USER_PATH_PATTERN exactly — requires a quoted
  // drive-letter path through a known local workstation folder (users/documents/desktop/
  // downloads/temp/tmp), or a quoted /users//home/ path. A bare "C:\" or "https://" is
  // NOT enough (the latter false-positived against the old ad hoc substring checks).
  const LOCAL_USER_PATH_PATTERN = /["'](?:[a-zA-Z]:[\\/](?:users|documents|desktop|downloads|temp|tmp)[^"']*|(?:\/users\/|\/home\/)[^"']*)["']/i;
  for (const src of mSources) {
    const s = src.source;
    if (LOCAL_USER_PATH_PATTERN.test(s)) {
      findings.push({
        rule_id: 'M_HARDCODED_DATA_SOURCE',
        category: 'model',
        severity: 'HIGH',
        title: 'Hardcoded local file path in Power Query data source',
        issue: `Table '${src.table}' references a hardcoded local machine file path in its M partition query.`,
        evidence: `Partition M query references local path: ${src.source.substring(0, 120)}...`,
        impact: 'Hardcoded local file paths fail in automated Power BI Gateway or Cloud Scheduled Refresh.',
        recommendation: 'Convert hardcoded file paths to Power Query Parameters or SharePoint/OneDrive URLs.',
        confidence: 100,
        location: `Table: ${src.table}`,
      });
    }
  }

  // M007: Auto-Date Tables (mirrors pbiscan.rules.model.check_auto_datetime_bloat —
  // only LocalDateTable_* prefixed tables count, not any table with "date" in its name)
  const hasAutoDate = tables.some((tbl) => tbl.name.toLowerCase().startsWith('localdatetable_'));
  if (hasAutoDate) {
    findings.push({
      rule_id: 'MODEL_AUTO_DATETIME_BLOAT',
      category: 'model',
      severity: 'MEDIUM',
      title: 'Auto Date/Time feature enabled generating hidden tables',
      issue: 'Semantic model contains auto-generated LocalDateTable_* hidden date hierarchies.',
      evidence: 'Model contains LocalDateTable_* tables generated by default Auto Date/Time.',
      impact: 'Auto Date/Time creates hidden tables for every date column, bloating file size and RAM footprint.',
      recommendation: 'Disable "Auto Date/Time" in Power BI Options and use a single centralized Date dimension.',
      confidence: 100,
      location: 'Model',
    });
  }

  // D002: Excessive Calc Columns
  for (const tbl of tables) {
    if (tbl.calc_cols_count > 4) {
      findings.push({
        rule_id: 'DAX_EXCESSIVE_CALC_COLUMNS',
        category: 'dax',
        severity: 'MEDIUM',
        title: 'Excessive calculated columns on table',
        issue: `Table '${tbl.name}' has ${tbl.calc_cols_count} calculated columns, exceeding the threshold of 4.`,
        evidence: `${tbl.name} contains ${tbl.calc_cols_count} calculated columns.`,
        impact: 'Calculated columns consume uncompressed VertiPaq RAM and slow down model refresh.',
        recommendation: 'Move calculations upstream to Power Query (M) or SQL ETL.',
        confidence: 100,
        location: `Table: ${tbl.name}`,
      });
    }
  }

  // D001: Suspicious DAX Patterns (mirrors pbiscan.rules.dax.check_suspicious_dax —
  // driven purely by the three regex patterns in rules.config.json; one finding per
  // measure, first match wins. No ad hoc "naked division" or "/0" heuristics.)
  const SUSPICIOUS_DAX_PATTERNS: [RegExp, string][] = [
    [/FILTER\s*\(\s*ALL\s*\(/is, 'FILTER(ALL(...)) — consider CALCULATE with filter arguments'],
    [/\bEARLIER\s*\(/is, 'EARLIER() — legacy iterator function; consider VAR/RETURN instead'],
    [/CALCULATE\s*\(.*?CALCULATE\s*\(/is, 'Nested CALCULATE() — verify context-transition behaviour'],
  ];
  for (const m of measures) {
    for (const [pattern, description] of SUSPICIOUS_DAX_PATTERNS) {
      if (pattern.test(m.expression)) {
        findings.push({
          rule_id: 'DAX_SUSPICIOUS_PATTERN',
          category: 'dax',
          severity: 'ADVISORY',
          title: 'Suspicious DAX pattern detected',
          issue: `Measure '${m.name}' [${m.table}]: ${description}`,
          evidence: `Measure '${m.name}' [${m.table}]: ${description}`,
          impact: 'Indicates a pattern worth reviewing; does not by itself prove a performance problem.',
          recommendation: 'Review the flagged expression against the suggested alternative pattern.',
          confidence: 65,
          location: `Measure: ${m.name}`,
        });
        break;
      }
    }
  }

  // D003: Duplicate Measures
  const normalizedMap = new Map<string, MeasureInfo[]>();
  for (const m of measures) {
    const norm = m.expression.replace(/\s+/g, '').toLowerCase();
    if (norm.length > 5) {
      const list = normalizedMap.get(norm) || [];
      list.push(m);
      normalizedMap.set(norm, list);
    }
  }
  for (const [_, list] of normalizedMap.entries()) {
    if (list.length > 1) {
      const names = list.map((m) => `${m.table}[${m.name}]`).join(', ');
      findings.push({
        rule_id: 'DAX_DUPLICATE_MEASURE',
        category: 'dax',
        severity: 'MEDIUM',
        title: 'Duplicate measure logic detected',
        issue: `Multiple measures contain identical normalized expressions: ${names}`,
        evidence: list[0].expression,
        impact: 'Redundant measures create maintenance overhead and duplicate cache footprint.',
        recommendation: 'Consolidate duplicate measures into a single reusable measure.',
        confidence: 90,
        location: names,
      });
    }
  }

  // D004: Unused Measures (mirrors pbiscan.rules.dax.check_unused_measures — multi-hop,
  // cycle-safe DaxDependencyGraph.is_reachable_from_visual against the combined root set
  // of visual bindings + calc group / field parameter / RLS semantic references, instead
  // of a shallow one-hop cross-measure regex scan.)
  for (const m of measures) {
    const isUsed = daxGraph.isReachableFromVisual(m.name, activeRootMeasures);
    if (!isUsed) {
      findings.push({
        rule_id: 'DAX_UNUSED_MEASURE',
        category: 'dax',
        severity: 'ADVISORY',
        title: 'Potentially unused measure',
        issue: `Measure '${m.name}' is not placed in any report visuals and not referenced by other measures.`,
        evidence: `Measure '${m.name}' in ${m.table}: 0 downstream visual or DAX references found.`,
        impact: 'Unused measures bloat the model field list.',
        recommendation: 'Review and remove or hide if not needed for ad-hoc analysis.',
        confidence: 90,
        location: `Measure: ${m.name}`,
      });
    }
  }

  // R001 & R002: Visual & Slicer Bloat (hidden pages excluded, mirrors
  // pbiscan.rules.report — both check_visual_bloat and check_slicer_bloat skip
  // pages where visibility != 0)
  for (const p of pages) {
    if (p.is_hidden) continue;
    if (p.visual_count > 15) {
      findings.push({
        rule_id: 'REPORT_VISUAL_BLOAT',
        category: 'report',
        severity: 'MEDIUM',
        title: 'Visual bloat detected on page',
        issue: `Page '${p.display_name}' has ${p.visual_count} visuals, exceeding the limit of 15.`,
        evidence: `Page '${p.display_name}' contains ${p.visual_count} visuals.`,
        impact: 'High visual counts generate concurrent DAX queries that spike page render latency.',
        recommendation: 'Consolidate visuals using multi-row cards or split into drill-through tabs.',
        confidence: 100,
        location: `Page: ${p.display_name}`,
      });
    }
    if (p.slicer_count > 6) {
      findings.push({
        rule_id: 'REPORT_SLICER_BLOAT',
        category: 'report',
        severity: 'MEDIUM',
        title: 'Excessive slicers on page',
        issue: `Page '${p.display_name}' has ${p.slicer_count} slicers, exceeding the threshold of 6.`,
        evidence: `Page '${p.display_name}' contains ${p.slicer_count} slicers.`,
        impact: 'Excessive slicers generate redundant query overhead on initial page load.',
        recommendation: 'Use the native Power BI Filter Pane or sync slicers across pages.',
        confidence: 100,
        location: `Page: ${p.display_name}`,
      });
    }
  }

  // Calculate Scores
  const scores = calculateClientScores(findings);

  return {
    report_name: projectName,
    source_path: projectName,
    scores,
    findings,
    tables: tables.filter(t => !t.name.toLowerCase().includes('localdatetable') && !t.name.toLowerCase().includes('datetabletemplate')),
    relationships,
    measures,
    calculated_columns: calcCols,
    pages,
    warnings: [],
    summary: {
      total_findings: findings.length,
      table_count: tables.length,
      measure_count: measures.length,
      relationship_count: relationships.length,
      page_count: pages.length,
    },
  };
}

function _detectIsUnique(col: any): boolean {
  if (col.isUnique || col.isKey) return true;
  if (Array.isArray(col.annotations)) {
    for (const ann of col.annotations) {
      if (ann.name === 'PBI_IsUnique' && String(ann.value).toLowerCase() === 'true') return true;
    }
  }
  return false;
}

/** Returns the model.bim `model.roles` array (raw TMSL) for RLS extraction. */
function parseModelBim(
  content: string,
  tables: TableInfo[],
  relationships: RelationshipInfo[],
  measures: MeasureInfo[],
  calcCols: CalculatedColumnInfo[],
  mSources: { table: string; source: string }[],
  calcGroupEntries: CalcGroupEntry[]
): any[] {
  try {
    const data = JSON.parse(content);
    const model = data.model || data;

    if (model.tables && Array.isArray(model.tables)) {
      for (const t of model.tables) {
        const colList: any[] = [];
        let tMeasures = 0;
        let tCalcCols = 0;

        if (t.columns && Array.isArray(t.columns)) {
          for (const col of t.columns) {
            if (col.type === 'calculated' || col.expression) {
              tCalcCols++;
              calcCols.push({
                name: col.name,
                table: t.name,
                expression: Array.isArray(col.expression) ? col.expression.join('\n') : (col.expression || ""),
                data_type: col.dataType || 'string',
              });
            } else {
              colList.push({
                name: col.name,
                data_type: col.dataType || 'string',
                is_unique: _detectIsUnique(col),
                in_relationship: false,
                hidden: col.isHidden || false,
              });
            }
          }
        }

        if (t.measures && Array.isArray(t.measures)) {
          for (const m of t.measures) {
            tMeasures++;
            measures.push({
              name: m.name,
              table: t.name,
              expression: Array.isArray(m.expression) ? m.expression.join('\n') : (m.expression || ""),
              hidden: m.isHidden || false,
            });
          }
        }

        if (t.partitions && Array.isArray(t.partitions)) {
          for (const part of t.partitions) {
            if (part.source && part.source.expression) {
              const expr = Array.isArray(part.source.expression) ? part.source.expression.join('\n') : part.source.expression;
              mSources.push({ table: t.name, source: expr });
            }
          }
        }

        // Calculation Group items (TMSL: table.calculationGroup.calculationItems[]).
        // NOTE: pbiscan's own BIM extractor has the same behavior mirrored here —
        // it doesn't map the raw TMSL `formatStringDefinition` key into the
        // extractor's `format_string`/`format_string_definition` fields, so
        // format-string-embedded bracket references are only picked up for
        // TMDL-sourced calc groups, not BIM-sourced ones. Matched here for parity.
        const calcGroup = t.calculationGroup;
        if (calcGroup && Array.isArray(calcGroup.calculationItems)) {
          calcGroupEntries.push({
            table: t.name,
            items: calcGroup.calculationItems.map((item: any) => ({
              name: item.name || 'UnknownItem',
              expression: Array.isArray(item.expression) ? item.expression.join('\n') : (item.expression || ''),
            })),
          });
        }

        tables.push({
          name: t.name,
          hidden: t.isHidden || false,
          is_date_table: t.name.toLowerCase().includes('localdatetable') || t.name.toLowerCase().includes('date'),
          column_count: colList.length,
          columns: colList,
          measures_count: tMeasures,
          calc_cols_count: tCalcCols,
        });
      }
    }

    if (model.relationships && Array.isArray(model.relationships)) {
      for (const r of model.relationships) {
        relationships.push({
          from_table: r.fromTable || "",
          from_column: r.fromColumn || "",
          to_table: r.toTable || "",
          to_column: r.toColumn || "",
          cardinality: r.cardinality || (r.fromCardinality && r.toCardinality ? `${r.fromCardinality}To${r.toCardinality}` : 'manyToOne'),
          cross_filter_direction: r.crossFilteringBehavior === 'bothDirections' ? 'both' : (r.crossFilteringBehavior || 'single'),
          is_active: r.isActive !== false,
        });
      }
    }

    return Array.isArray(model.roles) ? model.roles : [];
  } catch (e) {
    console.error("Failed to parse model.bim JSON:", e);
    return [];
  }
}

function _leadingTabDepth(rawLine: string): number {
  let n = 0;
  while (n < rawLine.length && rawLine[n] === '\t') n++;
  return n;
}

function parseTableTmdl(
  content: string,
  tables: TableInfo[],
  measures: MeasureInfo[],
  calcCols: CalculatedColumnInfo[],
  mSources: { table: string; source: string }[],
  calcGroupEntries: CalcGroupEntry[]
) {
  const lines = content.split('\n');
  let currentTable = "UnknownTable";
  let columns: any[] = [];
  let tableMeasures = 0;
  let tableCalcCols = 0;
  let inPartition = false;
  let partitionSource = "";
  let calcItems: CalcItem[] = [];

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();
    if (line.startsWith('table ') || line.startsWith('table\t')) {
      currentTable = line.substring(6).replace(/['"]/g, '').trim();
    } else if (line.startsWith('partition ') || line.startsWith('partition\t')) {
      inPartition = true;
    } else if (inPartition) {
      partitionSource += line + "\n";
    } else if (line.startsWith('column ') || line.startsWith('column\t')) {
      // NOTE: pbiscan's own TMDL extractor does not parse `isKey`/annotations into a
      // uniqueness signal today (only the model.bim/database.json JSON path does via
      // _detect_is_unique) — so is_unique intentionally stays false here for strict
      // parity with the Python engine, even though this under-detects MODEL_HIGH_CARDINALITY
      // for TMDL-sourced projects. Fixing that is a Python-side gap, not a TS one.
      const colName = line.substring(7).split('=')[0].trim();
      if (line.includes('=')) {
        tableCalcCols++;
        const expr = line.split('=').slice(1).join('=').trim();
        calcCols.push({ name: colName, table: currentTable, expression: expr, data_type: 'string' });
      } else {
        columns.push({ name: colName, data_type: 'string', is_unique: false, in_relationship: false, hidden: false });
      }
    } else if (line.startsWith('measure ') || line.startsWith('measure\t')) {
      const measureDepth = _leadingTabDepth(rawLine);
      tableMeasures++;
      const measureHeader = line.substring(8).trim();
      let measureName = measureHeader;
      let expr = "";
      if (measureHeader.includes('=')) {
        measureName = measureHeader.split('=')[0].trim();
        expr = measureHeader.split('=').slice(1).join('=').trim();
      }
      // Only lines MORE indented than the `measure` declaration itself belong to this
      // measure's body/metadata; a sibling `measure`/`column`/`partition` line at the
      // same depth ends it. (A prior version used a bare tab-prefix check, which never
      // stopped at sibling declarations and silently concatenated every subsequent
      // measure's DAX into the current one's expression.)
      let j = i + 1;
      while (j < lines.length && lines[j].trim() !== '' && _leadingTabDepth(lines[j]) > measureDepth) {
        const propLine = lines[j].trim();
        if (!propLine.startsWith('lineageTag') && !propLine.startsWith('formatString') && !propLine.startsWith('//')) {
          expr += (expr ? '\n' : '') + propLine;
        }
        j++;
      }
      measures.push({
        name: measureName.replace(/['"[\]]/g, ''),
        table: currentTable,
        expression: expr || "BLANK()",
        hidden: false,
      });
    } else if (line.startsWith('calculationItem ') || line.startsWith('calculationItem\t')) {
      const itemDepth = _leadingTabDepth(rawLine);
      const itemHeader = line.substring(16).trim();
      let itemName = itemHeader;
      const bodyLines: string[] = [];
      if (itemHeader.includes('=')) {
        itemName = itemHeader.split('=')[0].trim();
        const inlineExpr = itemHeader.split('=').slice(1).join('=').trim();
        if (inlineExpr) bodyLines.push(inlineExpr);
      }
      let j = i + 1;
      while (j < lines.length && lines[j].trim() !== '' && _leadingTabDepth(lines[j]) > itemDepth) {
        const propLine = lines[j].trim();
        if (!propLine.startsWith('lineageTag') && !propLine.startsWith('//')) {
          bodyLines.push(propLine);
        }
        j++;
      }
      // A `formatStringDefinition = ...` (or possibly multi-line) property sits
      // inline within the captured body — split there into expression vs format string.
      const fmtIdx = bodyLines.findIndex((l) => /^formatStringDefinition\s*[:=]/.test(l));
      let expression: string;
      let formatString: string | undefined;
      if (fmtIdx === -1) {
        expression = bodyLines.join('\n');
      } else {
        expression = bodyLines.slice(0, fmtIdx).join('\n');
        const fmtLines = bodyLines.slice(fmtIdx);
        const sep = fmtLines[0].includes('=') ? '=' : ':';
        fmtLines[0] = fmtLines[0].split(sep).slice(1).join(sep).trim();
        formatString = fmtLines.join('\n');
      }
      calcItems.push({
        name: itemName.replace(/['"[\]]/g, ''),
        expression,
        format_string: formatString,
      });
    }
  }

  if (partitionSource) {
    mSources.push({ table: currentTable, source: partitionSource });
  }
  if (calcItems.length) {
    calcGroupEntries.push({ table: currentTable, items: calcItems });
  }

  tables.push({
    name: currentTable,
    hidden: false,
    is_date_table: currentTable.toLowerCase().includes('date') || currentTable.toLowerCase().includes('calendar'),
    column_count: columns.length,
    columns,
    measures_count: tableMeasures,
    calc_cols_count: tableCalcCols,
  });
}

function parseRelationshipsTmdl(content: string, relationships: RelationshipInfo[]) {
  const relBlocks = content.split(/relationship\s+/i);
  for (const block of relBlocks) {
    if (!block.trim()) continue;
    const lines = block.split('\n');
    let fromTable = "", fromCol = "", toTable = "", toCol = "";
    let bidi = false;

    for (const l of lines) {
      const line = l.trim();
      if (line.startsWith('fromColumn:')) {
        const parts = line.substring(11).trim().split('.');
        fromTable = parts[0]?.replace(/['"]/g, '') || "";
        fromCol = parts[1]?.replace(/[\[\]']/g, '') || "";
      } else if (line.startsWith('toColumn:')) {
        const parts = line.substring(9).trim().split('.');
        toTable = parts[0]?.replace(/['"]/g, '') || "";
        toCol = parts[1]?.replace(/[\[\]']/g, '') || "";
      } else if (line.includes('crossFilteringBehavior: bothDirections')) {
        bidi = true;
      }
    }

    if (fromTable && toTable) {
      relationships.push({
        from_table: fromTable,
        from_column: fromCol,
        to_table: toTable,
        to_column: toCol,
        cardinality: 'manyToOne',
        cross_filter_direction: bidi ? 'both' : 'single',
        is_active: true,
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Report/visual parsing — legacy report.json and modern PBIR page.json/visual.json
// ---------------------------------------------------------------------------

/** Legacy format: a single report.json with `sections[].visualContainers[]`.
 * Mirrors PBIPReader._parse_single_visual_container: measure refs come from
 * prototypeQuery.Select[], projections{}, AND a full recursive AST walk of the
 * parsed visual config (objects.title/subTitle/referenceLabel/conditional
 * formatting/filters — not just a crude bracket-text scan). */
function processLegacyReportJson(files: DroppedFile[], pages: PageInfo[], visualMeasureRefs: Set<string>) {
  for (const file of files) {
    try {
      const data = JSON.parse(file.content);
      if (!data.sections || !Array.isArray(data.sections)) continue;

      const existingNames = new Set(pages.map((p) => p.name));
      for (const s of data.sections) {
        if (existingNames.has(s.name)) continue;
        existingNames.add(s.name);

        let slicerCount = 0;
        const containers = Array.isArray(s.visualContainers) ? s.visualContainers : [];
        for (const vc of containers) {
          const configStr = vc.config || "{}";
          let config: any = {};
          if (typeof configStr === 'string') {
            try {
              config = JSON.parse(configStr);
            } catch {
              config = {};
            }
          } else {
            config = configStr;
          }

          const singleVisual = config.singleVisual || {};
          const visualType = (singleVisual.visualType || '').toLowerCase();
          if (visualType === 'slicer') slicerCount++;

          const pq = singleVisual.prototypeQuery || {};
          for (const selectItem of pq.Select || []) {
            if (selectItem.Measure) {
              const prop = selectItem.Measure.Property;
              if (prop) visualMeasureRefs.add(prop);
            }
          }

          const projections = singleVisual.projections || {};
          if (projections && typeof projections === 'object') {
            for (const items of Object.values(projections)) {
              if (Array.isArray(items)) {
                for (const item of items as any[]) {
                  const qref = item?.queryRef;
                  if (qref) {
                    const clean = qref.includes('.') ? qref.split('.').slice(1).join('.') : qref;
                    visualMeasureRefs.add(clean);
                  }
                }
              }
            }
          }

          for (const m of extractMeasureNamesFromExprTree(config)) visualMeasureRefs.add(m);
        }

        const visibility = typeof s.visibility === 'number' ? s.visibility : 0;
        pages.push({
          name: s.name || `Section_${pages.length + 1}`,
          display_name: s.displayName || `Page ${pages.length + 1}`,
          is_hidden: visibility !== 0,
          visual_count: containers.length,
          slicer_count: slicerCount,
        });
      }
    } catch {
      // Non-JSON or malformed report.json — skip.
    }
  }
}

/** Modern PBIR format: page.json (page metadata) and visual.json (one file per
 * visual, under pages/<pageId>/visuals/<visualId>/visual.json) are separate
 * files, so visuals can't be attributed to a page until all files are seen. */
function processModernPbirPages(
  pageFiles: DroppedFile[],
  visualFiles: DroppedFile[],
  pages: PageInfo[],
  visualMeasureRefs: Set<string>
) {
  if (!pageFiles.length && !visualFiles.length) return;

  const pageIdFromPath = (path: string): string => {
    const segments = path.replace(/\\/g, '/').split('/');
    const idx = segments.findIndex((s) => s.toLowerCase() === 'pages');
    if (idx !== -1 && idx + 1 < segments.length) return segments[idx + 1];
    // Fallback: parent directory name.
    return segments[segments.length - 2] || 'UnknownPage';
  };

  interface PageAgg {
    displayName: string;
    isHidden: boolean;
    visualCount: number;
    slicerCount: number;
  }
  const pageMap = new Map<string, PageAgg>();

  for (const file of pageFiles) {
    const pageId = pageIdFromPath(file.path);
    try {
      const data = JSON.parse(file.content);
      const visibility = typeof data.visibility === 'number' ? data.visibility : 0;
      pageMap.set(pageId, {
        displayName: data.displayName || pageId,
        isHidden: visibility !== 0,
        visualCount: 0,
        slicerCount: 0,
      });
    } catch {
      pageMap.set(pageId, { displayName: pageId, isHidden: false, visualCount: 0, slicerCount: 0 });
    }
  }

  for (const file of visualFiles) {
    const pageId = pageIdFromPath(file.path);
    let agg = pageMap.get(pageId);
    if (!agg) {
      agg = { displayName: pageId, isHidden: false, visualCount: 0, slicerCount: 0 };
      pageMap.set(pageId, agg);
    }
    agg.visualCount++;

    try {
      const raw = JSON.parse(file.content);
      const visualNode = raw.visual || {};
      const visualType = (visualNode.visualType || '').toLowerCase();
      if (visualType === 'slicer') agg.slicerCount++;

      // queryState projections (mirrors PBIPReader._extract_measure_refs_from_pbir_query)
      const queryState = visualNode.query?.queryState || {};
      for (const bucket of Object.values(queryState)) {
        const projections = (bucket as any)?.projections;
        if (Array.isArray(projections)) {
          for (const proj of projections) {
            const prop = proj?.field?.Measure?.Property;
            if (prop) visualMeasureRefs.add(prop);
          }
        }
      }

      // Full recursive AST walk (objects.referenceLabel/title/subTitle/conditional
      // formatting/filters, etc.) — mirrors PBIPReader._extract_measure_names_from_expr_tree.
      for (const m of extractMeasureNamesFromExprTree(raw)) visualMeasureRefs.add(m);
    } catch {
      // Malformed visual.json — counted above, just skip measure-ref extraction.
    }
  }

  const existingNames = new Set(pages.map((p) => p.name));
  for (const [pageId, agg] of pageMap.entries()) {
    if (existingNames.has(pageId)) continue;
    pages.push({
      name: pageId,
      display_name: agg.displayName,
      is_hidden: agg.isHidden,
      visual_count: agg.visualCount,
      slicer_count: agg.slicerCount,
    });
  }
}

function calculateClientScores(findings: AuditFinding[]): ScoreData {
  let modelDeductions = 0;
  let daxDeductions = 0;
  let reportDeductions = 0;

  for (const f of findings) {
    let ded = 5;
    if (f.severity === 'CRITICAL') ded = 15;
    else if (f.severity === 'HIGH') ded = 10;
    else if (f.severity === 'MEDIUM') ded = 5;
    else if (f.severity === 'WARNING') ded = 3;
    else if (f.severity === 'ADVISORY' || f.severity === 'LOW') ded = 1;

    if (f.category === 'model') modelDeductions += ded;
    else if (f.category === 'dax') daxDeductions += ded;
    else if (f.category === 'report') reportDeductions += ded;
  }

  const modelScore = Math.max(0, 100 - modelDeductions);
  const daxScore = Math.max(0, 100 - daxDeductions);
  const reportScore = Math.max(0, 100 - reportDeductions);

  // Weights: model 0.35, dax 0.25, report 0.20 (normalized across active categories)
  const overall = Number(((modelScore * 0.35 + daxScore * 0.25 + reportScore * 0.20) / 0.80).toFixed(1));

  return {
    overall,
    category_scores: {
      model: modelScore,
      dax: daxScore,
      report: reportScore,
    },
  };
}
