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
import { SUPPRESSIONS_FILENAME, applySuppressions, loadSuppressions } from './suppressions';

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

  // Filter out backup folders, git, and metadata. A leading byte-order mark is
  // dropped: it would hide a TMDL file's first line and make JSON.parse fail.
  const validFiles = files.filter(f => {
    const p = f.path.toLowerCase().replace(/\\/g, '/');
    return !p.includes('/backup/') && !p.startsWith('backup/') && !p.includes('/.git/') && !p.includes('/.pbi/');
  }).map((f) => (f.content.charCodeAt(0) === 0xfeff ? { ...f, content: f.content.slice(1) } : f));

  // Files that exist but could not be parsed. Any of them could define or use a
  // measure, so D004 (unused measures) is not reported while this is non-empty —
  // mirrors RawExtraction.unread_files in the Python reader.
  const unreadFiles: string[] = [];

  // Check for model.bim or database.json
  const bimFile = validFiles.find(f => f.name.toLowerCase() === 'model.bim' || f.name.toLowerCase() === 'database.json');
  let bimRoles: any[] = [];
  if (bimFile) {
    const roles = parseModelBim(bimFile.content, tables, relationships, measures, calcCols, mSources, calcGroupEntries);
    if (roles === null) unreadFiles.push(bimFile.path);
    else bimRoles = roles;
  }

  const reportJsonFiles: DroppedFile[] = [];
  const pageJsonFiles: DroppedFile[] = [];
  const visualJsonFiles: DroppedFile[] = [];
  const reportLevelFiles: DroppedFile[] = [];

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
    if (lowerPath.endsWith('.tmdl') && lowerPath.includes('/tables/')) {
      if (!parseTableTmdl(file.content, tables, measures, calcCols, mSources, calcGroupEntries)) {
        unreadFiles.push(file.path);
      }
    }

    // Relationships TMDL
    if (lowerPath.endsWith('relationships.tmdl')) {
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
    } else if (lowerPath.endsWith('reportextensions.json') || (lowerPath.includes('/bookmarks/') && lowerPath.endsWith('.json'))) {
      reportLevelFiles.push(file);
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
  processLegacyReportJson(reportJsonFiles, pages, visualMeasureRefs, unreadFiles);
  processModernPbirPages(pageJsonFiles, visualJsonFiles, pages, visualMeasureRefs, unreadFiles);
  // Page/report-level filters, bookmarks and report-level ("thin report") measures
  // (mirrors PBIPReader._parse_report_level + CanonicalBuilder steps 1b-1d)
  processReportLevelReferences(reportJsonFiles, reportLevelFiles, knownMeasureNames, visualMeasureRefs, unreadFiles);

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
        ...ruleMeta('MODEL_BIDIRECTIONAL'),
        title: 'Bi-directional relationship detected',
        issue: `Relationship between ${rel.from_table}[${rel.from_column}] and ${rel.to_table}[${rel.to_column}] is bi-directional.`,
        evidence: `${rel.from_table}[${rel.from_column}] <-> ${rel.to_table}[${rel.to_column}] (BothDirections)`,
        impact: 'Bidirectional relationships create ambiguity in filter propagation and increase DAX context transition overhead.',
        recommendation: 'Change to single-directional cross-filtering or evaluate using CROSSFILTER() in DAX.',
        location: `${rel.from_table}[${rel.from_column}] <-> ${rel.to_table}[${rel.to_column}]`,
      });
    }

    // M002: Many-to-Many
    if (rel.cardinality?.toLowerCase().includes('manytomany') || rel.cardinality?.toLowerCase().includes('both')) {
      findings.push({
        ...ruleMeta('MODEL_MANY_TO_MANY'),
        title: 'Many-to-many relationship detected',
        issue: `Many-to-many cardinality between ${rel.from_table} and ${rel.to_table}.`,
        evidence: `${rel.from_table}[${rel.from_column}] *..* ${rel.to_table}[${rel.to_column}]`,
        impact: 'Many-to-many relationships rely on hash tables in memory and introduce filter ambiguity.',
        recommendation: 'Introduce a distinct bridge dimension table to resolve into two 1:N relationships.',
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
          ...ruleMeta('MODEL_FACT_TO_FACT'),
          title: 'Potential fact-to-fact relationship detected',
          issue: `Both '${rel.from_table}' and '${rel.to_table}' contain measures and neither matches a dimension naming pattern.`,
          evidence: `${rel.from_table} -> ${rel.to_table}: both tables contain measures and neither matches a dimension naming pattern.`,
          impact: 'Direct relationships between transactional fact tables can produce inconsistent aggregation results.',
          recommendation: 'Introduce a shared dimension table to relate these facts, or confirm the relationship is intentional.',
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
        ...ruleMeta('MODEL_NO_DATE_TABLE'),
        title: 'No dedicated Date dimension table found',
        issue: 'No table is marked as a Date Table and no table matches date-dimension naming or data-category signals.',
        evidence: `Tables found: ${tables.map((t) => t.name).join(', ')}`,
        impact: 'Without a marked Date table, time-intelligence DAX functions (e.g. TOTALYTD, SAMEPERIODLASTYEAR) may behave unpredictably.',
        recommendation: 'Mark a dedicated table as the Date Table in Model view, or create one if missing.',
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
          ...ruleMeta('MODEL_HIGH_CARDINALITY'),
          title: 'Potential high-cardinality column',
          issue: `Column '${tbl.name}[${col.name}]' is a unique string/text column not used in any relationship.`,
          evidence: `${tbl.name}[${col.name}]: dataType=${col.data_type}, isUnique=${col.is_unique}, inRelationship=${col.in_relationship}`,
          impact: 'High-cardinality string columns inflate VertiPaq dictionary size and memory footprint.',
          recommendation: 'Consider removing, hashing, or splitting the column if it is not needed for reporting.',
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
        ...ruleMeta('M_HARDCODED_DATA_SOURCE'),
        title: 'Hardcoded local file path in Power Query data source',
        issue: `Table '${src.table}' references a hardcoded local machine file path in its M partition query.`,
        evidence: `Partition M query references local path: ${src.source.substring(0, 120)}...`,
        impact: 'Hardcoded local file paths fail in automated Power BI Gateway or Cloud Scheduled Refresh.',
        recommendation: 'Convert hardcoded file paths to Power Query Parameters or SharePoint/OneDrive URLs.',
        location: `Table: ${src.table}`,
      });
    }
  }

  // M007: Auto-Date Tables (mirrors pbiscan.rules.model.check_auto_datetime_bloat —
  // only LocalDateTable_* prefixed tables count, not any table with "date" in its name)
  const hasAutoDate = tables.some((tbl) => tbl.name.toLowerCase().startsWith('localdatetable_'));
  if (hasAutoDate) {
    findings.push({
      ...ruleMeta('MODEL_AUTO_DATETIME_BLOAT'),
      title: 'Auto Date/Time feature enabled generating hidden tables',
      issue: 'Semantic model contains auto-generated LocalDateTable_* hidden date hierarchies.',
      evidence: 'Model contains LocalDateTable_* tables generated by default Auto Date/Time.',
      impact: 'Auto Date/Time creates hidden tables for every date column, bloating file size and RAM footprint.',
      recommendation: 'Disable "Auto Date/Time" in Power BI Options and use a single centralized Date dimension.',
      location: 'Model',
    });
  }

  // D002: Excessive Calc Columns
  for (const tbl of tables) {
    if (tbl.calc_cols_count > 4) {
      findings.push({
        ...ruleMeta('DAX_EXCESSIVE_CALC_COLUMNS'),
        title: 'Excessive calculated columns on table',
        issue: `Table '${tbl.name}' has ${tbl.calc_cols_count} calculated columns, exceeding the threshold of 4.`,
        evidence: `${tbl.name} contains ${tbl.calc_cols_count} calculated columns.`,
        impact: 'Calculated columns consume uncompressed VertiPaq RAM and slow down model refresh.',
        recommendation: 'Move calculations upstream to Power Query (M) or SQL ETL.',
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
          ...ruleMeta('DAX_SUSPICIOUS_PATTERN'),
          title: 'Suspicious DAX pattern detected',
          issue: `Measure '${m.name}' [${m.table}]: ${description}`,
          evidence: `Measure '${m.name}' [${m.table}]: ${description}`,
          impact: 'Indicates a pattern worth reviewing; does not by itself prove a performance problem.',
          recommendation: 'Review the flagged expression against the suggested alternative pattern.',
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
        ...ruleMeta('DAX_DUPLICATE_MEASURE'),
        title: 'Duplicate measure logic detected',
        issue: `Multiple measures contain identical normalized expressions: ${names}`,
        evidence: list[0].expression,
        impact: 'Redundant measures create maintenance overhead and duplicate cache footprint.',
        recommendation: 'Consolidate duplicate measures into a single reusable measure.',
        location: names,
      });
    }
  }

  // D004: Unused Measures (mirrors pbiscan.rules.dax.check_unused_measures — multi-hop,
  // cycle-safe DaxDependencyGraph.is_reachable_from_visual against the combined root set
  // of visual bindings + calc group / field parameter / RLS semantic references, instead
  // of a shallow one-hop cross-measure regex scan.) Skipped entirely when any file could
  // not be read: that file may be the only place a measure is used.
  const warnings: string[] = unreadFiles.map((path) => `Skipped ${path}: could not be parsed`);
  if (unreadFiles.length) {
    warnings.push(
      `DAX_UNUSED_MEASURE was not checked: ${unreadFiles.length} project file(s) could not be read, ` +
      'and any of them could use a measure that would otherwise look unused.'
    );
  }
  for (const m of unreadFiles.length ? [] : measures) {
    const isUsed = daxGraph.isReachableFromVisual(m.name, activeRootMeasures);
    if (!isUsed) {
      findings.push({
        ...ruleMeta('DAX_UNUSED_MEASURE'),
        title: 'Potentially unused measure',
        issue: `Measure '${m.name}' is not placed in any report visuals and not referenced by other measures.`,
        evidence: `Measure '${m.name}' in ${m.table}: 0 downstream visual or DAX references found.`,
        impact: 'Unused measures bloat the model field list.',
        recommendation: 'Review and remove or hide if not needed for ad-hoc analysis.',
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
        ...ruleMeta('REPORT_VISUAL_BLOAT'),
        title: 'Visual bloat detected on page',
        issue: `Page '${p.display_name}' has ${p.visual_count} visuals, exceeding the limit of 15.`,
        evidence: `Page '${p.display_name}' contains ${p.visual_count} visuals.`,
        impact: 'High visual counts generate concurrent DAX queries that spike page render latency.',
        recommendation: 'Consolidate visuals using multi-row cards or split into drill-through tabs.',
        location: `Page: ${p.display_name}`,
      });
    }
    if (p.slicer_count > 6) {
      findings.push({
        ...ruleMeta('REPORT_SLICER_BLOAT'),
        title: 'Excessive slicers on page',
        issue: `Page '${p.display_name}' has ${p.slicer_count} slicers, exceeding the threshold of 6.`,
        evidence: `Page '${p.display_name}' contains ${p.slicer_count} slicers.`,
        impact: 'Excessive slicers generate redundant query overhead on initial page load.',
        recommendation: 'Use the native Power BI Filter Pane or sync slicers across pages.',
        location: `Page: ${p.display_name}`,
      });
    }
  }

  // Apply pbiscan.suppressions.json from the project root (the shallowest copy)
  const suppressionsFile = validFiles
    .filter((f) => f.name.toLowerCase() === SUPPRESSIONS_FILENAME)
    .sort((a, b) => a.path.split('/').length - b.path.split('/').length)[0];
  if (suppressionsFile) {
    applySuppressions(findings, loadSuppressions(suppressionsFile.content, suppressionsFile.path, warnings));
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
    warnings,
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

/** Returns the model.bim `model.roles` array (raw TMSL) for RLS extraction, or null if the file can't be parsed. */
function parseModelBim(
  content: string,
  tables: TableInfo[],
  relationships: RelationshipInfo[],
  measures: MeasureInfo[],
  calcCols: CalculatedColumnInfo[],
  mSources: { table: string; source: string }[],
  calcGroupEntries: CalcGroupEntry[]
): any[] | null {
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
    return null;
  }
}

function _leadingTabDepth(rawLine: string): number {
  let n = 0;
  while (n < rawLine.length && rawLine[n] === '\t') n++;
  return n;
}

// TMDL name helpers — mirror pbiscan/extraction/tmdl_parser.py.

const TMDL_FENCE = '```';

/** Strip TMDL single quotes from a name, un-escaping doubled quotes ('' -> '). */
export function tmdlUnquote(s: string): string {
  s = s.trim();
  if (s.length >= 2 && s.startsWith("'") && s.endsWith("'")) return s.slice(1, -1).replace(/''/g, "'");
  return s;
}

/** Split `Name = expression` at the first `=` outside a quoted name. */
export function tmdlSplitDeclaration(sig: string): [string, string | null] {
  let inQuote = false;
  for (let i = 0; i < sig.length; i++) {
    const ch = sig[i];
    if (ch === "'") inQuote = !inQuote;
    else if (ch === '=' && !inQuote) return [tmdlUnquote(sig.slice(0, i)), sig.slice(i + 1).trim()];
  }
  return [tmdlUnquote(sig), null];
}

/** Parse 'Table Name'.ColumnName or TableName.ColumnName. */
export function tmdlParseColRef(ref: string): [string, string] {
  const m = /^(?:'((?:[^']|'')*)'|([^.']+))\.(.*)$/s.exec(ref.trim());
  if (!m) return ['', ''];
  const table = m[1] !== undefined ? m[1].replace(/''/g, "'") : m[2];
  return [table, tmdlUnquote(m[3])];
}

/** Remove the ``` delimiters TMDL puts around verbatim multi-line expressions. */
function tmdlStripFence(expr: string): string {
  if (expr.startsWith(TMDL_FENCE)) {
    expr = expr.slice(TMDL_FENCE.length).trimEnd();
    if (expr.endsWith(TMDL_FENCE)) expr = expr.slice(0, -TMDL_FENCE.length);
  }
  return expr.trim();
}

/** If `line` is `keyword` followed by a space or tab, return the rest; else null. */
function tmdlKeyword(line: string, keyword: string): string | null {
  const next = line.charAt(keyword.length);
  return line.startsWith(keyword) && (next === ' ' || next === '\t') ? line.slice(keyword.length + 1).trim() : null;
}

/** Collect the body lines of a measure/calculationItem declared at `depth`:
 * every following line indented deeper, stopping at a blank line or a sibling.
 * A ``` fence is taken verbatim up to its closing ```, blank lines included. */
function tmdlCollectBody(
  lines: string[], start: number, depth: number, inlineExpr: string | null, skip: (l: string) => boolean
): { body: string[]; next: number } {
  const body: string[] = inlineExpr ? [inlineExpr] : [];
  let j = start;
  if (inlineExpr === TMDL_FENCE) {
    while (j < lines.length) {
      const l = lines[j++].trim();
      body.push(l);
      if (l.endsWith(TMDL_FENCE)) break;
    }
  }
  while (j < lines.length && lines[j].trim() !== '' && _leadingTabDepth(lines[j]) > depth) {
    const l = lines[j].trim();
    if (!skip(l)) body.push(l);
    j++;
  }
  return { body, next: j };
}

/** Returns false (and records nothing) when the file has no `table` declaration. */
function parseTableTmdl(
  content: string,
  tables: TableInfo[],
  measures: MeasureInfo[],
  calcCols: CalculatedColumnInfo[],
  mSources: { table: string; source: string }[],
  calcGroupEntries: CalcGroupEntry[]
): boolean {
  const lines = content.split(/\r\n|\r|\n/);
  let currentTable = '';
  let columns: any[] = [];
  const fileMeasures: Omit<MeasureInfo, 'table'>[] = [];
  const fileCalcCols: Omit<CalculatedColumnInfo, 'table'>[] = [];
  let inPartition = false;
  let partitionSource = "";
  let calcItems: CalcItem[] = [];

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();
    const tableSig = tmdlKeyword(line, 'table');
    // `table` is a top-level declaration; an indented one only counts as the first.
    if (tableSig !== null && (!/^[ \t]/.test(rawLine) || !currentTable)) {
      currentTable = tmdlUnquote(tableSig);
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
      const [colName, expr] = tmdlSplitDeclaration(line.substring(7));
      if (expr !== null) {
        fileCalcCols.push({ name: colName, expression: tmdlStripFence(expr), data_type: 'string' });
      } else {
        columns.push({ name: colName, data_type: 'string', is_unique: false, in_relationship: false, hidden: false });
      }
    } else if (line.startsWith('measure ') || line.startsWith('measure\t')) {
      const [measureName, inlineExpr] = tmdlSplitDeclaration(line.substring(8));
      // Only lines MORE indented than the `measure` declaration itself belong to this
      // measure's body/metadata; a sibling `measure`/`column`/`partition` line at the
      // same depth ends it. (A prior version used a bare tab-prefix check, which never
      // stopped at sibling declarations and silently concatenated every subsequent
      // measure's DAX into the current one's expression.)
      const { body } = tmdlCollectBody(
        lines, i + 1, _leadingTabDepth(rawLine), inlineExpr,
        (l) => l.startsWith('lineageTag') || l.startsWith('formatString') || l.startsWith('//'),
      );
      fileMeasures.push({
        name: measureName,
        expression: tmdlStripFence(body.join('\n')) || "BLANK()",
        hidden: false,
      });
    } else if (line.startsWith('calculationItem ') || line.startsWith('calculationItem\t')) {
      const [itemName, inlineExpr] = tmdlSplitDeclaration(line.substring(16));
      const { body: bodyLines } = tmdlCollectBody(
        lines, i + 1, _leadingTabDepth(rawLine), inlineExpr,
        (l) => l.startsWith('lineageTag') || l.startsWith('//'),
      );
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
        name: itemName,
        expression: tmdlStripFence(expression),
        format_string: formatString,
      });
    }
  }

  // No `table` declaration: the file is skipped and reported, like the Python reader.
  if (!currentTable) return false;

  measures.push(...fileMeasures.map((m) => ({ ...m, table: currentTable })));
  calcCols.push(...fileCalcCols.map((c) => ({ ...c, table: currentTable })));
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
    measures_count: fileMeasures.length,
    calc_cols_count: fileCalcCols.length,
  });
  return true;
}

/** Each `relationship <id>` line starts a block; its `key: value` lines follow. */
function parseRelationshipsTmdl(content: string, relationships: RelationshipInfo[]) {
  const blocks: string[][] = [];
  for (const l of content.split(/\r\n|\r|\n/)) {
    const line = l.trim();
    if (tmdlKeyword(line, 'relationship') !== null) blocks.push([]);
    else if (blocks.length) blocks[blocks.length - 1].push(line);
  }
  for (const lines of blocks) {
    let fromTable = "", fromCol = "", toTable = "", toCol = "";
    let bidi = false;

    for (const line of lines) {
      if (line.startsWith('fromColumn:')) {
        [fromTable, fromCol] = tmdlParseColRef(line.substring(11));
      } else if (line.startsWith('toColumn:')) {
        [toTable, toCol] = tmdlParseColRef(line.substring(9));
      } else if (line.includes('crossFilteringBehavior: bothDirections')) {
        bidi = true;
      }
    }

    if (fromTable && fromCol && toTable && toCol) {
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
function processLegacyReportJson(
  files: DroppedFile[], pages: PageInfo[], visualMeasureRefs: Set<string>, unreadFiles: string[]
) {
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

          for (const m of extractMeasureNamesFromExprTree([config, decodeJsonField(vc.filters)])) visualMeasureRefs.add(m);
        }

        // Page-level filters and config are stringified JSON in report.json
        for (const m of extractMeasureNamesFromExprTree([decodeJsonField(s.filters), decodeJsonField(s.config)])) {
          visualMeasureRefs.add(m);
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
      // Non-JSON or malformed report.json — skip, and report it.
      unreadFiles.push(file.path);
    }
  }
}

/** Legacy report.json stores filters/config as JSON strings; decode them (or pass through). */
function decodeJsonField(value: any): any {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }
  return value;
}

/** Flatten `[{entities: [{measures: [{name, expression}]}]}]` into DAX expressions. */
function collectExtensionExpressions(modelExtensions: any): string[] {
  const out: string[] = [];
  if (!Array.isArray(modelExtensions)) return out;
  for (const ext of modelExtensions) {
    for (const entity of (ext && Array.isArray(ext.entities)) ? ext.entities : []) {
      for (const m of (entity && Array.isArray(entity.measures)) ? entity.measures : []) {
        if (m && m.name) out.push(Array.isArray(m.expression) ? m.expression.join('\n') : String(m.expression || ''));
      }
    }
  }
  return out;
}

/** Report-wide references: report-level filters/config (legacy and PBIR report.json),
 * PBIR bookmarks, and model measures used inside report-level ("thin report") measures. */
function processReportLevelReferences(
  reportFiles: DroppedFile[],
  reportLevelFiles: DroppedFile[],
  knownMeasureNames: Set<string>,
  visualMeasureRefs: Set<string>,
  unreadFiles: string[]
) {
  const extensionExpressions: string[] = [];

  for (const file of reportFiles) {
    try {
      const data = JSON.parse(file.content);
      if (Array.isArray(data.sections)) {
        // Legacy report.json: stringified report-level filters + config (with modelExtensions)
        const config = decodeJsonField(data.config);
        for (const m of extractMeasureNamesFromExprTree([decodeJsonField(data.filters), config])) visualMeasureRefs.add(m);
        if (config && typeof config === 'object') extensionExpressions.push(...collectExtensionExpressions(config.modelExtensions));
      } else {
        // PBIR definition/report.json
        for (const m of extractMeasureNamesFromExprTree(data)) visualMeasureRefs.add(m);
      }
    } catch {
      // Malformed report.json — report it once even if the page pass already did.
      if (!unreadFiles.includes(file.path)) unreadFiles.push(file.path);
    }
  }

  for (const file of reportLevelFiles) {
    try {
      const data = JSON.parse(file.content);
      if (file.path.toLowerCase().endsWith('reportextensions.json')) {
        extensionExpressions.push(...collectExtensionExpressions([data]));
      } else {
        for (const m of extractMeasureNamesFromExprTree(data)) visualMeasureRefs.add(m);
      }
    } catch {
      // Malformed bookmark / reportExtensions.json — skip, and report it.
      unreadFiles.push(file.path);
    }
  }

  const measureLookup = new Map([...knownMeasureNames].map((n) => [n.toLowerCase(), n]));
  for (const expr of extensionExpressions) {
    for (const match of expr.matchAll(/\[([^\]]+)\]/g)) {
      const target = measureLookup.get(match[1].trim().toLowerCase());
      if (target) visualMeasureRefs.add(target);
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
  visualMeasureRefs: Set<string>,
  unreadFiles: string[]
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
      // page.json filterConfig (page-level filter pane) and any other bindings
      for (const m of extractMeasureNamesFromExprTree(data)) visualMeasureRefs.add(m);
      const visibility = typeof data.visibility === 'number' ? data.visibility : 0;
      pageMap.set(pageId, {
        displayName: data.displayName || pageId,
        isHidden: visibility !== 0,
        visualCount: 0,
        slicerCount: 0,
      });
    } catch {
      unreadFiles.push(file.path);
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
      // Malformed visual.json — counted above; its measure refs are unknown.
      unreadFiles.push(file.path);
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

// Mirror RULE_CATALOG in pbiscan/rules/catalog.py; the parity test fails if they drift apart.
type RuleMeta = Pick<AuditFinding, 'category' | 'severity' | 'confidence'>;
export const RULE_CATALOG: Record<string, RuleMeta> = {
  MODEL_BIDIRECTIONAL: { category: 'model', severity: 'WARNING', confidence: 100 },
  MODEL_MANY_TO_MANY: { category: 'model', severity: 'WARNING', confidence: 100 },
  MODEL_NO_DATE_TABLE: { category: 'model', severity: 'WARNING', confidence: 70 },
  MODEL_HIGH_CARDINALITY: { category: 'model', severity: 'ADVISORY', confidence: 87 },
  MODEL_FACT_TO_FACT: { category: 'model', severity: 'ADVISORY', confidence: 60 },
  M_HARDCODED_DATA_SOURCE: { category: 'model', severity: 'HIGH', confidence: 95 },
  MODEL_AUTO_DATETIME_BLOAT: { category: 'model', severity: 'MEDIUM', confidence: 100 },
  DAX_SUSPICIOUS_PATTERN: { category: 'dax', severity: 'ADVISORY', confidence: 65 },
  DAX_EXCESSIVE_CALC_COLUMNS: { category: 'dax', severity: 'MEDIUM', confidence: 100 },
  DAX_DUPLICATE_MEASURE: { category: 'dax', severity: 'MEDIUM', confidence: 90 },
  DAX_UNUSED_MEASURE: { category: 'dax', severity: 'ADVISORY', confidence: 95 },
  REPORT_VISUAL_BLOAT: { category: 'report', severity: 'MEDIUM', confidence: 100 },
  REPORT_SLICER_BLOAT: { category: 'report', severity: 'MEDIUM', confidence: 100 },
};

function ruleMeta(ruleId: string): RuleMeta & { rule_id: string } {
  return { rule_id: ruleId, ...RULE_CATALOG[ruleId] };
}

// Mirror DEFAULT_CONFIG in pbiscan/service.py (and rules.config.json);
// tests/unit/test_client_scanner_parity.py fails if they drift apart.
export const SEVERITY_DEDUCTIONS: Record<AuditFinding['severity'], number> = {
  CRITICAL: 15,
  HIGH: 10,
  MEDIUM: 5,
  WARNING: 3,
  ADVISORY: 1,
  LOW: 2,
};
export const CATEGORY_WEIGHTS = { model: 0.35, dax: 0.25, report: 0.2 } as const;

/** Python's round(x, 1): ties go to the even digit. toFixed() rounds ties up.
 * A double can only sit exactly on a tie at .x25 or .x75 — exactly when x * 4
 * (an exact operation) is an odd integer. */
function roundHalfEven1(x: number): number {
  const quarters = x * 4;
  if (Number.isInteger(quarters) && quarters % 2 !== 0) {
    const lower = Math.floor(x * 10);
    return (lower % 2 === 0 ? lower : lower + 1) / 10;
  }
  return Number(x.toFixed(1));
}

/** Same float operations, in the same order, as score_overall() in
 * pbiscan/engine/scoring.py, so both engines produce identical scores. */
export function overallScore(modelScore: number, daxScore: number, reportScore: number): number {
  const w = CATEGORY_WEIGHTS;
  const totalWeight = 0 + w.model + w.dax + w.report;
  const weightedSum =
    0 + modelScore * (w.model / totalWeight) + daxScore * (w.dax / totalWeight) + reportScore * (w.report / totalWeight);
  return roundHalfEven1(weightedSum);
}

function calculateClientScores(findings: AuditFinding[]): ScoreData {
  let modelDeductions = 0;
  let daxDeductions = 0;
  let reportDeductions = 0;

  for (const f of findings) {
    if (f.suppressed) continue;
    const ded = SEVERITY_DEDUCTIONS[f.severity] ?? 5;
    if (f.category === 'model') modelDeductions += ded;
    else if (f.category === 'dax') daxDeductions += ded;
    else if (f.category === 'report') reportDeductions += ded;
  }

  const modelScore = Math.max(0, 100 - modelDeductions);
  const daxScore = Math.max(0, 100 - daxDeductions);
  const reportScore = Math.max(0, 100 - reportDeductions);

  const overall = overallScore(modelScore, daxScore, reportScore);

  return {
    overall,
    category_scores: {
      model: modelScore,
      dax: daxScore,
      report: reportScore,
    },
  };
}
