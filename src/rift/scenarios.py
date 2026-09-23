from .models import Constraint, Scenario

def emergency_building() -> Scenario:
    """Smart-building emergency scenario.

    Blocked-exit semantics: ``stairwell_b`` is a policy choice to route via
    stairwell B, and ``blocked_b_penalty`` is a risk penalty applied when B
    is marked blocked. This is a penalty model, NOT a physical closure: it
    does not reduce ``corridor_capacity``. See tests/test_scenario_semantics.py.
    """
    def transition(state, policy):
        density = state["crowd"] / max(state["corridor_capacity"], 1.0)
        route_a = policy.get("route_a", 0)
        route_c = policy.get("route_c", 0)
        smoke = state["smoke"] + state.get("smoke_growth", 0.0)
        congestion = max(0.0, density * 40.0 + 24.0 * (route_a + route_c) - 16.0 * min(route_a, route_c))
        evacuation = 7.0 + congestion * 0.07 + smoke * 0.9
        risk = smoke * 7.0 + congestion * 1.8 + max(0.0, 55.0 - evacuation) * 0.2
        if policy.get("stairwell_b", 0):
            risk += state.get("blocked_b_penalty", 0.0)
        return {**state, "smoke": smoke, "congestion": congestion, "evacuation_time": evacuation, "risk": risk}

    constraints = (
        Constraint("hazard", lambda s: s["smoke"] < 9.0, "Policy enters a high-smoke regime"),
        Constraint("congestion", lambda s: s["congestion"] < 100.0, "Crowd density exceeds safe operating capacity"),
        Constraint("time", lambda s: s["evacuation_time"] < 30.0, "Evacuation time exceeds the hard limit"),
    )
    return Scenario(
        name="smart-building-emergency",
        initial_state={"crowd": 430.0, "corridor_capacity": 520.0, "smoke": 3.0, "smoke_growth": 0.0, "blocked_b_penalty": 0.0},
        interventions={"route_a": (0, 1), "route_c": (0, 1), "stairwell_b": (0, 1)},
        transition=transition,
        constraints=constraints,
        objective=lambda s: s["risk"] + 0.45 * s["congestion"] + 0.8 * s["evacuation_time"],
    )
