// Semantic Reference Index — TypeScript port of pbiscan.canonical.references +
// pbiscan.extraction.{calc_group_extractor, field_param_extractor, rls_extractor}.
//
// Ports the server-side "Unified Semantic Reference Index" so the in-browser
// Studio Workbench can resolve the same measure-usage surfaces the Python engine
// does: Calculation Group calculationItem DAX (including SELECTEDMEASURE()
// building-block references and ISSELECTEDMEASURE()/SELECTEDMEASURENAME()
// predicates), Field Parameter NAMEOF() bindings, and Row-Level Security
// tablePermission filter expressions. Regex patterns are copied verbatim from
// the Python source so behavior matches exactly.

export type ReferenceSourceType =
  | 'visual_projection'
  | 'visual_filter'
  | 'visual_property'
  | 'calc_item_dax'
  | 'calc_item_predicate'
  | 'field_parameter'
  | 'field_parameter_grouped'
  | 'rls_table_permission';

export type ReferenceTargetType = 'measure' | 'column' | 'table' | 'unresolved';

export interface SemanticReference {
  target_name: string;
  target_table?: string;
  target_type: ReferenceTargetType;
  source_type: ReferenceSourceType;
  source_object: string;
  source_file: string;
  source_expression?: string;
  activates_root: boolean;
  confidence: number;
}

export class SemanticReferenceIndex {
  references: SemanticReference[] = [];

  add(ref: SemanticReference): void {
    this.references.push(ref);
  }

  addMany(refs: SemanticReference[]): void {
    this.references.push(...refs);
  }

  activeRootMeasureNames(): Set<string> {
    const roots = new Set<string>();
    for (const ref of this.references) {
      if (ref.activates_root && ref.target_type === 'measure') {
        roots.add(ref.target_name);
      }
    }
    return roots;
  }

  findByTarget(targetName: string): SemanticReference[] {
    const lower = targetName.toLowerCase();
    return this.references.filter((r) => r.target_name.toLowerCase() === lower);
  }
}

// ---------------------------------------------------------------------------
// Calculation Group extractor (mirrors pbiscan.extraction.calc_group_extractor)
// ---------------------------------------------------------------------------

const BRACKET_REF_PATTERN = /(?:'([^']+)'|\b([a-zA-Z_][a-zA-Z0-9_]*))?\[([^\]]+)\]/gi;
const ISSELECTEDMEASURE_PATTERN = /\bISSELECTEDMEASURE\s*\(\s*(?:'([^']+)'\s*|([a-zA-Z_][a-zA-Z0-9_]*)\s*)?\[([^\]]+)\]/gi;
const SELECTEDMEASURENAME_PATTERN = /\bSELECTEDMEASURENAME\s*\(\s*\)\s*(?:==?|=)\s*"([^"]+)"/gi;

const IGNORED_BRACKET_NAMES = new Set([
  'name', 'value', 'value1', 'value2', 'value3', 'value4', 'ordinal',
  'selectedmeasure', 'selectedmeasureformatstring',
]);

export interface CalcItem {
  name: string;
  expression: string;
  format_string?: string;
}

export function extractCalcGroupReferences(
  tableName: string,
  calcItems: CalcItem[],
  sourceFile: string = ''
): SemanticReference[] {
  const references: SemanticReference[] = [];

  for (const item of calcItems) {
    const itemName = item.name || 'UnknownItem';
    const itemDax = item.expression || '';
    const formatDax = item.format_string || '';
    const sourceObj = `${tableName}['${itemName}']`;

    // 1. ISSELECTEDMEASURE([Measure]) predicates
    for (const match of itemDax.matchAll(ISSELECTEDMEASURE_PATTERN)) {
      const [, tblQuoted, tblUnquoted, measName] = match;
      const targetTbl = tblQuoted || tblUnquoted;
      if (!IGNORED_BRACKET_NAMES.has(measName.trim().toLowerCase())) {
        references.push({
          target_name: measName.trim(),
          target_table: targetTbl,
          target_type: 'measure',
          source_type: 'calc_item_predicate',
          source_object: sourceObj,
          source_file: sourceFile,
          source_expression: match[0],
          activates_root: true,
          confidence: 100,
        });
      }
    }

    // 2. SELECTEDMEASURENAME() == "MeasureName" predicates
    for (const match of itemDax.matchAll(SELECTEDMEASURENAME_PATTERN)) {
      const measName = match[1].trim();
      if (!IGNORED_BRACKET_NAMES.has(measName.toLowerCase())) {
        references.push({
          target_name: measName,
          target_type: 'measure',
          source_type: 'calc_item_predicate',
          source_object: sourceObj,
          source_file: sourceFile,
          source_expression: match[0],
          activates_root: true,
          confidence: 100,
        });
      }
    }

    // 3. Explicit bracket references from calculation item DAX (skip ones already
    // captured by ISSELECTEDMEASURE above)
    for (const match of itemDax.matchAll(BRACKET_REF_PATTERN)) {
      const [, tblQuoted, tblUnquoted, propName] = match;
      const propClean = propName.trim();
      if (IGNORED_BRACKET_NAMES.has(propClean.toLowerCase())) continue;

      const prefix = itemDax.slice(Math.max(0, match.index! - 25), match.index!);
      if (prefix.toUpperCase().includes('ISSELECTEDMEASURE')) continue;

      const targetTbl = tblQuoted || tblUnquoted;
      references.push({
        target_name: propClean,
        target_table: targetTbl,
        target_type: 'measure',
        source_type: 'calc_item_dax',
        source_object: sourceObj,
        source_file: sourceFile,
        source_expression: match[0],
        activates_root: true,
        confidence: 100,
      });
    }

    // 4. Bracket references from format string DAX definition
    if (formatDax) {
      for (const match of formatDax.matchAll(BRACKET_REF_PATTERN)) {
        const [, tblQuoted, tblUnquoted, propName] = match;
        const propClean = propName.trim();
        if (IGNORED_BRACKET_NAMES.has(propClean.toLowerCase())) continue;

        const targetTbl = tblQuoted || tblUnquoted;
        references.push({
          target_name: propClean,
          target_table: targetTbl,
          target_type: 'measure',
          source_type: 'calc_item_dax',
          source_object: `${sourceObj}.formatStringDefinition`,
          source_file: sourceFile,
          source_expression: match[0],
          activates_root: true,
          confidence: 100,
        });
      }
    }
  }

  return references;
}

// ---------------------------------------------------------------------------
// Field Parameter extractor (mirrors pbiscan.extraction.field_param_extractor)
// ---------------------------------------------------------------------------

const NAMEOF_PATTERN = /\bNAMEOF\s*\(\s*(?:'([^']+)'\s*|([a-zA-Z_][a-zA-Z0-9_]*)\s*)?\[([^\]]+)\]\s*\)/gi;
const GROUPED_TUPLE_PATTERN = /,\s*"[^"]+"\s*\)\s*\}/;

export function extractFieldParamReferences(
  tableName: string,
  partitionExpression: string,
  knownMeasureNames?: Set<string>,
  knownColumnNames?: Set<string>,
  sourceFile: string = ''
): SemanticReference[] {
  if (!partitionExpression || !partitionExpression.toUpperCase().includes('NAMEOF')) {
    return [];
  }

  const measSet = knownMeasureNames ? new Set(Array.from(knownMeasureNames).map((m) => m.toLowerCase())) : new Set<string>();
  const colSet = knownColumnNames ? new Set(Array.from(knownColumnNames).map((c) => c.toLowerCase())) : new Set<string>();

  const isGrouped = GROUPED_TUPLE_PATTERN.test(partitionExpression);
  const sourceType: ReferenceSourceType = isGrouped ? 'field_parameter_grouped' : 'field_parameter';

  const references: SemanticReference[] = [];

  for (const match of partitionExpression.matchAll(NAMEOF_PATTERN)) {
    const [, tblQuoted, tblUnquoted, entityName] = match;
    const targetTbl = tblQuoted || tblUnquoted;
    const entityClean = entityName.trim();
    const entityLower = entityClean.toLowerCase();

    let targetType: ReferenceTargetType;
    let activatesRoot: boolean;
    if (measSet.size && measSet.has(entityLower)) {
      targetType = 'measure';
      activatesRoot = true;
    } else if (colSet.size && colSet.has(entityLower)) {
      targetType = 'column';
      activatesRoot = false;
    } else {
      targetType = 'measure';
      activatesRoot = true;
    }

    references.push({
      target_name: entityClean,
      target_table: targetTbl,
      target_type: targetType,
      source_type: sourceType,
      source_object: tableName,
      source_file: sourceFile,
      source_expression: match[0],
      activates_root: activatesRoot,
      confidence: 100,
    });
  }

  return references;
}

// ---------------------------------------------------------------------------
// RLS extractor (mirrors pbiscan.extraction.rls_extractor)
// ---------------------------------------------------------------------------

const RLS_IGNORED_TOKENS = new Set([
  'userprincipalname', 'userobjectid', 'username', 'customdata',
  'true', 'false', 'blank', 'value',
]);

export function extractRlsTmdlReferences(
  roleName: string,
  tmdlContent: string,
  sourceFile: string = ''
): SemanticReference[] {
  if (!tmdlContent || !tmdlContent.includes('tablePermission')) return [];

  const references: SemanticReference[] = [];
  const permPattern = /tablePermission\s+([^\s=]+)\s*=\s*([\s\S]+?)(?=(?:\n\s*tablePermission|\n\s*role|\n\s*member|$))/g;

  for (const match of tmdlContent.matchAll(permPattern)) {
    const permTable = match[1].trim().replace(/'/g, '');
    const daxExpr = match[2].trim();

    for (const refMatch of daxExpr.matchAll(BRACKET_REF_PATTERN)) {
      const [, tblQuoted, tblUnquoted, entityName] = refMatch;
      const entityClean = entityName.trim();
      if (RLS_IGNORED_TOKENS.has(entityClean.toLowerCase())) continue;

      const targetTbl = tblQuoted || tblUnquoted || permTable;
      references.push({
        target_name: entityClean,
        target_table: targetTbl,
        target_type: 'measure',
        source_type: 'rls_table_permission',
        source_object: `${roleName}.tablePermission['${permTable}']`,
        source_file: sourceFile,
        source_expression: refMatch[0],
        activates_root: true,
        confidence: 100,
      });
    }
  }

  return references;
}

export function extractRlsBimReferences(roles: any[], sourceFile: string = 'model.bim'): SemanticReference[] {
  if (!roles || !roles.length) return [];

  const references: SemanticReference[] = [];

  for (const role of roles) {
    if (!role || typeof role !== 'object') continue;
    const roleName = role.name || 'UnknownRole';
    const tablePerms = Array.isArray(role.tablePermissions) ? role.tablePermissions : [];

    for (const perm of tablePerms) {
      if (!perm || typeof perm !== 'object') continue;
      const permTable = perm.name || 'UnknownTable';
      const daxExpr = perm.filterExpression != null ? String(perm.filterExpression) : '';

      for (const refMatch of daxExpr.matchAll(BRACKET_REF_PATTERN)) {
        const [, tblQuoted, tblUnquoted, entityName] = refMatch;
        const entityClean = entityName.trim();
        if (RLS_IGNORED_TOKENS.has(entityClean.toLowerCase())) continue;

        const targetTbl = tblQuoted || tblUnquoted || permTable;
        references.push({
          target_name: entityClean,
          target_table: targetTbl,
          target_type: 'measure',
          source_type: 'rls_table_permission',
          source_object: `${roleName}.tablePermissions['${permTable}']`,
          source_file: sourceFile,
          source_expression: refMatch[0],
          activates_root: true,
          confidence: 100,
        });
      }
    }
  }

  return references;
}

// ---------------------------------------------------------------------------
// PBIR / legacy report AST measure extraction
// (mirrors PBIPReader._extract_measure_names_from_expr_tree)
// ---------------------------------------------------------------------------

/** Recursively traverse any JSON subtree and extract every `{"Measure": {"Property": ...}}` reference. */
export function extractMeasureNamesFromExprTree(obj: any): Set<string> {
  const refs = new Set<string>();
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    if (obj.Measure && typeof obj.Measure === 'object') {
      const prop = obj.Measure.Property;
      if (prop) refs.add(prop);
    }
    for (const v of Object.values(obj)) {
      for (const r of extractMeasureNamesFromExprTree(v)) refs.add(r);
    }
  } else if (Array.isArray(obj)) {
    for (const item of obj) {
      for (const r of extractMeasureNamesFromExprTree(item)) refs.add(r);
    }
  }
  return refs;
}
