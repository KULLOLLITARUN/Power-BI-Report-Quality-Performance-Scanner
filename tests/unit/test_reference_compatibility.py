"""Compatibility contract test ensuring models outside v1.4 domains remain invariant."""

from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex


class TestReferenceCompatibilityContract:
    """Contract tests ensuring zero interference on standard models."""

    def test_empty_semantic_index_returns_empty_active_roots(self):
        index = SemanticReferenceIndex()
        assert index.active_root_measure_names() == set()

    def test_non_measure_entities_do_not_inject_spurious_roots(self):
        index = SemanticReferenceIndex()
        index.add(SemanticReference(target_name="Category", target_type="column", activates_root=False))
        index.add(SemanticReference(target_name="DimDate", target_type="table", activates_root=False))

        assert index.active_root_measure_names() == set()

    def test_reference_index_preserves_case_exactness(self):
        index = SemanticReferenceIndex()
        index.add(SemanticReference(target_name="TotalRevenue", target_type="measure", activates_root=True))
        assert "TotalRevenue" in index.active_root_measure_names()
