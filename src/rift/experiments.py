"""First-class experiment model: durable identity + reproducible configuration.

The engine's :class:`rift.models.Scenario` holds Python callables and is
therefore not serializable. This module is the serializable product layer
sitting above it: an :class:`ExperimentSpec` captures *everything* needed
to reproduce a run (scenario descriptor, perturbations, policies,
optimizer/backend config, seed, engine version) using only JSON-safe
values, plus a stable fingerprint for compare/reproduce flows.

Lifecycle: CREATE → CONFIGURE → RUN → PERSIST → INSPECT → COMPARE → REPRODUCE.

Phase 10 additions:
- Experiment templates (reusable configurations)
- Experiment/Run versioning
- Deterministic replay with exact seed+spec
- Scenario snapshots (serializable scenario state)
- Benchmark suites & datasets
- Experiment comparison (optimizer, model, perturbation, robustness, regression)
- Experiment metadata & provenance
- Evidence bundles (reproducible evidence from stored runs)
- Reproducibility verification
- Historical experiment archive
- Export/import (portable experiment packages)
- Automated experiment execution & scheduling
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

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
VALID_STATUSES = ("created", "configured", "running", "succeeded", "failed", "cancelled")

# --- Core Experiment Spec ---

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
    # Phase 10: template support
    template_id: str | None = None
    template_version: str | None = None

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
            "template_id": self.template_id,
            "template_version": self.template_version,
        }

    def fingerprint(self) -> str:
        """Stable SHA-256 over canonical JSON (sorted keys, compact)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def with_overrides(self, **overrides) -> "ExperimentSpec":
        """Create a new spec with overridden fields (for versioning)."""
        data = self.to_dict()
        data.update(overrides)
        return ExperimentSpec(**data)


# --- Experiment Template ---

@dataclass(frozen=True)
class ExperimentTemplate:
    """Reusable experiment configuration template."""
    id: str
    name: str
    description: str
    spec: ExperimentSpec
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    tags: tuple = field(default_factory=tuple)
    is_public: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "spec": self.spec.to_dict(),
            "version": self.version,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "tags": list(self.tags),
            "is_public": self.is_public,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentTemplate":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            spec=ExperimentSpec(**data["spec"]),
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            created_by=data.get("created_by", "system"),
            tags=tuple(data.get("tags", [])),
            is_public=data.get("is_public", False),
        )


# --- Experiment Run ---

@dataclass(frozen=True)
class ExperimentRun:
    """Single execution of an experiment."""
    id: str
    experiment_id: str
    experiment_version: int
    spec: ExperimentSpec
    optimizer: str
    metrics: dict
    result: dict | None
    seed: int | None
    engine_version: str
    started_at: str
    completed_at: str | None
    status: str  # running, succeeded, failed, cancelled
    error: str | None = None
    # Phase 10: reproducibility
    fingerprint: str | None = None
    git_commit: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "experiment_version": self.experiment_version,
            "spec": self.spec.to_dict(),
            "optimizer": self.optimizer,
            "metrics": self.metrics,
            "result": self.result,
            "seed": self.seed,
            "engine_version": self.engine_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "error": self.error,
            "fingerprint": self.fingerprint,
            "git_commit": self.git_commit,
        }


# --- Scenario Snapshot ---

@dataclass(frozen=True)
class ScenarioSnapshot:
    """Serializable snapshot of a scenario for replay."""
    id: str
    experiment_id: str
    scenario_name: str
    initial_state: dict
    perturbations: list[dict]
    policy_variables: list[str]
    constraints: list[dict]
    objective: str  # serialized representation
    transition: str  # serialized representation
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "scenario_name": self.scenario_name,
            "initial_state": self.initial_state,
            "perturbations": self.perturbations,
            "policy_variables": self.policy_variables,
            "constraints": self.constraints,
            "objective": self.objective,
            "transition": self.transition,
            "created_at": self.created_at,
            "fingerprint": self.fingerprint,
        }


# --- Benchmark Suite ---

@dataclass(frozen=True)
class BenchmarkDataset:
    """Reference dataset for benchmarking."""
    id: str
    name: str
    description: str
    scenarios: list[dict]  # list of scenario configs
    expected_results: dict | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scenarios": self.scenarios,
            "expected_results": self.expected_results,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BenchmarkSuite:
    """Collection of benchmark datasets and comparison criteria."""
    id: str
    name: str
    description: str
    datasets: list[BenchmarkDataset]
    metrics: list[str]  # metrics to compare (energy, runtime, gap, etc.)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "datasets": [d.to_dict() for d in self.datasets],
            "metrics": self.metrics,
            "created_at": self.created_at,
        }


# --- Comparison Results ---

@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing experiments/runs."""
    comparison_id: str
    type: str  # optimizer, model, perturbation, robustness, regression
    baseline_id: str
    candidate_ids: list[str]
    metrics: dict  # metric -> {baseline: val, candidate: val, diff: val}
    summary: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "comparison_id": self.comparison_id,
            "type": self.type,
            "baseline_id": self.baseline_id,
            "candidate_ids": self.candidate_ids,
            "metrics": self.metrics,
            "summary": self.summary,
            "created_at": self.created_at,
        }


# --- Evidence Bundle ---

@dataclass(frozen=True)
class EvidenceBundle:
    """Complete reproducible evidence for an experiment/run."""
    bundle_id: str
    experiment_id: str
    run_id: str | None
    spec: ExperimentSpec
    scenario_snapshot: ScenarioSnapshot | None
    runs: list[ExperimentRun]
    comparisons: list[ComparisonResult]
    benchmark_results: dict | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    verification_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "spec": self.spec.to_dict(),
            "scenario_snapshot": self.scenario_snapshot.to_dict() if self.scenario_snapshot else None,
            "runs": [r.to_dict() for r in self.runs],
            "comparisons": [c.to_dict() for c in self.comparisons],
            "benchmark_results": self.benchmark_results,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "verification_hash": self.verification_hash,
        }


# --- Experiment Archive ---

class ExperimentArchive:
    """Historical experiment archive with query and export."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._experiments: dict[str, dict] = {}  # id -> full experiment record
        self._runs: dict[str, list[ExperimentRun]] = {}  # experiment_id -> runs
        self._templates: dict[str, ExperimentTemplate] = {}
        self._benchmarks: dict[str, BenchmarkSuite] = {}
        self._comparisons: dict[str, ComparisonResult] = {}
        self._evidence_bundles: dict[str, EvidenceBundle] = {}

    def store_experiment(self, exp_record: dict) -> None:
        with self._lock:
            self._experiments[exp_record["id"]] = exp_record

    def get_experiment(self, exp_id: str) -> dict | None:
        with self._lock:
            return self._experiments.get(exp_id)

    def list_experiments(self, limit: int = 100, status: str | None = None) -> list[dict]:
        with self._lock:
            exps = list(self._experiments.values())
            if status:
                exps = [e for e in exps if e.get("status") == status]
            exps.sort(key=lambda e: e.get("created_at", ""), reverse=True)
            return exps[:limit]

    def store_run(self, run: ExperimentRun) -> None:
        with self._lock:
            self._runs.setdefault(run.experiment_id, []).append(run)

    def get_runs(self, experiment_id: str) -> list[ExperimentRun]:
        with self._lock:
            return list(self._runs.get(experiment_id, []))

    def store_template(self, template: ExperimentTemplate) -> None:
        with self._lock:
            self._templates[template.id] = template

    def get_template(self, template_id: str) -> ExperimentTemplate | None:
        with self._lock:
            return self._templates.get(template_id)

    def list_templates(self, public_only: bool = False) -> list[ExperimentTemplate]:
        with self._lock:
            templates = list(self._templates.values())
            if public_only:
                templates = [t for t in templates if t.is_public]
            return templates

    def store_benchmark(self, suite: BenchmarkSuite) -> None:
        with self._lock:
            self._benchmarks[suite.id] = suite

    def get_benchmark(self, suite_id: str) -> BenchmarkSuite | None:
        with self._lock:
            return self._benchmarks.get(suite_id)

    def store_comparison(self, comp: ComparisonResult) -> None:
        with self._lock:
            self._comparisons[comp.comparison_id] = comp

    def get_comparison(self, comp_id: str) -> ComparisonResult | None:
        with self._lock:
            return self._comparisons.get(comp_id)

    def store_evidence_bundle(self, bundle: EvidenceBundle) -> None:
        with self._lock:
            self._evidence_bundles[bundle.bundle_id] = bundle

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundle | None:
        with self._lock:
            return self._evidence_bundles.get(bundle_id)

    def export_experiment(self, exp_id: str) -> dict | None:
        """Export full experiment package for portability."""
        with self._lock:
            exp = self._experiments.get(exp_id)
            if not exp:
                return None
            return {
                "experiment": exp,
                "runs": [r.to_dict() for r in self._runs.get(exp_id, [])],
                "templates": [t.to_dict() for t in self._templates.values() if t.id == exp.get("template_id")],
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "engine_version": ENGINE_VERSION,
            }

    def import_experiment(self, package: dict, new_name: str | None = None) -> str:
        """Import experiment package, optionally renaming."""
        with self._lock:
            exp = package["experiment"]
            if new_name:
                exp["name"] = new_name
            exp["id"] = f"exp-{uuid.uuid4().hex[:12]}"
            exp["status"] = "created"
            self._experiments[exp["id"]] = exp
            for run_data in package.get("runs", []):
                run = ExperimentRun(**run_data)
                run.experiment_id = exp["id"]
                self._runs.setdefault(exp["id"], []).append(run)
            return exp["id"]


# --- Comparison Engine ---

class ComparisonEngine:
    """Compare experiments across dimensions."""

    @staticmethod
    def compare_optimizers(
        baseline_run: ExperimentRun,
        candidate_runs: list[ExperimentRun],
        metrics: list[str] | None = None,
    ) -> ComparisonResult:
        metrics = metrics or ["energy", "runtime_ms", "approximation_gap"]
        comparison_metrics = {}
        for m in metrics:
            baseline_val = baseline_run.metrics.get(m)
            candidate_vals = {r.id: r.metrics.get(m) for r in candidate_runs}
            comparison_metrics[m] = {
                "baseline": baseline_val,
                "candidates": candidate_vals,
                "diff": {cid: (v - baseline_val) if baseline_val is not None and v is not None else None
                         for cid, v in candidate_vals.items()},
            }
        return ComparisonResult(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            type="optimizer",
            baseline_id=baseline_run.id,
            candidate_ids=[r.id for r in candidate_runs],
            metrics=comparison_metrics,
            summary=f"Compared {len(candidate_runs)} optimizer runs against baseline {baseline_run.id}",
        )

    @staticmethod
    def compare_models(
        baseline_run: ExperimentRun,
        candidate_runs: list[ExperimentRun],
        metrics: list[str] | None = None,
    ) -> ComparisonResult:
        metrics = metrics or ["energy", "robustness_gap", "uncertainty"]
        comparison_metrics = {}
        for m in metrics:
            baseline_val = baseline_run.metrics.get(m)
            candidate_vals = {r.id: r.metrics.get(m) for r in candidate_runs}
            comparison_metrics[m] = {
                "baseline": baseline_val,
                "candidates": candidate_vals,
                "diff": {cid: (v - baseline_val) if baseline_val is not None and v is not None else None
                         for cid, v in candidate_vals.items()},
            }
        return ComparisonResult(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            type="model",
            baseline_id=baseline_run.id,
            candidate_ids=[r.id for r in candidate_runs],
            metrics=comparison_metrics,
            summary=f"Compared {len(candidate_runs)} model runs against baseline {baseline_run.id}",
        )

    @staticmethod
    def compare_perturbations(
        baseline_run: ExperimentRun,
        candidate_runs: list[ExperimentRun],
        metrics: list[str] | None = None,
    ) -> ComparisonResult:
        metrics = metrics or ["worst_case_risk", "feasibility_rate", "robustness_margin"]
        comparison_metrics = {}
        for m in metrics:
            baseline_val = baseline_run.metrics.get(m)
            candidate_vals = {r.id: r.metrics.get(m) for r in candidate_runs}
            comparison_metrics[m] = {
                "baseline": baseline_val,
                "candidates": candidate_vals,
                "diff": {cid: (v - baseline_val) if baseline_val is not None and v is not None else None
                         for cid, v in candidate_vals.items()},
            }
        return ComparisonResult(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            type="perturbation",
            baseline_id=baseline_run.id,
            candidate_ids=[r.id for r in candidate_runs],
            metrics=comparison_metrics,
            summary=f"Compared {len(candidate_runs)} perturbation sets against baseline {baseline_run.id}",
        )

    @staticmethod
    def compare_robustness(
        baseline_run: ExperimentRun,
        candidate_runs: list[ExperimentRun],
    ) -> ComparisonResult:
        """Compare robustness: worst-case, feasibility, risk margins."""
        metrics = ["worst_case_risk", "feasible_under_all", "robustness_margin", "nominal_risk"]
        comparison_metrics = {}
        for m in metrics:
            baseline_val = baseline_run.metrics.get(m)
            candidate_vals = {r.id: r.metrics.get(m) for r in candidate_runs}
            comparison_metrics[m] = {
                "baseline": baseline_val,
                "candidates": candidate_vals,
                "diff": {cid: (v - baseline_val) if baseline_val is not None and v is not None else None
                         for cid, v in candidate_vals.items()},
            }
        return ComparisonResult(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            type="robustness",
            baseline_id=baseline_run.id,
            candidate_ids=[r.id for r in candidate_runs],
            metrics=comparison_metrics,
            summary=f"Robustness comparison: {len(candidate_runs)} candidates vs baseline",
        )

    @staticmethod
    def compare_regression(
        baseline_run: ExperimentRun,
        candidate_runs: list[ExperimentRun],
    ) -> ComparisonResult:
        """Regression comparison: detect degradations."""
        metrics = ["energy", "runtime_ms", "worst_case_risk", "feasible_under_all"]
        comparison_metrics = {}
        regressions = []
        for m in metrics:
            baseline_val = baseline_run.metrics.get(m)
            candidate_vals = {r.id: r.metrics.get(m) for r in candidate_runs}
            diff = {cid: (v - baseline_val) if baseline_val is not None and v is not None else None
                    for cid, v in candidate_vals.items()}
            comparison_metrics[m] = {"baseline": baseline_val, "candidates": candidate_vals, "diff": diff}
            # Detect regression (higher energy/risk = worse)
            if m in ("energy", "worst_case_risk", "runtime_ms"):
                for cid, d in diff.items():
                    if d is not None and d > 0:
                        regressions.append(f"{cid}: {m} degraded by {d:.4f}")
        return ComparisonResult(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            type="regression",
            baseline_id=baseline_run.id,
            candidate_ids=[r.id for r in candidate_runs],
            metrics=comparison_metrics,
            summary=f"Regression check: {len(regressions)} degradations found" if regressions else "No regressions detected",
        )


# --- Experiment Scheduler (local) ---

class ExperimentScheduler:
    """Local experiment scheduler for automated execution."""

    def __init__(self, runner_fn: Callable[[ExperimentSpec], dict]) -> None:
        self._runner_fn = runner_fn
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._running = False
        self._thread: threading.Thread | None = None

    def schedule(
        self,
        experiment_id: str,
        spec: ExperimentSpec,
        run_at: str | None = None,
        repeat: str | None = None,  # "daily", "hourly", None
    ) -> str:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "experiment_id": experiment_id,
                "spec": spec,
                "run_at": run_at,
                "repeat": repeat,
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_run": None,
                "next_run": run_at,
            }
        return job_id

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while self._running:
            now = datetime.now(timezone.utc).isoformat()
            with self._lock:
                for job in self._jobs.values():
                    if job["status"] == "scheduled" and job["next_run"] and job["next_run"] <= now:
                        job["status"] = "running"
                        # Execute in background
                        threading.Thread(target=self._execute_job, args=(job,), daemon=True).start()
            time.sleep(10)

    def _execute_job(self, job: dict) -> None:
        try:
            result = self._runner_fn(job["spec"])
            job["status"] = "succeeded"
            job["last_run"] = datetime.now(timezone.utc).isoformat()
            job["last_result"] = result
        except Exception as e:
            job["status"] = "failed"
            job["last_error"] = str(e)
        finally:
            if job["repeat"] == "hourly":
                job["next_run"] = (datetime.fromisoformat(job["next_run"]) + timedelta(hours=1)).isoformat()
            elif job["repeat"] == "daily":
                job["next_run"] = (datetime.fromisoformat(job["next_run"]) + timedelta(days=1)).isoformat()
            else:
                job["status"] = "completed"

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return list(self._jobs.values())


# --- Validation Functions ---

def validate_spec_payload(payload: dict) -> ExperimentSpec:
    """Validate an untrusted POST body into an ExperimentSpec."""
    if not isinstance(payload, dict):
        raise ValueError("experiment body must be a JSON object")
    name = payload.get("name", "")
    check_name(name)

    scenario_name = payload.get("scenario_name", "smart-building-emergency")
    scenario = payload.get("scenario")
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

    template_id = payload.get("template_id")
    template_version = payload.get("template_version")

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
        template_id=template_id,
        template_version=template_version,
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


# --- Reproducibility Verification ---

def verify_reproducibility(
    original_spec: ExperimentSpec,
    replay_result: dict,
    tolerance: float = 1e-6,
) -> dict:
    """Verify that a replay matches the original within tolerance."""
    original_fp = original_spec.fingerprint()
    replay_fp = replay_result.get("fingerprint", "")
    fingerprint_match = original_fp == replay_fp

    metrics_match = True
    metric_diffs = {}
    for key, val in original_spec.to_dict().items():
        if key in replay_result:
            if isinstance(val, (int, float)) and isinstance(replay_result[key], (int, float)):
                diff = abs(val - replay_result[key])
                metric_diffs[key] = diff
                if diff > tolerance:
                    metrics_match = False

    return {
        "fingerprint_match": fingerprint_match,
        "original_fingerprint": original_fp,
        "replay_fingerprint": replay_fp,
        "metrics_match": metrics_match,
        "metric_diffs": metric_diffs,
        "overall_pass": fingerprint_match and metrics_match,
    }


# Canonical instances
experiment_archive = ExperimentArchive()
comparison_engine = ComparisonEngine()

# --- Default Templates ---

DEFAULT_TEMPLATES = {
    "smoke-test": ExperimentTemplate(
        id="tmpl-smoke-test",
        name="Smoke Test",
        description="Quick validation with minimal perturbations",
        spec=ExperimentSpec(
            name="smoke-test",
            perturbations=(dict(smoke=2.0),),
            policy_variables=("route_a", "route_c", "stairwell_b"),
            optimizer="exact",
            backend="statevector-simulator",
            seed=42,
        ),
        tags=("smoke", "quick"),
        is_public=True,
    ),
    "full-robustness": ExperimentTemplate(
        id="tmpl-full-robustness",
        name="Full Robustness Suite",
        description="Complete perturbation set with all optimizers",
        spec=ExperimentSpec(
            name="full-robustness",
            perturbations=(
                {"smoke": 2.0},
                {"crowd": 80.0},
                {"smoke": 2.0, "crowd": 80.0},
                {"corridor_capacity": -70.0},
            ),
            policy_variables=("route_a", "route_c", "stairwell_b"),
            optimizer="exact",
            backend="statevector-simulator",
            seed=42,
        ),
        tags=("robustness", "full"),
        is_public=True,
    ),
    "qaoa-benchmark": ExperimentTemplate(
        id="tmpl-qaoa-benchmark",
        name="QAOA Benchmark",
        description="Compare QAOA variants against exact",
        spec=ExperimentSpec(
            name="qaoa-benchmark",
            perturbations=({"smoke": 2.0},),
            policy_variables=("route_a", "route_c", "stairwell_b"),
            optimizer="qaoa-expectation",
            backend="statevector-simulator",
            seed=123,
        ),
        tags=("qaoa", "benchmark"),
        is_public=True,
    ),
}

for t in DEFAULT_TEMPLATES.values():
    experiment_archive.store_template(t)


# --- Default Benchmarks ---

DEFAULT_BENCHMARK = BenchmarkSuite(
    id="bench-core",
    name="Core Optimization Benchmarks",
    description="Standard benchmarks for optimizer comparison",
    datasets=[
        BenchmarkDataset(
            id="ds-reference",
            name="Reference Instance",
            description="Standard smart-building-emergency instance",
            scenarios=[{
                "name": "smart-building-emergency",
                "initial_state": {"smoke": 10, "crowd": 200, "corridor_capacity": 50},
                "perturbations": [{"smoke": 2.0}, {"crowd": 80.0}],
                "policy_variables": ["route_a", "route_c", "stairwell_b"],
            }],
            expected_results={"exact": {"energy": -42.5, "gap": 0.0}},
            metadata={"size": "small", "type": "reference"},
        ),
    ],
    metrics=["energy", "runtime_ms", "approximation_gap", "worst_case_risk", "feasible_under_all"],
)

experiment_archive.store_benchmark(DEFAULT_BENCHMARK)