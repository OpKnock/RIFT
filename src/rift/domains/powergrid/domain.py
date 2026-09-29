"""Power Grid Emergency Domain - Third reference domain for RIFT plugin architecture.

This domain models emergency load-shedding for a islanded grid zone:
- State: demand, firm supply, frequency, spinning reserve, shed load
- Interventions: controllable load-shed ratio, peaker dispatch level
- Objective: minimize unserved energy plus frequency deviation
- Constraints: statutory frequency band, shed cap, equipment bounds

The model is intentionally stylized (linear swing approximation, not a
power-flow simulation) and documented as such: it exercises RIFT's
counterfactual, robust, guardian, and audit machinery on a third set of
physics, not a claim of grid-operation fidelity.
"""
from __future__ import annotations

from typing import Callable

from ...models import Scenario, Constraint
from ...counterfactual import generate_futures
from ...robust import rank_robust_candidates
from ...adversarial import search_failure_states
from ...verifier import verify_under_perturbations


# --- Domain Constants ---

DOMAIN_ID = "powergrid-emergency"
DISPLAY_NAME = "Power Grid Emergency Shedding"
DESCRIPTION = "Optimize emergency load-shedding and peaker dispatch for a grid zone"

# State variables
STATE_VARS = ("demand_mw", "supply_mw", "frequency_hz", "reserve_pct", "shed_mw")
INTERVENTION_VARS = ("load_shed_ratio", "peaker_dispatch")

# Physical bounds
DEMAND_BOUNDS = (0.0, 2000.0)        # MW
SUPPLY_BOUNDS = (0.0, 2000.0)        # MW firm supply
FREQUENCY_BOUNDS = (45.0, 55.0)      # Hz (statutory band is tighter; see constraints)
FREQUENCY_STATUTORY = (49.2, 50.8)   # Hz normal operating band
RESERVE_BOUNDS = (0.0, 100.0)        # percent spinning reserve
SHED_BOUNDS = (0.0, 600.0)           # MW shed in one step
SHED_RATIO_BOUNDS = (0.0, 0.3)       # fraction of controllable load
PEAKER_BOUNDS = (0.0, 1.0)           # peaker dispatch level
PEAKER_CAPACITY_MW = 200.0
BLACKOUT_HZ = 48.5                   # below this the zone is considered blacked out

# Perturbations for robustness testing
POWERGRID_PERTURBATIONS = [
    {"demand_mw": 150.0},                        # demand surge (heat wave)
    {"supply_mw": -120.0},                       # generator trip
    {"demand_mw": 100.0, "supply_mw": -60.0},    # compound shortfall
    {"demand_mw": -100.0},                       # demand drop (over-frequency risk)
    {"supply_mw": -40.0, "demand_mw": 60.0},     # mild shortfall
]


# --- Scenario Construction ---

def create_powergrid_scenario(config: dict | None = None) -> Scenario:
    """Create a power-grid emergency scenario from config."""
    config = config or {}

    initial_state = config.get("initial_state", {
        "demand_mw": 1200.0,
        "supply_mw": 1100.0,
        "frequency_hz": 50.0,
        "reserve_pct": 60.0,
        "shed_mw": 0.0,
    })

    def transition(state: dict, policy: dict) -> dict:
        """Stylized swing model: shed + peaker dispatch close the energy gap."""
        shed_ratio = min(max(policy.get("load_shed_ratio", 0.0), 0.0), 1.0)
        peaker = min(max(policy.get("peaker_dispatch", 0.0), 0.0), 1.0)
        demand = state["demand_mw"]
        supply = state["supply_mw"]

        shed = min(demand * shed_ratio, SHED_BOUNDS[1])
        served = max(0.0, demand - shed)
        total_supply = supply + peaker * PEAKER_CAPACITY_MW
        deficit = served - total_supply
        # Linear swing approximation: 200 MW of deficit moves 1 Hz.
        frequency = 50.0 - deficit / 200.0
        reserve = state["reserve_pct"] - peaker * 8.0 + 2.0

        # Deterministic dither (state-seeded, like the traffic domain).
        import hashlib
        seed_str = f"{demand:.1f}{supply:.1f}{shed_ratio:.2f}{peaker:.2f}"
        h = int(hashlib.md5(seed_str.encode(), usedforsecurity=False).hexdigest()[:8], 16)
        noise = (h % 1000) / 10000.0 - 0.05  # -5% to +5%

        def clamp(value: float, bounds: tuple) -> float:
            return max(bounds[0], min(bounds[1], value))

        return {
            "demand_mw": clamp(demand, DEMAND_BOUNDS),
            "supply_mw": clamp(total_supply, SUPPLY_BOUNDS),
            "frequency_hz": clamp(frequency * (1.0 + noise * 0.02), FREQUENCY_BOUNDS),
            "reserve_pct": clamp(reserve, RESERVE_BOUNDS),
            "shed_mw": clamp(shed, SHED_BOUNDS),
        }

    constraints = (
        Constraint("frequency_band",
                   lambda s: FREQUENCY_STATUTORY[0] <= s.get("frequency_hz", 50.0) <= FREQUENCY_STATUTORY[1],
                   "Frequency outside the statutory operating band"),
        Constraint("no_blackout",
                   lambda s: s.get("frequency_hz", 50.0) >= BLACKOUT_HZ,
                   "Frequency below blackout threshold"),
        Constraint("shed_cap",
                   lambda s: SHED_BOUNDS[0] <= s.get("shed_mw", 0.0) <= SHED_BOUNDS[1],
                   "Shed load outside equipment limits"),
        Constraint("demand_bounds",
                   lambda s: DEMAND_BOUNDS[0] <= s.get("demand_mw", 0.0) <= DEMAND_BOUNDS[1],
                   "Demand outside modeled range"),
        Constraint("reserve_bounds",
                   lambda s: RESERVE_BOUNDS[0] <= s.get("reserve_pct", 0.0) <= RESERVE_BOUNDS[1],
                   "Reserve outside physical range"),
    )

    def objective(state: dict) -> float:
        # Unserved energy (normalized) plus frequency deviation (Hz scaled).
        shed_norm = state.get("shed_mw", 0.0) / SHED_BOUNDS[1]
        freq_dev = abs(state.get("frequency_hz", 50.0) - 50.0)
        reserve_short = 1.0 - state.get("reserve_pct", 100.0) / 100.0
        return 0.6 * shed_norm + 0.3 * (freq_dev / 5.0) + 0.1 * reserve_short

    return Scenario(
        name="powergrid-emergency",
        initial_state=initial_state,
        interventions={
            "load_shed_ratio": SHED_RATIO_BOUNDS,
            "peaker_dispatch": PEAKER_BOUNDS,
        },
        transition=transition,
        constraints=constraints,
        objective=objective,
    )


# --- Domain Plugin Interface ---

class PowerGridDomainPlugin:
    """Plugin implementation for the power-grid emergency domain."""

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
        return create_powergrid_scenario(config)

    def get_policy_variables(self) -> list[str]:
        return list(INTERVENTION_VARS)

    def get_default_perturbations(self) -> list[dict]:
        return POWERGRID_PERTURBATIONS

    def get_constraints(self) -> list:
        from ..models import Constraint
        return [
            Constraint("frequency_band",
                       lambda s: FREQUENCY_STATUTORY[0] <= s.get("frequency_hz", 50.0) <= FREQUENCY_STATUTORY[1],
                       "Frequency outside the statutory operating band"),
            Constraint("no_blackout",
                       lambda s: s.get("frequency_hz", 50.0) >= BLACKOUT_HZ,
                       "Frequency below blackout threshold"),
            Constraint("shed_cap",
                       lambda s: SHED_BOUNDS[0] <= s.get("shed_mw", 0.0) <= SHED_BOUNDS[1],
                       "Shed load outside equipment limits"),
        ]

    def get_objective(self) -> Callable[[dict], float]:
        def objective(state: dict) -> float:
            shed_norm = state.get("shed_mw", 0.0) / SHED_BOUNDS[1]
            freq_dev = abs(state.get("frequency_hz", 50.0) - 50.0)
            reserve_short = 1.0 - state.get("reserve_pct", 100.0) / 100.0
            return 0.6 * shed_norm + 0.3 * (freq_dev / 5.0) + 0.1 * reserve_short
        return objective

    def get_transition(self) -> Callable[[dict, dict], dict]:
        scenario = create_powergrid_scenario()
        return scenario.transition

    def get_interventions(self) -> dict[str, tuple]:
        return {
            "load_shed_ratio": SHED_RATIO_BOUNDS,
            "peaker_dispatch": PEAKER_BOUNDS,
        }

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        state = config.get("initial_state", {})
        for key, bounds in (("demand_mw", DEMAND_BOUNDS),
                            ("supply_mw", SUPPLY_BOUNDS),
                            ("frequency_hz", FREQUENCY_BOUNDS),
                            ("reserve_pct", RESERVE_BOUNDS)):
            if key in state and not (bounds[0] <= state[key] <= bounds[1]):
                errors.append(f"{key} must be in {bounds}")
        return errors

    # --- Domain-specific Guardian Rules ---

    GUARDIAN_RULES = {
        "P-001": {
            "stage": "STATE",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Frequency outside statutory band",
            "check": lambda state: not (FREQUENCY_STATUTORY[0] <= state.get("frequency_hz", 50.0) <= FREQUENCY_STATUTORY[1]),
            "message": "Frequency {frequency_hz} Hz outside [49.2, 50.8] Hz band",
        },
        "P-002": {
            "stage": "STATE",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Blackout regime",
            "check": lambda state: state.get("frequency_hz", 50.0) < BLACKOUT_HZ,
            "message": "Frequency below blackout threshold 48.5 Hz",
        },
        "P-003": {
            "stage": "OPTIMIZATION",
            "severity": "HIGH",
            "action": "WITHHOLD",
            "summary": "Optimization sheds more than the cap allows",
            "check": lambda result: result.get("policy", {}).get("load_shed_ratio", 0.0) > SHED_RATIO_BOUNDS[1],
            "message": "Shed ratio above 0.30 equipment cap",
        },
        "P-004": {
            "stage": "STATE",
            "severity": "MEDIUM",
            "action": "WARN",
            "summary": "Spinning reserve critically low",
            "check": lambda state: state.get("reserve_pct", 100.0) < 15.0,
            "message": "Reserve {reserve_pct}% below 15% floor",
        },
        "P-005": {
            "stage": "OUTPUT",
            "severity": "MEDIUM",
            "action": "WARN",
            "summary": "Optimization increases unserved energy sharply",
            "check": lambda result: result.get("state", {}).get("shed_mw", 0.0) > result.get("previous_state", {}).get("shed_mw", 0.0) + 200.0,
            "message": "Optimization sheds 200+ MW more than the previous state",
        },
    }

    # --- Domain-specific Visualization Config ---

    VISUALIZATION_CONFIG = {
        "state_variables": {
            "demand_mw": {"label": "Demand", "unit": "MW", "color": "#3b82f6", "bounds": DEMAND_BOUNDS},
            "supply_mw": {"label": "Supply", "unit": "MW", "color": "#10b981", "bounds": SUPPLY_BOUNDS},
            "frequency_hz": {"label": "Frequency", "unit": "Hz", "color": "#f59e0b", "bounds": FREQUENCY_BOUNDS},
            "reserve_pct": {"label": "Reserve", "unit": "%", "color": "#8b5cf6", "bounds": RESERVE_BOUNDS},
            "shed_mw": {"label": "Shed Load", "unit": "MW", "color": "#ef4444", "bounds": SHED_BOUNDS},
        },
        "intervention_variables": {
            "load_shed_ratio": {"label": "Load Shed Ratio", "unit": "ratio", "bounds": SHED_RATIO_BOUNDS},
            "peaker_dispatch": {"label": "Peaker Dispatch", "unit": "level", "bounds": PEAKER_BOUNDS},
        },
        "perturbation_colors": {
            "demand_mw": "#3b82f6",
            "supply_mw": "#10b981",
            "frequency_hz": "#f59e0b",
        },
        "dashboard_layout": {
            "primary_metric": "frequency_hz",
            "secondary_metrics": ["demand_mw", "shed_mw"],
            "show_perturbation_bands": True,
            "show_guardian_zones": True,
        },
    }

    def get_visualization_config(self) -> dict:
        return self.VISUALIZATION_CONFIG

    def get_guardian_rules(self) -> dict:
        return self.GUARDIAN_RULES


# --- Experiment Template ---

DEFAULT_POWERGRID_TEMPLATE = {
    "name": "powergrid-emergency-shedding",
    "scenario_name": "powergrid-emergency",
    "initial_state": {
        "demand_mw": 1200.0,
        "supply_mw": 1100.0,
        "frequency_hz": 50.0,
        "reserve_pct": 60.0,
        "shed_mw": 0.0,
    },
    "perturbations": POWERGRID_PERTURBATIONS,
    "policy_variables": list(INTERVENTION_VARS),
    "optimizer": "exact",
    "backend": "statevector-simulator",
    "seed": 42,
    "description": "Emergency load-shedding with supply shortfall perturbations",
}


# --- Canonical Plugin Instance ---

powergrid_domain_plugin = PowerGridDomainPlugin()


# --- Validation: Test the domain works with RIFT core ---

def validate_domain_integration() -> dict:
    """Validate that the domain works with RIFT core components."""
    from rift.counterfactual import generate_futures
    from rift.robust import rank_robust_candidates
    from rift.adversarial import search_failure_states
    from rift.verifier import verify_under_perturbations
    from rift.counterfactual import Future

    # Create scenario
    scenario = create_powergrid_scenario()

    # Generate futures
    futures = generate_futures(scenario)

    # Robust ranking
    ranked = rank_robust_candidates(scenario, futures, POWERGRID_PERTURBATIONS)

    # Adversarial search
    best_policy = ranked[0].candidate.policy if ranked else {}
    best_future = ranked[0].candidate if ranked else Future(policy=best_policy, score=0.0, valid=True)
    adversarial = search_failure_states(scenario, best_future, POWERGRID_PERTURBATIONS)

    # Verification
    verified = verify_under_perturbations(
        dict(scenario.initial_state), best_policy,
        scenario.transition, list(scenario.constraints), POWERGRID_PERTURBATIONS,
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
    "perturbations": POWERGRID_PERTURBATIONS,
    "guardian_rules": list(PowerGridDomainPlugin.GUARDIAN_RULES.keys()),
    "visualization": PowerGridDomainPlugin().VISUALIZATION_CONFIG,
    "template": DEFAULT_POWERGRID_TEMPLATE,
}


# --- Register with Extension Manager ---

try:
    from ..developer.plugin_sdk import extension_manager, ExtensionManifest

    powergrid_manifest = ExtensionManifest(
        id=DOMAIN_ID,
        name=DISPLAY_NAME,
        version="1.0.0",
        description=DESCRIPTION,
        author="RIFT Team",
        provides=["domain"],
        entry_points={"domain": "rift.domains.powergrid.domain.PowerGridDomainPlugin"},
    )

    # Only register if extension manager is available
    if hasattr(extension_manager, '_manifests'):
        extension_manager._manifests[DOMAIN_ID] = powergrid_manifest
except Exception:  # nosec B110 -- extension manager not available yet; domain still importable standalone
    pass


# Canonical plugin instance
powergrid_domain_plugin = PowerGridDomainPlugin()
