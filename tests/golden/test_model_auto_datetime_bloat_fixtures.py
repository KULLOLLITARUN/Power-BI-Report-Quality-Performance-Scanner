"""Golden Fixture Contract Test: MODEL_AUTO_DATETIME_BLOAT.

Verifies that hidden auto-generated LocalDateTable_* tables created by Power BI's
Auto Date/Time feature are detected as model quality findings, while clean models
with explicit date tables produce NO findings.
"""

from pathlib import Path
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.model import check_auto_datetime_bloat

FIXTURE_PATH = Path(__file__).parent / "test_model_auto_datetime_bloat"
CLEAN_FIXTURE_PATH = Path(__file__).parent / "test_enterprise_stress"


class TestModelAutoDateTimeBloatContract:
    """Contract verification for Auto Date/Time bloat detection."""

    def test_detects_auto_datetime_tables(self):
        reader = PBIPReader()
        raw = reader.read(FIXTURE_PATH)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        findings = check_auto_datetime_bloat(report)
        assert len(findings) == 1

        f = findings[0]
        assert f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"
        assert f.severity == "MEDIUM"
        assert f.confidence == 100
        assert "2 auto-generated" in f.evidence
        assert "LocalDateTable_12345678" in f.evidence

    def test_clean_model_without_auto_datetime_produces_no_finding(self):
        reader = PBIPReader()
        raw = reader.read(CLEAN_FIXTURE_PATH)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        findings = check_auto_datetime_bloat(report)
        assert findings == []
