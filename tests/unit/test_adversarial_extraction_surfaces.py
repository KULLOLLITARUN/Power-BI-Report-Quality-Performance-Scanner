"""Adversarial negative coverage contract tests for all PBIR and DAX extraction surfaces.

Validates that when measures are referenced ONLY through specific subtle PBIR visual
surfaces or multi-hop DAX dependencies, PBIP Sentinel correctly identifies them as active
and NEVER emits a false-positive DAX_UNUSED_MEASURE finding.
"""

import json

from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.rules.dax import check_unused_measures


class TestAdversarialExtractionSurfaces:
    """Deliberate negative-coverage tests for all 10 visual extraction surfaces."""

    def test_all_ten_visual_extraction_surfaces(self, tmp_path):
        """Construct a PBIR visual referencing 10 separate measures exclusively across 10 distinct AST surfaces."""
        visual_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.2.0/schema.json",
            "name": "adversarial_visual",
            "visual": {
                "visualType": "card",
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [
                                {
                                    "queryRef": "TotalBaseSales",
                                    "field": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "TotalBaseSales"
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "prototypeQuery": {
                        "OrderBy": [
                            {
                                "Expression": {
                                    "Measure": {
                                        "Expression": {"SourceRef": {"Entity": "Sales"}},
                                        "Property": "OrderByMeasure"
                                    }
                                }
                            }
                        ]
                    }
                },
                "objects": {
                    "referenceLabel": [
                        {
                            "properties": {
                                "value": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "RefLabelMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "referenceLabelDetail": [
                        {
                            "properties": {
                                "detailValue": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "RefDetailMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "title": [
                        {
                            "properties": {
                                "text": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "DynamicTitleMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "subTitle": [
                        {
                            "properties": {
                                "text": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "DynamicSubTitleMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "dataPoint": [
                        {
                            "properties": {
                                "fill": {
                                    "solid": {
                                        "color": {
                                            "expr": {
                                                "Measure": {
                                                    "Expression": {"SourceRef": {"Entity": "Sales"}},
                                                    "Property": "ColorFormatMeasure"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "valueAxis": [
                        {
                            "properties": {
                                "max": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "AxisMaxMeasure"
                                        }
                                    }
                                },
                                "min": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "AxisMinMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "visualHeaderTooltip": [
                        {
                            "properties": {
                                "text": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "HeaderTooltipMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ]
                },
                "visualContainerObjects": {
                    "general": [
                        {
                            "properties": {
                                "altText": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "AltTextMeasure"
                                        }
                                    }
                                }
                            }
                        }
                    ]
                },
                "filters": [
                    {
                        "expression": {
                            "Measure": {
                                "Expression": {"SourceRef": {"Entity": "Sales"}},
                                "Property": "VisualFilterMeasure"
                            }
                        }
                    }
                ]
            }
        }

        # Build PBIP structure
        proj_dir = tmp_path / "AdversarialTest"
        proj_dir.mkdir()
        (proj_dir / "AdversarialTest.pbip").write_text('{"version": "1.0"}', encoding="utf-8")

        report_dir = proj_dir / "AdversarialTest.Report"
        def_dir = report_dir / "definition"
        pages_dir = def_dir / "pages" / "Page1" / "visuals" / "v1"
        pages_dir.mkdir(parents=True)
        (def_dir / "report.json").write_text('{"$schema": "report.json", "name": "AdvReport"}', encoding="utf-8")
        (report_dir / "definition.pbir").write_text('{"version": "4.0", "datasetReference": {"byPath": {"path": "../AdversarialTest.SemanticModel"}}}', encoding="utf-8")
        (def_dir / "pages" / "Page1" / "page.json").write_text('{"name": "Page1", "displayName": "Page 1"}', encoding="utf-8")
        (pages_dir / "visual.json").write_text(json.dumps(visual_json), encoding="utf-8")

        # Build Semantic Model with 11 measures (10 surface-bound + 1 multi-hop + 1 deliberately unused)
        sm_dir = proj_dir / "AdversarialTest.SemanticModel"
        tmdl_dir = sm_dir / "definition" / "tables"
        tmdl_dir.mkdir(parents=True)
        (sm_dir / "definition.pbism").write_text('{"version": "4.0"}', encoding="utf-8")
        (sm_dir / "definition" / "model.tmdl").write_text("model Model\n\tref table Sales\n", encoding="utf-8")

        sales_tmdl = """table Sales
\tcolumn Amount = 100
\t\tdataType: int64

\tmeasure TotalBaseSales = SUM(Sales[Amount])
\tmeasure OrderByMeasure = [TotalBaseSales] * 1
\tmeasure RefLabelMeasure = [TotalBaseSales] * 2
\tmeasure RefDetailMeasure = [TotalBaseSales] * 3
\tmeasure DynamicTitleMeasure = "Sales: " & [MultiHopMeasure]
\tmeasure MultiHopMeasure = [TotalBaseSales] * 4
\tmeasure DynamicSubTitleMeasure = "Sub"
\tmeasure ColorFormatMeasure = IF([TotalBaseSales] > 0, "Green", "Red")
\tmeasure AxisMaxMeasure = 1000
\tmeasure AxisMinMeasure = 0
\tmeasure HeaderTooltipMeasure = "Help text"
\tmeasure AltTextMeasure = "Alt text"
\tmeasure VisualFilterMeasure = [TotalBaseSales] > 50

\tmeasure DeliberatelyUnusedKPI = 9999
"""
        (tmdl_dir / "Sales.tmdl").write_text(sales_tmdl, encoding="utf-8")

        reader = PBIPReader()
        raw = reader.read(proj_dir)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        unused_findings = check_unused_measures(report)

        # Expected result: Exactly 1 unused measure ('DeliberatelyUnusedKPI')
        # All 12 other measures (including MultiHopMeasure) must be recognized as ACTIVE.
        assert len(unused_findings) == 1, (
            f"Expected exactly 1 unused measure, but got {len(unused_findings)}: {[f.location for f in unused_findings]}"
        )
        assert unused_findings[0].location == "Measure: DeliberatelyUnusedKPI"
