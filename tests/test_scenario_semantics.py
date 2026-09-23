"""Blocked-exit semantics: stairwell_b is a risk penalty, not a physical closure.

The emergency-building transition adds ``blocked_b_penalty`` to risk when a
policy routes via stairwell B while the scenario marks B blocked. It does
NOT remove corridor capacity. These tests pin that semantic so future
changes either preserve it or consciously remodel it (and update docs).
"""

from rift.multivariable import evaluate_policy
from rift.scenarios import emergency_building


def test_unblocked_stairwell_has_no_penalty():
    scenario = emergency_building()
    assert scenario.initial_state["blocked_b_penalty"] == 0.0
    plain = evaluate_policy(scenario, {"route_a": 0, "route_c": 0, "stairwell_b": 0}, [])
    via_b = evaluate_policy(scenario, {"route_a": 0, "route_c": 0, "stairwell_b": 1}, [])
    assert via_b.nominal_cost == plain.nominal_cost


def test_blocked_penalty_flows_into_robust_cost():
    scenario = emergency_building()
    scenario.initial_state["blocked_b_penalty"] = 35.0
    plain = evaluate_policy(scenario, {"route_a": 0, "route_c": 0, "stairwell_b": 0}, [])
    via_b = evaluate_policy(scenario, {"route_a": 0, "route_c": 0, "stairwell_b": 1}, [])
    assert via_b.nominal_cost == plain.nominal_cost + 35.0
    assert via_b.robust_cost == plain.robust_cost + 35.0


def test_blocked_exit_does_not_change_capacity():
    scenario = emergency_building()
    scenario.initial_state["blocked_b_penalty"] = 35.0
    state = scenario.transition(dict(scenario.initial_state), {"route_a": 0, "route_c": 0, "stairwell_b": 1})
    assert state["corridor_capacity"] == scenario.initial_state["corridor_capacity"]
