"""Traffic Optimization Domain - Second reference domain for RIFT plugin architecture.

This domain models urban traffic corridor optimization:
- State: flow rate, queue length, average wait time
- Interventions: green time ratio, cycle length
- Objective: minimize wait time, maximize throughput
- Constraints: physical limits, safety requirements
"""
from __future__ import annotations

from typing import Callable

from ...models import Scenario, Constraint
from ...counterfactual import generate_futures
from ...robust import rank_robust_candidates
from ...adversarial import search_failure_states
from ...verifier import verify_under_perturbations


# --- Domain Constants ---

DOMAIN_ID = "traffic-optimization"
DISPLAY_NAME = "Traffic Flow Optimization"
DESCRIPTION = "Optimize traffic light timing for urban corridors"

# State variables
STATE_VARS = ("flow_rate", "queue_length", "avg_wait_time")
INTERVENTION_VARS = ("green_time_ratio", "cycle_length")

# Physical bounds
FLOW_BOUNDS = (0, 5000)          # vehicles/hour
QUEUE_BOUNDS = (0, 200)          # vehicles
WAIT_BOUNDS = (0, 300)           # seconds
GREEN_TIME_BOUNDS = (0.2, 0.8)   # ratio
CYCLE_BOUNDS = (30, 180)         # seconds

# Perturbations for robustness testing
TRAFFIC_PERTURBATIONS = [
    {"flow_rate": 500.0},           # demand surge
    {"flow_rate": -300.0},          # demand drop
    {"queue_length": 20.0},         # incident backup
    {"avg_wait_time": 30.0},        # downstream blockage
    {"flow_rate": 400.0, "queue_length": 15.0},  # compound
]


# --- Scenario Construction ---

def create_traffic_scenario(config: dict | None = None) -> Scenario:
    """Create a traffic optimization scenario from config."""
    config = config or {}

    # Initial state
    initial_state = config.get("initial_state", {
        "flow_rate": 1200.0,
        "queue_length": 25.0,
        "avg_wait_time": 45.0,
    })

    def transition(state: dict, policy: dict) -> dict:
        """Simulate traffic light policy effect on corridor."""
        green_time = policy.get("green_time_ratio", 0.5)
        cycle_len = policy.get("cycle_length", 90.0)

        # Green time effect: more green -> higher throughput, lower wait
        throughput_factor = 1.0 + 0.4 * (green_time - 0.5)
        wait_factor = max(0.3, 1.0 - 0.5 * (green_time - 0.3))
        cycle_factor = 1.0 + 0.1 * (cycle_len - 90.0) / 90.0

        new_flow = state["flow_rate"] * throughput_factor * cycle_factor
        new_queue = max(0.0, state["queue_length"] - 10.0 * green_time * cycle_factor)
        new_wait = max(WAIT_BOUNDS[0], state["avg_wait_time"] * wait_factor / cycle_factor)

        # Add stochastic variation (deterministic seed based on state)
        import hashlib
        seed_str = f"{state['flow_rate']:.1f}{state['queue_length']:.1f}{green_time:.2f}"
        h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        noise = (h % 1000) / 10000.0 - 0.05  # -5% to +5%

        return {
            "flow_rate": max(FLOW_BOUNDS[0], min(FLOW_BOUNDS[1], new_flow * (1.0 + noise))),
            "queue_length": max(QUEUE_BOUNDS[0], min(QUEUE_BOUNDS[1], new_queue * (1.0 + noise))),
            "avg_wait_time": max(WAIT_BOUNDS[0], min(WAIT_BOUNDS[1], new_wait * (1.0 + noise))),
        }

    # Constraints
    constraints = (
        Constraint("flow_positive", lambda s: FLOW_BOUNDS[0] <= s.get("flow_rate", 0) <= FLOW_BOUNDS[1], "Flow rate out of bounds"),
        Constraint("queue_nonneg", lambda s: QUEUE_BOUNDS[0] <= s.get("queue_length", 0) <= QUEUE_BOUNDS[1], "Queue length out of bounds"),
        Constraint("wait_reasonable", lambda s: WAIT_BOUNDS[0] <= s.get("avg_wait_time", 0) <= WAIT_BOUNDS[1], "Wait time out of bounds"),
        Constraint("green_time_bounds", lambda s: True, "Green time bounds enforced in policy"),
        Constraint("cycle_bounds", lambda s: True, "Cycle bounds enforced in policy"),
    )

    # Objective: minimize weighted sum of wait time and maximize flow
    def objective(state: dict) -> float:
        # Normalize: wait_time [0-300] -> [0-1], flow_rate [0-5000] -> [0-1]
        wait_norm = state.get("avg_wait_time", 300) / 300.0
        flow_norm = 1.0 - (state.get("flow_rate", 0) / 5000.0)
        queue_norm = state.get("queue_length", 200) / 200.0

        # Weighted: 50% wait, 30% queue, 20% inverse flow
        return 0.5 * wait_norm + 0.3 * queue_norm + 0.2 * flow_norm

    return Scenario(
        name="traffic-optimization",
        initial_state=initial_state,
        interventions={
            "green_time_ratio": GREEN_TIME_BOUNDS,
            "cycle_length": CYCLE_BOUNDS,
        },
        transition=transition,
        constraints=constraints,
        objective=objective,
    )


# --- Domain Plugin Interface ---

class TrafficDomainPlugin:
    """Plugin implementation for Traffic Optimization domain."""

    @property
    def domain_id(self) -> str:
        return DOMAIN_ID

    @property
    def display_name(self) -> str:
        return DISPLAY_NAME

    @property
    def description(self) -> str:
        return DESCRIPTION

    def create_scenario(self, config: dict) -> "Scenario":
        return create_traffic_scenario(config)

    def get_policy_variables(self) -> list[str]:
        return list(INTERVENTION_VARS)

    def get_default_perturbations(self) -> list[dict]:
        return TRAFFIC_PERTURBATIONS

    def get_constraints(self) -> list:
        from ..models import Constraint
        return [
            Constraint("flow_positive", lambda s: FLOW_BOUNDS[0] <= s.get("flow_rate", 0) <= FLOW_BOUNDS[1], "Flow rate out of bounds"),
            Constraint("queue_nonneg", lambda s: QUEUE_BOUNDS[0] <= s.get("queue_length", 0) <= QUEUE_BOUNDS[1], "Queue length out of bounds"),
            Constraint("wait_reasonable", lambda s: WAIT_BOUNDS[0] <= s.get("avg_wait_time", 0) <= WAIT_BOUNDS[1], "Wait time out of bounds"),
        ]

    def get_objective(self) -> Callable[[dict], float]:
        def objective(state: dict) -> float:
            wait_norm = state.get("avg_wait_time", 300) / 300.0
            flow_norm = 1.0 - (state.get("flow_rate", 0) / 5000.0)
            queue_norm = state.get("queue_length", 200) / 200.0
            return 0.5 * wait_norm + 0.3 * queue_norm + 0.2 * flow_norm
        return objective

    def get_transition(self) -> Callable[[dict, dict], dict]:
        scenario = create_traffic_scenario()
        return scenario.transition

    def get_interventions(self) -> dict[str, tuple]:
        return {
            "green_time_ratio": GREEN_TIME_BOUNDS,
            "cycle_length": CYCLE_BOUNDS,
        }

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        state = config.get("initial_state", {})
        if "flow_rate" in state and not (FLOW_BOUNDS[0] <= state["flow_rate"] <= FLOW_BOUNDS[1]):
            errors.append(f"flow_rate must be in {FLOW_BOUNDS}")
        if "queue_length" in state and not (QUEUE_BOUNDS[0] <= state["queue_length"] <= QUEUE_BOUNDS[1]):
            errors.append(f"queue_length must be in {QUEUE_BOUNDS}")
        if "avg_wait_time" in state and not (WAIT_BOUNDS[0] <= state["avg_wait_time"] <= WAIT_BOUNDS[1]):
            errors.append(f"avg_wait_time must be in {WAIT_BOUNDS}")
        return errors

    # --- Domain-specific Guardian Rules ---

    GUARDIAN_RULES = {
        "T-001": {
            "stage": "STATE",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Flow rate exceeds physical capacity",
            "check": lambda state: state.get("flow_rate", 0) > 4500,
            "message": "Flow rate {flow_rate} vph exceeds 4500 vph capacity",
        },
        "T-002": {
            "stage": "STATE",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Queue length exceeds storage capacity",
            "check": lambda state: state.get("queue_length", 0) > 180,
            "message": "Queue length {queue_length} vehicles exceeds 180 storage limit",
        },
        "T-003": {
            "stage": "STATE",
            "severity": "MEDIUM",
            "action": "WARN",
            "summary": "Wait time exceeds acceptable threshold",
            "check": lambda state: state.get("avg_wait_time", 0) > 120,
            "message": "Average wait time {avg_wait_time}s exceeds 120s threshold",
        },
        "T-004": {
            "stage": "OPTIMIZATION",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Optimization suggests unsafe green time",
            "check": lambda result: result.get("policy", {}).get("green_time_ratio", 0.5) > 0.75,
            "message": "Green time ratio {green_time_ratio} > 0.75 unsafe for cross-traffic",
        },
        "T-005": {
            "stage": "OUTPUT",
            "severity": "MEDIUM",
            "action": "WARN",
            "summary": "Predicted wait time increase",
            "check": lambda result: result.get("state", {}).get("avg_wait_time", 0) > result.get("previous_state", {}).get("avg_wait_time", 0) * 1.5,
            "message": "Optimization increases wait time by >50%",
        },
    }

    # --- Domain-specific Visualization Config ---

    VISUALIZATION_CONFIG = {
        "state_variables": {
            "flow_rate": {"label": "Flow Rate (vph)", "unit": "vph", "color": "#3b82f6", "bounds": FLOW_BOUNDS},
            "queue_length": {"label": "Queue Length", "unit": "veh", "color": "#f59e0b", "bounds": QUEUE_BOUNDS},
            "avg_wait_time": {"label": "Avg Wait Time", "unit": "s", "color": "#ef4444", "bounds": WAIT_BOUNDS},
        },
        "intervention_variables": {
            "green_time_ratio": {"label": "Green Time Ratio", "unit": "ratio", "bounds": GREEN_TIME_BOUNDS},
            "cycle_length": {"label": "Cycle Length", "unit": "s", "bounds": CYCLE_BOUNDS},
        },
        "perturbation_colors": {
            "flow_rate": "#3b82f6",
            "queue_length": "#f59e0b",
            "avg_wait_time": "#ef4444",
        },
        "dashboard_layout": {
            "primary_metric": "avg_wait_time",
            "secondary_metrics": ["flow_rate", "queue_length"],
            "show_perturbation_bands": True,
            "show_guardian_zones": True,
        },
    }

    def get_visualization_config(self) -> dict:
        return self.VISUALIZATION_CONFIG

    def get_guardian_rules(self) -> dict:
        return self.GUARDIAN_RULES


# --- Experiment Template ---

DEFAULT_TRAFFIC_TEMPLATE = {
    "name": "traffic-corridor-optimization",
    "scenario_name": "traffic-optimization",
    "initial_state": {
        "flow_rate": 1200.0,
        "queue_length": 25.0,
        "avg_wait_time": 45.0,
    },
    "perturbations": TRAFFIC_PERTURBATIONS,
    "policy_variables": list(INTERVENTION_VARS),
    "optimizer": "exact",
    "backend": "statevector-simulator",
    "seed": 42,
    "description": "Traffic corridor optimization with demand perturbations",
}


# --- Canonical Plugin Instance ---

traffic_domain_plugin = TrafficDomainPlugin()


# --- Validation: Test the domain works with RIFT core ---

def validate_domain_integration() -> dict:
    """Validate that the domain works with RIFT core components."""
    from rift.counterfactual import generate_futures
    from rift.robust import rank_robust_candidates
    from rift.adversarial import search_failure_states
    from rift.verifier import verify_under_perturbations
    from rift.counterfactual import Future

    # Create scenario
    scenario = create_traffic_scenario()

    # Generate futures
    futures = generate_futures(scenario)

    # Robust ranking
    ranked = rank_robust_candidates(scenario, futures, TRAFFIC_PERTURBATIONS)

    # Adversarial search
    best_policy = ranked[0].candidate.policy if ranked else {}
    best_future = ranked[0].candidate if ranked else Future(policy=best_policy, score=0.0, valid=True)
    adversarial = search_failure_states(scenario, best_future, TRAFFIC_PERTURBATIONS)

    # Verification
    verified = verify_under_perturbations(
        dict(scenario.initial_state), best_policy,
        scenario.transition, list(scenario.constraints), TRAFFIC_PERTURBATIONS,
    )

    return {
        "domain_id": DOMAIN_ID,
        "scenario_created": True,
        "futures_generated": len(futures),
        "policies_ranked": len(ranked),
        "adversarial_found": len(adversarial) > 0,
        "verified": all(v.passed for v in verified),
        "top_policy": ranked[0].candidate.policy if ranked else None,
        "worst_case_risk": ranked[0].worst_case.adversarial_score if ranked and ranked[0].worst_case else None,
    }


# --- Domain Metadata for Registry ---

DOMAIN_METADATA = {
    "domain_id": DOMAIN_ID,
    "display_name": DISPLAY_NAME,
    "description": DESCRIPTION,
    "version": "1.0.0",
    "author": "RIFT Team",
    "state_variables": list(STATE_VARS),
    "intervention_variables": list(INTERVENTION_VARS),
    "perturbations": TRAFFIC_PERTURBATIONS,
    "guardian_rules": list(TrafficDomainPlugin.GUARDIAN_RULES.keys()),
    "visualization": TrafficDomainPlugin().VISUALIZATION_CONFIG,
    "template": DEFAULT_TRAFFIC_TEMPLATE,
}


# --- Register with Extension Manager ---

try:
    from ..developer.plugin_sdk import extension_manager, ExtensionManifest
    from pathlib import Path

    traffic_manifest = ExtensionManifest(
        id=DOMAIN_ID,
        name=DISPLAY_NAME,
        version="1.0.0",
        description=DESCRIPTION,
        author="RIFT Team",
        provides=["domain"],
        entry_points={"domain": "rift.domains.traffic.domain.TrafficDomainPlugin"},
    )

    # Only register if extension manager is available
    if hasattr(extension_manager, '_manifests'):
        extension_manager._manifests[DOMAIN_ID] = traffic_manifest
except Exception:
    pass  # Extension manager not available yet


# Canonical plugin instance
traffic_domain_plugin = TrafficDomainPlugin()