"""Power-grid emergency domain: registration, physics sanity, integration."""
import pytest

from rift.domains.powergrid.domain import (
    DOMAIN_ID,
    DOMAIN_METADATA,
    POWERGRID_PERTURBATIONS,
    PowerGridDomainPlugin,
    create_powergrid_scenario,
    validate_domain_integration,
)
from rift.experiments import SUPPORTED_SCENARIOS, validate_spec_payload
from rift.limits import SCENARIO_BOUNDS
from rift.runner import build_scenario, run_spec


def test_registered_everywhere():
    assert DOMAIN_ID == "powergrid-emergency"
    assert DOMAIN_ID in SUPPORTED_SCENARIOS
    for key in ("demand_mw", "supply_mw", "frequency_hz", "reserve_pct", "shed_mw"):
        assert key in SCENARIO_BOUNDS
    scenario = build_scenario(validate_spec_payload(
        {"name": "x", "scenario_name": DOMAIN_ID, "initial_state": {}}))
    assert scenario.name == DOMAIN_ID


def test_transition_physics_direction():
    scenario = create_powergrid_scenario()
    base = dict(scenario.initial_state)
    # Shedding + peaker must raise frequency when in deficit.
    stressed = dict(base, demand_mw=1500.0, supply_mw=1100.0)
    no_action = scenario.transition(dict(stressed), {"load_shed_ratio": 0.0, "peaker_dispatch": 0.0})
    action = scenario.transition(dict(stressed), {"load_shed_ratio": 0.2, "peaker_dispatch": 1.0})
    assert action["frequency_hz"] > no_action["frequency_hz"]
    assert action["shed_mw"] > 0.0
    # Blackout regime is reachable and detected.
    collapsed = scenario.transition(dict(stressed, supply_mw=200.0),
                                    {"load_shed_ratio": 0.0, "peaker_dispatch": 0.0})
    assert collapsed["frequency_hz"] < 48.5


def test_nominal_state_passes_guardian():
    from rift.verifier import verify_under_perturbations
    scenario = create_powergrid_scenario()
    checks = verify_under_perturbations(dict(scenario.initial_state), {},
                                        scenario.transition, list(scenario.constraints), [])
    assert all(c.passed for c in checks)


def test_perturbations_trigger_withhold():
    from rift.verifier import verify_under_perturbations
    scenario = create_powergrid_scenario()
    checks = verify_under_perturbations(dict(scenario.initial_state), {},
                                        scenario.transition, list(scenario.constraints),
                                        POWERGRID_PERTURBATIONS)
    assert any(not c.passed for c in checks)


def test_full_run_template_end_to_end():
    from rift.domains.powergrid.domain import DEFAULT_POWERGRID_TEMPLATE as t
    spec = validate_spec_payload({
        "name": "grid-e2e", "optimizer": "exact", "scenario_name": t["scenario_name"],
        "initial_state": dict(t["initial_state"]),
        "perturbations": [dict(p) for p in t["perturbations"]],
        "policy_variables": list(t["policy_variables"]),
    })
    out = dict(run_spec(spec))
    out.pop("duration_ms", None)
    assert out["assignment"] and out["method"].startswith("exact")


def test_plugin_metadata_and_integration():
    plugin = PowerGridDomainPlugin()
    assert plugin.domain_id == DOMAIN_ID
    assert set(plugin.get_policy_variables()) == {"load_shed_ratio", "peaker_dispatch"}
    assert len(plugin.get_default_perturbations()) == 5
    assert set(plugin.get_guardian_rules()) == {"P-001", "P-002", "P-003", "P-004", "P-005"}
    assert DOMAIN_METADATA["template"]["scenario_name"] == DOMAIN_ID
    report = validate_domain_integration()
    assert report["scenario_created"] is True
    assert report["futures_generated"] > 0 and report["policies_ranked"] > 0


def test_rejects_unknown_fields_and_bad_config():
    plugin = PowerGridDomainPlugin()
    assert plugin.validate_config({"initial_state": {"demand_mw": 9999.0}})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "scenario_name": DOMAIN_ID,
                               "initial_state": {"demand_mw": 9999.0}})
