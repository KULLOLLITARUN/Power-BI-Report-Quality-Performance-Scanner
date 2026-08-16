"""Golden Fixture Contract Test: M_HARDCODED_DATA_SOURCE.

Verifies that hardcoded local developer workstation file paths in M partitions
are detected as quality findings, while cloud data sources and parameterized
connections produce NO findings.
"""

from pathlib import Path
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.model import check_hardcoded_data_sources

FIXTURE_PATH = Path(__file__).parent / "test_m_hardcoded_datasource"


class TestMHardcodedDataSourceContract:
    """Contract verification for hardcoded M data sources."""

    def test_m_hardcoded_datasource_detection_and_controls(self):
        reader = PBIPReader()
        raw = reader.read(FIXTURE_PATH)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        findings = check_hardcoded_data_sources(report)
        findings_by_loc = {f.location: f for f in findings}

        # 1. Positives: Must detect LocalOrders and DownloadsCustomers
        assert "Table: LocalOrders" in findings_by_loc, "Expected finding for LocalOrders (Desktop path)"
        f_orders = findings_by_loc["Table: LocalOrders"]
        assert f_orders.rule_id == "M_HARDCODED_DATA_SOURCE"
        assert "Desktop" in f_orders.evidence
        assert f_orders.severity in ("HIGH", "MEDIUM")

        assert "Table: DownloadsCustomers" in findings_by_loc, "Expected finding for DownloadsCustomers (Downloads path)"
        f_cust = findings_by_loc["Table: DownloadsCustomers"]
        assert f_cust.rule_id == "M_HARDCODED_DATA_SOURCE"
        assert "Downloads" in f_cust.evidence

        # 2. Negatives: Cloud and Parameterized sources must NOT be flagged
        assert "Table: CloudSales" not in findings_by_loc, "SharePoint cloud URL must NOT be flagged"
        assert "Table: SqlDatabase" not in findings_by_loc, "Parameterized SQL database must NOT be flagged"

        # 3. Exact count check
        assert len(findings) == 2, f"Expected exactly 2 findings, got {len(findings)}: {[f.location for f in findings]}"
