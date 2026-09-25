"""Guardian rule registry: all 16 rules carry owner/version/evidence slots."""
import pytest

from rift.health.guardian import RULE_METADATA, RULE_VERSION, rule_metadata

EXPECTED = [f"G-{i:03d}" for i in range(1, 17)]


def test_all_sixteen_rules_registered():
    assert sorted(RULE_METADATA) == EXPECTED


def test_each_rule_has_owner_version_evidence():
    for rule_id in EXPECTED:
        meta = RULE_METADATA[rule_id]
        assert meta["version"] == RULE_VERSION
        assert meta["stage"] in ("INPUT", "STATE", "MODEL", "COUNTERFACTUAL", "OUTPUT", "DEPLOYMENT")
        assert meta["owner"].startswith("UNASSIGNED")
        assert meta["evidence"]
        assert meta["summary"]


def test_rule_metadata_lookup_fail_closed():
    assert rule_metadata("G-001")["stage"] == "STATE"
    with pytest.raises(KeyError):
        rule_metadata("G-999")


def test_review_metric_exported_and_rendered():
    from rift.health.monitoring import EXPORTED_METRICS, MetricsCollector, render_prometheus
    assert "rift_clinician_reviews_total" in EXPORTED_METRICS
    col = MetricsCollector()
    col.record_review("ACCEPT")
    col.record_review("OVERRIDE")
    col.record_review("nonsense")  # ignored, never invents a bucket
    text = render_prometheus(col.report())
    assert 'rift_clinician_reviews_total{action="accept"} 1' in text
    assert 'rift_clinician_reviews_total{action="override"} 1' in text
    assert "nonsense" not in text
