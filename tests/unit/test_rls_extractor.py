"""Unit tests for isolated Row-Level Security (RLS) semantic reference extractor."""

from pbiscan.extraction.rls_extractor import extract_rls_tmdl_references, extract_rls_bim_references


class TestRlsExtractor:
    """Test suite for RLS role reference extractors."""

    def test_extracts_tmdl_table_permission_measures(self):
        tmdl_content = """role RegionalManagerRole
	modelPermission: read

	tablePermission Sales = [IsUserAuthorizedRegion] == 1 || [TotalSales] > 0

	tablePermission DimCustomer = [Segment] == "Enterprise"
"""
        refs = extract_rls_tmdl_references("RegionalManagerRole", tmdl_content, "roles/RegionalManagerRole.tmdl")
        assert len(refs) == 3
        target_names = {r.target_name for r in refs}
        assert "IsUserAuthorizedRegion" in target_names
        assert "TotalSales" in target_names
        assert "Segment" in target_names
        assert all(r.source_type == "rls_table_permission" for r in refs)
        assert all(r.activates_root is True for r in refs)

    def test_extracts_bim_role_table_permission_measures(self):
        roles = [
            {
                "name": "ComplianceOfficerRole",
                "tablePermissions": [
                    {
                        "name": "Sales",
                        "filterExpression": "[ComplianceFlagMeasure] == 1",
                    }
                ],
            }
        ]
        refs = extract_rls_bim_references(roles)
        assert len(refs) == 1
        assert refs[0].target_name == "ComplianceFlagMeasure"
        assert refs[0].source_type == "rls_table_permission"
        assert refs[0].activates_root is True

    def test_ignores_userprincipalname_and_system_tokens(self):
        tmdl_content = """role AdminRole
	tablePermission Sales = USERPRINCIPALNAME() = "admin@co.com" && TRUE()
"""
        refs = extract_rls_tmdl_references("AdminRole", tmdl_content)
        assert len(refs) == 0  # No measures, only system functions
