import { ScanResult, AuditFinding, TableInfo, RelationshipInfo, MeasureInfo, CalculatedColumnInfo, PageInfo, ScoreData } from '../types';

export interface DroppedFile {
  name: string;
  path: string;
  content: string;
}

export function parseDroppedPbip(files: DroppedFile[], projectName: string = "uploaded_report.pbip"): ScanResult {
  const tables: TableInfo[] = [];
  const relationships: RelationshipInfo[] = [];
  const measures: MeasureInfo[] = [];
  const calcCols: CalculatedColumnInfo[] = [];
  const pages: PageInfo[] = [];
  const visualReferences = new Set<string>();
  const mSources: { table: string; source: string }[] = [];

  // Filter out backup folders, git, and metadata
  const validFiles = files.filter(f => {
    const p = f.path.toLowerCase().replace(/\\/g, '/');
    return !p.includes('/backup/') && !p.startsWith('backup/') && !p.includes('/.git/') && !p.includes('/.pbi/');
  });

  // Check for model.bim or database.json
  const bimFile = validFiles.find(f => f.name.toLowerCase() === 'model.bim' || f.name.toLowerCase() === 'database.json');
  if (bimFile) {
    parseModelBim(bimFile.content, tables, relationships, measures, calcCols, mSources);
  }

  // 1. Process TMDL files
  for (const file of validFiles) {
    const lowerPath = file.path.toLowerCase().replace(/\\/g, '/');
    
    // Table TMDL
    if (lowerPath.endsWith('.tmdl') && (lowerPath.includes('/tables/') || lowerPath.includes('table '))) {
      parseTableTmdl(file.content, tables, measures, calcCols, mSources);
    }
    
    // Relationships TMDL
    if (lowerPath.endsWith('relationships.tmdl') || (lowerPath.endsWith('.tmdl') && file.content.includes('relationship '))) {
      parseRelationshipsTmdl(file.content, relationships);
    }

    // Report JSON / PBIR
    if (lowerPath.endsWith('report.json') || lowerPath.endsWith('definition.pbir') || lowerPath.includes('page.json') || lowerPath.includes('visual.json')) {
      parseReportArtifact(file.name, file.content, pages, visualReferences);
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

  // D004: Unused Measures
  for (const m of measures) {
    const nameRef = `[${m.name}]`;
    const isReferencedInOtherMeasures = measures.some((other) => other.name !== m.name && other.expression.includes(nameRef));
    const isReferencedInVisuals = visualReferences.has(m.name) || Array.from(visualReferences).some(vr => vr.includes(m.name));

    if (!isReferencedInOtherMeasures && !isReferencedInVisuals) {
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

  // R001 & R002: Visual & Slicer Bloat
  for (const p of pages) {
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

function parseModelBim(
  content: string,
  tables: TableInfo[],
  relationships: RelationshipInfo[],
  measures: MeasureInfo[],
  calcCols: CalculatedColumnInfo[],
  mSources: { table: string; source: string }[]
) {
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
  } catch (e) {
    console.error("Failed to parse model.bim JSON:", e);
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
  mSources: { table: string; source: string }[]
) {
  const lines = content.split('\n');
  let currentTable = "UnknownTable";
  let columns: any[] = [];
  let tableMeasures = 0;
  let tableCalcCols = 0;
  let inPartition = false;
  let partitionSource = "";

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
    }
  }

  if (partitionSource) {
    mSources.push({ table: currentTable, source: partitionSource });
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

function parseReportArtifact(name: string, content: string, pages: PageInfo[], visualReferences: Set<string>) {
  try {
    const data = JSON.parse(content);
    if (data.sections && Array.isArray(data.sections)) {
      // Deduplicate pages by section name
      const existingNames = new Set(pages.map(p => p.name));
      for (const s of data.sections) {
        if (existingNames.has(s.name)) continue;
        existingNames.add(s.name);

        const visualCount = s.visualContainers?.length || 0;
        let slicerCount = 0;
        if (s.visualContainers) {
          for (const vc of s.visualContainers) {
            const configStr = vc.config || "";
            if (configStr.includes('"slicer"') || configStr.includes('slicer')) slicerCount++;
            const match = configStr.match(/\[([^\]]+)\]/g);
            if (match) {
              match.forEach((m: string) => visualReferences.add(m.replace(/[\[\]]/g, '')));
            }
          }
        }
        pages.push({
          name: s.name || `Section_${pages.length + 1}`,
          display_name: s.displayName || `Page ${pages.length + 1}`,
          is_hidden: !s.ordinal && s.ordinal !== 0 ? false : s.isHidden || false,
          visual_count: visualCount,
          slicer_count: slicerCount,
        });
      }
    }
  } catch (e) {
    // Non-JSON or simple PBIR fragment
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
