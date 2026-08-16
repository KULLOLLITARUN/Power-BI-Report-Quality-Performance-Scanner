"""Phase 3G Adversarial & Security Hardening Test Suite for Semantic Reference Extractors."""

import pytest
from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex
from pbiscan.extraction.calc_group_extractor import extract_calc_group_references
from pbiscan.extraction.field_param_extractor import extract_field_param_references
from pbiscan.extraction.rls_extractor import extract_rls_tmdl_references, extract_rls_bim_references


class TestAdversarialHardening:
    """Stress testing extractors against malformed, adversarial, and edge-case inputs."""

    # 1. Field Parameter Malformed Inputs
    def test_field_param_empty_and_garbage_expressions(self):
        assert extract_field_param_references("ParamTable", "") == []
        assert extract_field_param_references("ParamTable", "NOT A NAMEOF EXPRESSION") == []
        assert extract_field_param_references("ParamTable", "NAMEOF()") == []
        assert extract_field_param_references("ParamTable", "NAMEOF('UnclosedTable[Col])") == []
        assert extract_field_param_references("ParamTable", "NAMEOF(TableNoBrackets)") == []

    def test_field_param_unicode_and_special_characters(self):
        expr = """
        {
            ("Chiffre d'affaires", NAMEOF('Ventes €'[Montant Total]), 0),
            ("日本語メジャー", NAMEOF('売上'[総売上]), 1)
        }
        """
        refs = extract_field_param_references(
            "UnicodeParams",
            expr,
            known_measure_names={"Montant Total", "総売上"},
        )
        assert len(refs) == 2
        assert refs[0].target_name == "Montant Total"
        assert refs[0].target_table == "Ventes €"
        assert refs[0].activates_root is True
        assert refs[1].target_name == "総売上"
        assert refs[1].target_table == "売上"

    # 2. Calculation Group Malformed Inputs
    def test_calc_group_malformed_and_empty_items(self):
        # Empty list
        assert extract_calc_group_references("EmptyCalcGroup", []) == []
        # Missing fields in dict
        calc_items = [
            {},
            {"name": None, "expression": None},
            {"name": "BadItem", "expression": 12345},  # Non-string expression
            {"name": "GarbageDAX", "expression": "CALCULATE( [UnclosedBracket "},
        ]
        # Should gracefully handle without crashing
        refs = extract_calc_group_references("FaultyGroup", calc_items)
        assert isinstance(refs, list)

    def test_calc_group_duplicate_bracket_tokens_in_same_expression(self):
        calc_items = [
            {
                "name": "MultiRef",
                "expression": "[MeasureA] + [MeasureA] * [MeasureB] - [MeasureA]",
            }
        ]
        refs = extract_calc_group_references("CalcGroup", calc_items)
        assert len(refs) == 4
        # All 4 occurrences captured with provenance
        target_names = [r.target_name for r in refs]
        assert target_names.count("MeasureA") == 3
        assert target_names.count("MeasureB") == 1

    # 3. RLS Role Malformed Inputs
    def test_rls_malformed_tmdl_and_garbage(self):
        assert extract_rls_tmdl_references("RoleA", "") == []
        assert extract_rls_tmdl_references("RoleA", "role RoleA\n\tmodelPermission: read\n") == []
        
        # Corrupted tablePermission line
        corrupted_tmdl = """role CorruptedRole
	tablePermission = [MissingTable]
	tablePermission BadTable
	tablePermission TableNoEquals [SomeMeasure]
"""
        refs = extract_rls_tmdl_references("CorruptedRole", corrupted_tmdl)
        assert isinstance(refs, list)

    def test_rls_malformed_bim_roles(self):
        assert extract_rls_bim_references([]) == []
        # Malformed dictionaries in roles array
        bim_roles = [
            {},
            {"name": "Role1"},
            {"name": "Role2", "tablePermissions": None},
            {"name": "Role3", "tablePermissions": [{}]},
            {"name": "Role4", "tablePermissions": [{"name": "Sales", "filterExpression": None}]},
        ]
        refs = extract_rls_bim_references(bim_roles)
        assert refs == []

    # 4. SemanticReferenceIndex Case & Duplication Hardening
    def test_semantic_reference_index_mixed_case_deduplication(self):
        index = SemanticReferenceIndex()
        index.add(SemanticReference(target_name="TotalSales", target_type="measure", activates_root=True))
        index.add(SemanticReference(target_name="totalsales", target_type="measure", activates_root=True))
        index.add(SemanticReference(target_name="TOTALSALES", target_type="measure", activates_root=True))

        roots = index.active_root_measure_names()
        assert len(roots) >= 1
        # Lookup is strictly case-insensitive
        assert len(index.find_by_target("TotalSales")) == 3
        assert len(index.find_by_target("totalsales")) == 3
        assert len(index.find_by_target("TOTALSALES")) == 3
