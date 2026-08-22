"""Unit tests — model rules M001–M005."""
from __future__ import annotations
from pbiscan.canonical.model import (
    CanonicalReport, Column, DaxDictionary, Measure,
    ModelGraph, Relationship, ReportDOM, Table,
)
from pbiscan.rules.model import (
    check_bidirectional, check_many_to_many, check_no_date_table,
    check_high_cardinality, check_fact_to_fact, check_hardcoded_data_sources,
    check_auto_datetime_bloat, MODEL_RULES,
)


def _make_report(**kwargs) -> CanonicalReport:
    """Helper: build a minimal CanonicalReport with given model parts."""
    return CanonicalReport(
        model=ModelGraph(
            tables=kwargs.get("tables", []),
            relationships=kwargs.get("relationships", []),
        ),
        dax=DaxDictionary(measures=kwargs.get("measures", [])),
        report=ReportDOM(pages=kwargs.get("pages", [])),
    )


def _rel(from_t, from_c, to_t, to_c, **kw) -> Relationship:
    return Relationship(from_table=from_t, from_column=from_c,
                        to_table=to_t, to_column=to_c, **kw)


def _table(name, cols=None, is_date=False, measures=None) -> Table:
    return Table(name=name, columns=cols or [], is_date_table=is_date)


# ---------------------------------------------------------------------------
# M001
# ---------------------------------------------------------------------------
class TestCheckBidirectional:
    def test_detects_both_direction(self):
        r = _make_report(relationships=[
            _rel("Sales", "CID", "Customer", "CID", cross_filter_direction="both")
        ])
        findings = check_bidirectional(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_BIDIRECTIONAL"
        assert findings[0].confidence == 100

    def test_no_finding_for_single(self):
        r = _make_report(relationships=[
            _rel("Sales", "CID", "Customer", "CID", cross_filter_direction="single")
        ])
        assert check_bidirectional(r) == []

    def test_empty_model(self):
        assert check_bidirectional(_make_report()) == []

    def test_multiple_bidir(self):
        r = _make_report(relationships=[
            _rel("A", "ID", "B", "ID", cross_filter_direction="both"),
            _rel("C", "ID", "D", "ID", cross_filter_direction="both"),
        ])
        assert len(check_bidirectional(r)) == 2

    def test_location_is_set(self):
        r = _make_report(relationships=[
            _rel("Sales", "CID", "Customer", "CID", cross_filter_direction="both")
        ])
        f = check_bidirectional(r)[0]
        assert "Sales" in f.location
        assert "Customer" in f.location


# ---------------------------------------------------------------------------
# M002
# ---------------------------------------------------------------------------
class TestCheckManyToMany:
    def test_detects_many_to_many(self):
        r = _make_report(relationships=[
            _rel("Sales", "PID", "Product", "PID", cardinality="manyToMany")
        ])
        findings = check_many_to_many(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_MANY_TO_MANY"

    def test_no_finding_for_one_to_many(self):
        r = _make_report(relationships=[
            _rel("Sales", "CID", "Customer", "CID", cardinality="oneToMany")
        ])
        assert check_many_to_many(r) == []

    def test_empty(self):
        assert check_many_to_many(_make_report()) == []


# ---------------------------------------------------------------------------
# M003
# ---------------------------------------------------------------------------
class TestCheckNoDateTable:
    def test_no_tables_returns_nothing(self):
        assert check_no_date_table(_make_report()) == []

    def test_fires_when_no_date_table(self):
        r = _make_report(tables=[
            _table("Sales"), _table("Customer"),
        ])
        findings = check_no_date_table(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_NO_DATE_TABLE"
        assert findings[0].confidence == 70

    def test_no_finding_when_marked_date_table(self):
        r = _make_report(tables=[
            _table("Sales"), _table("DimDate", is_date=True),
        ])
        assert check_no_date_table(r) == []

    def test_no_finding_when_date_in_name(self):
        r = _make_report(tables=[_table("Sales"), _table("DateDimension")])
        assert check_no_date_table(r) == []

    def test_no_finding_for_calendar_name(self):
        r = _make_report(tables=[_table("Sales"), _table("Calendar")])
        assert check_no_date_table(r) == []


# ---------------------------------------------------------------------------
# M004
# ---------------------------------------------------------------------------
class TestCheckHighCardinality:
    def test_detects_unique_string_not_in_rel(self):
        col = Column(
            name="TransactionCode", table="Sales",
            data_type="string", is_unique=True, in_relationship=False
        )
        r = _make_report(tables=[Table(name="Sales", columns=[col])])
        findings = check_high_cardinality(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_HIGH_CARDINALITY"
        assert findings[0].confidence == 87

    def test_no_finding_when_in_relationship(self):
        col = Column(
            name="CustomerCode", table="Sales",
            data_type="string", is_unique=True, in_relationship=True
        )
        r = _make_report(tables=[Table(name="Sales", columns=[col])])
        assert check_high_cardinality(r) == []

    def test_no_finding_for_int_column(self):
        col = Column(
            name="TransactionID", table="Sales",
            data_type="int64", is_unique=True, in_relationship=False
        )
        r = _make_report(tables=[Table(name="Sales", columns=[col])])
        assert check_high_cardinality(r) == []

    def test_no_finding_when_not_unique(self):
        col = Column(
            name="TransactionCode", table="Sales",
            data_type="string", is_unique=False, in_relationship=False
        )
        r = _make_report(tables=[Table(name="Sales", columns=[col])])
        assert check_high_cardinality(r) == []


# ---------------------------------------------------------------------------
# M005
# ---------------------------------------------------------------------------
class TestCheckFactToFact:
    def test_detects_fact_to_fact(self):
        measures = [
            Measure(name="Total Orders", table="Orders", expression="SUM(Orders[Amount])"),
            Measure(name="Total Returns", table="Returns", expression="SUM(Returns[Amount])"),
        ]
        r = _make_report(
            tables=[_table("Orders"), _table("Returns")],
            relationships=[_rel("Orders", "PID", "Returns", "PID")],
            measures=measures,
        )
        findings = check_fact_to_fact(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_FACT_TO_FACT"
        assert findings[0].confidence == 60

    def test_no_finding_when_one_is_dim(self):
        measures = [
            Measure(name="Total Orders", table="Orders", expression="SUM(Orders[Amount])"),
        ]
        r = _make_report(
            tables=[_table("Orders"), _table("DimProduct")],
            relationships=[_rel("Orders", "PID", "DimProduct", "PID")],
            measures=measures,
        )
        assert check_fact_to_fact(r) == []

    def test_no_finding_without_measures_in_both(self):
        r = _make_report(
            tables=[_table("Sales"), _table("Customer")],
            relationships=[_rel("Sales", "CID", "Customer", "CID")],
            measures=[Measure(name="Total", table="Sales", expression="SUM(Sales[Amount])")],
        )
        # Customer has no measures, should not fire
        assert check_fact_to_fact(r) == []


# ---------------------------------------------------------------------------
# M006 — TestCheckHardcodedDataSources
# ---------------------------------------------------------------------------
class TestCheckHardcodedDataSources:
    def test_detects_local_windows_desktop_path(self):
        r = _make_report(
            tables=[
                Table(
                    name="Orders",
                    columns=[Column(name="ID", table="Orders")],
                    partition_source='File.Contents("C:\\Users\\User\\Desktop\\Orders.xlsx")',
                )
            ]
        )
        findings = check_hardcoded_data_sources(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "M_HARDCODED_DATA_SOURCE"
        assert findings[0].location == "Table: Orders"
        assert "Desktop" in findings[0].evidence

    def test_detects_downloads_folder_path(self):
        r = _make_report(
            tables=[
                Table(
                    name="Customers",
                    columns=[Column(name="ID", table="Customers")],
                    partition_source='Csv.Document(File.Contents("C:/Users/Dev/Downloads/Data.csv"))',
                )
            ]
        )
        findings = check_hardcoded_data_sources(r)
        assert len(findings) == 1
        assert "Downloads" in findings[0].evidence

    def test_no_finding_for_cloud_and_database_sources(self):
        r = _make_report(
            tables=[
                Table(
                    name="SharePointFiles",
                    columns=[Column(name="ID", table="SharePointFiles")],
                    partition_source='SharePoint.Files("https://company.sharepoint.com/sites/bi")',
                ),
                Table(
                    name="SqlDb",
                    columns=[Column(name="ID", table="SqlDb")],
                    partition_source='Sql.Database(#"ServerName", #"DbName")',
                ),
            ]
        )
        findings = check_hardcoded_data_sources(r)
        assert findings == []


# ---------------------------------------------------------------------------
# M007 — TestCheckAutoDateTimeBloat
# ---------------------------------------------------------------------------
class TestCheckAutoDateTimeBloat:
    def test_detects_local_date_tables(self):
        r = _make_report(
            tables=[
                Table(name="Sales"),
                Table(name="LocalDateTable_1111"),
                Table(name="LocalDateTable_2222"),
                Table(name="DateTableTemplate_9999"),
            ]
        )
        findings = check_auto_datetime_bloat(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "MODEL_AUTO_DATETIME_BLOAT"
        assert "2 auto-generated" in findings[0].evidence
        assert "LocalDateTable_1111" in findings[0].evidence

    def test_no_finding_for_clean_model(self):
        r = _make_report(
            tables=[
                Table(name="Sales"),
                Table(name="Calendar", is_date_table=True),
            ]
        )
        findings = check_auto_datetime_bloat(r)
        assert findings == []


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------
def test_model_rules_registry():
    assert len(MODEL_RULES) == 7
    assert check_hardcoded_data_sources in MODEL_RULES
    assert check_auto_datetime_bloat in MODEL_RULES
