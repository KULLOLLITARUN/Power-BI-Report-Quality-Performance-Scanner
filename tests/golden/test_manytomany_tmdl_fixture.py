"""Golden fixture contract test: many-to-many cardinality is read from TMDL relationships.

relationships.tmdl declares two relationships:

- Orders.ProductID -> Returns.ProductID with fromCardinality/toCardinality many (true positive)
- Orders.CustomerID -> Customers.CustomerID with the TMDL defaults, many to one (control)

The Studio TypeScript port used to treat every TMDL relationship as many-to-one, so it missed the first.
tests/unit/test_client_scanner_parity.py diffs both engines over this fixture.
"""
from pathlib import Path

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_manytomany_tmdl"


def test_only_the_declared_many_to_many_relationship_is_flagged():
    result = ScanService.execute_scan(FIXTURE)
    flagged = [i.location for i in result.issues if i.rule_id == "MODEL_MANY_TO_MANY"]
    assert len(flagged) == 1
    assert "Orders" in flagged[0] and "Returns" in flagged[0]
