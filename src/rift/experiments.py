"""First-class experiment model: durable identity + reproducible configuration.

The engine's :class:`rift.models.Scenario` holds Python callables and is
therefore not serializable. This module is the serializable product layer
sitting above it: an :class:`ExperimentSpec` captures *everything* needed
to reproduce a run (scenario descriptor, perturbations, policies,
optimizer/backend config, seed, engine version) using only JSON-safe
values, plus a stable fingerprint for compare/reproduce flows.

Lifecycle: CREATE → CONFIGURE → RUN → PERSIST → INSPECT → COMPARE → REPRODUCE.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from . import __version__ as ENGINE_VERSION
from .limits import (
    check_name,
    check_perturbations,
    check_policy_variables,
    check_scenario_state,
)

SUPPORTED_SCENARIOS = ("smart-building-emergency",)
SUPPORTED_OPTIMIZERS = ("exact", "qaoa-expectation", "qaoa-cvar")
SUPPORTED_BACKENDS = ("statevector-simulator", "none")
VALID_STATUSES = ("created", "configured", "running", "succeeded", "failed")


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    scenario_name: str = "smart-building-emergency"
    initial_state: dict = field(default_factory=dict)
    perturbations: tuple = field(default_factory=tuple)
    policy_variables: tuple = field(default_factory=tuple)
    optimizer: str = "exact"
    backend: str = "statevector-simulator"
    seed: int | None = None
    engine_version: str = ENGINE_VERSION
    description: str = ""
    status: str = "created"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scenario_name": self.scenario_name,
            "initial_state": dict(self.initial_state),
            "perturbations": [dict(p) for p in self.perturbations],
            "policy_variables": list(self.policy_variables),
            "optimizer": self.optimizer,
            "backend": self.backend,
            "seed": self.seed,
            "engine_version": self.engine_version,
            "description": self.description,
            "status": self.status,
        }

    def fingerprint(self) -> str:
        """Stable SHA-256 over canonical JSON (sorted keys, compact)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_spec_payload(payload: dict) -> ExperimentSpec:
    """Validate an untrusted POST body into an ExperimentSpec.

    Raises ValueError with a client-safe message on any problem.
    """
    if not isinstance(payload, dict):
        raise ValueError("experiment body must be a JSON object")
    name = payload.get("name", "")
    check_name(name)

    scenario_name = payload.get("scenario_name", "smart-building-emergency")
    scenario = payload.get("scenario")
    # Backward compat: legacy clients send {"name", "scenario": {...}} where
    # scenario is either a state dict or {"initial_state": {...}}.
    initial_state: dict = {}
    if isinstance(scenario, dict):
        if isinstance(scenario.get("initial_state"), dict):
            initial_state = dict(scenario["initial_state"])
            if isinstance(scenario.get("name"), str) and scenario["name"]:
                scenario_name = scenario["name"]
        else:
            initial_state = dict(scenario)
    elif "initial_state" in payload and isinstance(payload["initial_state"], dict):
        initial_state = dict(payload["initial_state"])

    if scenario_name not in SUPPORTED_SCENARIOS:
        raise ValueError(f"unsupported scenario_name: {scenario_name!r}")
    if initial_state:
        check_scenario_state(initial_state)

    perturbations = payload.get("perturbations", [])
    if not isinstance(perturbations, list):
        raise ValueError("perturbations must be a list")
    check_perturbations(perturbations)

    policy_variables = payload.get("policy_variables", ()) or ()
    if policy_variables:
        if not isinstance(policy_variables, (list, tuple)):
            raise ValueError("policy_variables must be a list")
        check_policy_variables(tuple(policy_variables))

    optimizer = payload.get("optimizer", "exact")
    if optimizer not in SUPPORTED_OPTIMIZERS:
        raise ValueError(f"unsupported optimizer: {optimizer!r}")
    backend = payload.get("backend", "statevector-simulator")
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"unsupported backend: {backend!r}")

    seed = payload.get("seed")
    if seed is not None and (not isinstance(seed, int) or abs(seed) > 2**62):
        raise ValueError("seed must be an integer")

    description = payload.get("description", "")
    if not isinstance(description, str) or len(description) > 2000:
        raise ValueError("description must be a string up to 2000 characters")

    status = payload.get("status", "created")
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported status: {status!r}")

    return ExperimentSpec(
        name=name.strip(),
        scenario_name=scenario_name,
        initial_state=initial_state,
        perturbations=tuple(dict(p) for p in perturbations),
        policy_variables=tuple(policy_variables),
        optimizer=optimizer,
        backend=backend,
        seed=seed,
        description=description,
        status=status,
    )


def validate_run_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("run body must be a JSON object")
    optimizer = payload.get("optimizer", "")
    if not isinstance(optimizer, str) or not optimizer.strip() or len(optimizer) > 64:
        raise ValueError("optimizer is required (string up to 64 chars)")
    metrics = payload.get("metrics", {})
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    seed = payload.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    result = payload.get("result")
    if result is not None and not isinstance(result, dict):
        raise ValueError("result must be an object")
    return {
        "optimizer": optimizer.strip(),
        "metrics": metrics,
        "seed": seed,
        "result": result,
    }
