"""Python SDK for RIFT API."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from urllib.parse urljoin

import httpx
import websockets

from .. import __version__ as SDK_VERSION


@dataclass
class RiftConfig:
    """SDK configuration."""
    base_url: str = "http://localhost:8080"
    api_key: str | None = None
    jwt_token: str | None = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True


@dataclass
class HealthStatus:
    status: str
    engine: str
    version: str
    quantum_backend: str
    persistence: dict
    billing: dict


@dataclass
class EngineMeta:
    engine: str
    engine_version: str
    quantum_backend: str
    capabilities: list[str]
    optimizers: list[str]
    backends: list[str]
    limits: dict
    auth: dict


@dataclass
class DemoParams:
    crowd: int | None = None
    smoke: int | None = None
    corridor_capacity: int | None = None
    block_b: bool = False


@dataclass
class DemoResult:
    scenario: dict
    futures: list[dict]
    robust: list[dict]
    robust_optimization: dict
    multivariable: dict
    benchmark: list[dict]
    guardian: dict
    reproducibility: dict
    future_tree: list[dict]
    causal_graph: dict
    uncertainty: dict


@dataclass
class ExperimentSpec:
    name: str
    scenario_name: str = "smart-building-emergency"
    initial_state: dict | None = None
    perturbations: list[dict] | None = None
    policy_variables: list[str] | None = None
    optimizer: str = "exact"
    backend: str = "statevector-simulator"
    seed: int | None = None
    description: str = ""


@dataclass
class Experiment:
    id: str
    name: str
    scenario_name: str
    status: str
    created_at: str
    spec: ExperimentSpec
    versions: list[dict] | None = None
    runs: list[dict] | None = None


@dataclass
class Run:
    id: str
    experiment_id: str
    optimizer: str
    metrics: dict
    result: dict | None
    seed: int | None
    status: str
    created_at: str


@dataclass
class TwinSnapshot:
    day_index: int
    patient_id: str
    state: dict
    risk: dict
    guardian: dict
    futures: dict
    trajectories: list[dict]
    provenance: dict


class RiftError(Exception):
    """Base RIFT SDK error."""
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RiftAuthenticationError(RiftError):
    """Authentication failed."""
    pass


class RiftRateLimitError(RiftError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class RiftClient:
    """Synchronous RIFT API client."""

    def __init__(self, config: RiftConfig | None = None):
        self.config = config or RiftConfig()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        )
        self._setup_auth()

    def _setup_auth(self) -> None:
        if self.config.api_key:
            self._client.headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif self.config.jwt_token:
            self._client.headers["Authorization"] = f"Bearer {self.config.jwt_token}"

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._client.request(method, url, **kwargs)
                if response.status_code == 401:
                    raise RiftAuthenticationError("Authentication failed", 401)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", self.config.retry_delay))
                    if attempt < self.config.max_retries:
                        time.sleep(retry_after)
                        continue
                    raise RiftRateLimitError("Rate limit exceeded", retry_after)
                response.raise_for_status()
                return response
            except httpx.TimeoutException:
                if attempt == self.config.max_retries:
                    raise RiftError("Request timeout")
                time.sleep(self.config.retry_delay * (2 ** attempt))
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay * (2 ** attempt))
                    continue
                raise RiftError(f"HTTP {e.response.status_code}", e.response.status_code, e.response.json())
        raise RiftError("Max retries exceeded")

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params).json()

    def _post(self, path: str, json: dict | None = None) -> dict:
        return self._request("POST", path, json=json).json()

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path).json()

    # --- Health & Meta ---
    def health(self) -> HealthStatus:
        return HealthStatus(**self._get("/api/health"))

    def meta(self) -> EngineMeta:
        return EngineMeta(**self._get("/api/meta"))

    # --- Demo ---
    def run_demo(self, params: DemoParams | None = None) -> DemoResult:
        p = params or DemoParams()
        query = {}
        if p.crowd is not None: query["crowd"] = str(p.crowd)
        if p.smoke is not None: query["smoke"] = str(p.smoke)
        if p.corridor_capacity is not None: query["corridor_capacity"] = str(p.corridor_capacity)
        if p.block_b: query["block_b"] = "1"
        return DemoResult(**self._get("/api/demo", params=query))

    # --- Experiments ---
    def create_experiment(self, spec: ExperimentSpec) -> Experiment:
        return Experiment(**self._post("/api/experiments", json=spec.__dict__))

    def get_experiment(self, experiment_id: str) -> Experiment:
        return Experiment(**self._get(f"/api/experiments/{experiment_id}"))

    def list_experiments(self, status: str | None = None, limit: int = 100) -> list[Experiment]:
        params = {"limit": str(limit)}
        if status: params["status"] = status
        return [Experiment(**e) for e in self._get("/api/experiments", params=params)]

    def delete_experiment(self, experiment_id: str) -> None:
        self._delete(f"/api/experiments/{experiment_id}")

    def create_experiment_version(self, experiment_id: str, spec: ExperimentSpec, version: int, description: str = "") -> dict:
        return self._post(f"/api/experiments/{experiment_id}/versions", json={
            "spec": spec.__dict__,
            "version": version,
            "description": description,
        })

    def get_experiment_versions(self, experiment_id: str) -> list[dict]:
        return self._get(f"/api/experiments/{experiment_id}/versions")

    # --- Runs ---
    def create_run(self, experiment_id: str, optimizer: str, metrics: dict, result: dict | None = None, seed: int | None = None) -> Run:
        return Run(**self._post(f"/api/experiments/{experiment_id}/runs", json={
            "optimizer": optimizer,
            "metrics": metrics,
            "result": result,
            "seed": seed,
        }))

    def get_run(self, run_id: str) -> Run:
        return Run(**self._get(f"/api/runs/{run_id}"))

    def list_runs(self, experiment_id: str) -> list[Run]:
        return [Run(**r) for r in self._get(f"/api/experiments/{experiment_id}/runs")]

    # --- Comparisons ---
    def compare(
        self,
        comparison_type: str,
        baseline_id: str,
        candidate_ids: list[str],
    ) -> dict:
        return self._post("/api/experiments/compare", json={
            "type": comparison_type,
            "baseline_id": baseline_id,
            "candidate_ids": candidate_ids,
        })

    # --- Templates ---
    def list_templates(self) -> list[dict]:
        return self._get("/api/experiments/templates")

    def get_template(self, template_id: str) -> dict:
        return self._get(f"/api/experiments/templates/{template_id}")

    def create_template(self, name: str, spec: ExperimentSpec, description: str = "", version: str = "1.0.0", tags: list[str] | None = None, is_public: bool = False) -> dict:
        return self._post("/api/experiments/templates", json={
            "name": name,
            "spec": spec.__dict__,
            "description": description,
            "version": version,
            "tags": tags or [],
            "is_public": is_public,
        })

    # --- Benchmarks ---
    def list_benchmarks(self) -> list[dict]:
        return self._get("/api/experiments/benchmarks")

    # --- Evidence ---
    def get_evidence(self, experiment_id: str) -> list[dict]:
        return self._get(f"/api/experiments/{experiment_id}/evidence")

    # --- Export/Import ---
    def export_experiment(self, experiment_id: str) -> dict:
        return self._get(f"/api/experiments/{experiment_id}/export")

    def import_experiment(self, package: dict, name: str | None = None) -> dict:
        return self._post("/api/experiments/import", json={"package": package, "name": name})

    # --- Replay ---
    def replay_experiment(self, experiment_id: str) -> dict:
        return self._get(f"/api/experiments/{experiment_id}/replay")

    # --- Snapshots ---
    def get_snapshot(self, experiment_id: str) -> dict:
        return self._get(f"/api/experiments/{experiment_id}/snapshots")

    # --- Digital Twin ---
    def get_twin_demo(self, day: int) -> TwinSnapshot:
        return TwinSnapshot(**self._get("/api/twin/demo", params={"t": str(day)}))

    def get_twin_evidence(self) -> dict:
        return self._get("/api/twin/evidence")

    # --- Operations ---
    def get_monitor(self) -> dict:
        return self._get("/api/ops/monitor")

    def get_incidents(self, status: str | None = None, severity: str | None = None, type: str | None = None) -> list[dict]:
        params = {}
        if status: params["status"] = status
        if severity: params["severity"] = severity
        if type: params["type"] = type
        return self._get("/api/operations/incidents", params=params)

    def create_incident(self, type: str, severity: str, title: str, description: str, trigger_alert_id: str | None = None, tags: list[str] | None = None) -> dict:
        return self._post("/api/operations/incidents", json={
            "type": type, "severity": severity, "title": title,
            "description": description, "trigger_alert_id": trigger_alert_id, "tags": tags or [],
        })

    def incident_action(self, incident_id: str, action: str, note: str) -> dict:
        return self._post(f"/api/operations/incidents/{incident_id}/action", json={"action": action, "note": note})

    def get_decisions(self, status: str | None = None, scenario_id: str | None = None) -> list[dict]:
        params = {}
        if status: params["status"] = status
        if scenario_id: params["scenario_id"] = scenario_id
        return self._get("/api/operations/decisions", params=params)

    def decision_action(self, decision_id: str, action: str, note: str) -> dict:
        return self._post(f"/api/operations/decisions/{decision_id}/action", json={"action": action, "note": note})

    # --- Explainability ---
    def get_explainability_audit(self) -> dict:
        return self._get("/api/explainability/audit")

    def get_explainability_evidence(self) -> dict:
        return self._get("/api/explainability/evidence")

    # --- Billing ---
    def get_billing_status(self) -> dict:
        return self._get("/api/billing/status")

    def get_entitlement(self) -> dict:
        return self._get("/api/billing/entitlement")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RiftClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


class RiftAsyncClient:
    """Asynchronous RIFT API client."""

    def __init__(self, config: RiftConfig | None = None):
        self.config = config or RiftConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            self._setup_auth()
        return self._client

    def _setup_auth(self) -> None:
        if self._client:
            if self.config.api_key:
                self._client.headers["Authorization"] = f"Bearer {self.config.api_key}"
            elif self.config.jwt_token:
                self._client.headers["Authorization"] = f"Bearer {self.config.jwt_token}"

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        url = urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code == 401:
                    raise RiftAuthenticationError("Authentication failed", 401)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", self.config.retry_delay))
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RiftRateLimitError("Rate limit exceeded", retry_after)
                response.raise_for_status()
                return response
            except httpx.TimeoutException:
                if attempt == self.config.max_retries:
                    raise RiftError("Request timeout")
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    continue
                raise RiftError(f"HTTP {e.response.status_code}", e.response.status_code, e.response.json())
        raise RiftError("Max retries exceeded")

    async def _get(self, path: str, params: dict | None = None) -> dict:
        return (await self._request("GET", path, params=params)).json()

    async def _post(self, path: str, json: dict | None = None) -> dict:
        return (await self._request("POST", path, json=json)).json()

    async def _delete(self, path: str) -> dict:
        return (await self._request("DELETE", path)).json()

    # Async versions of all sync methods...
    async def health(self) -> HealthStatus:
        return HealthStatus(**await self._get("/api/health"))

    async def meta(self) -> EngineMeta:
        return EngineMeta(**await self._get("/api/meta"))

    async def run_demo(self, params: DemoParams | None = None) -> DemoResult:
        p = params or DemoParams()
        query = {}
        if p.crowd is not None: query["crowd"] = str(p.crowd)
        if p.smoke is not None: query["smoke"] = str(p.smoke)
        if p.corridor_capacity is not None: query["corridor_capacity"] = str(p.corridor_capacity)
        if p.block_b: query["block_b"] = "1"
        return DemoResult(**await self._get("/api/demo", params=query))

    async def create_experiment(self, spec: ExperimentSpec) -> Experiment:
        return Experiment(**await self._post("/api/experiments", json=spec.__dict__))

    async def get_experiment(self, experiment_id: str) -> Experiment:
        return Experiment(**await self._get(f"/api/experiments/{experiment_id}"))

    async def list_experiments(self, status: str | None = None, limit: int = 100) -> list[Experiment]:
        params = {"limit": str(limit)}
        if status: params["status"] = status
        return [Experiment(**e) for e in await self._get("/api/experiments", params=params)]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "RiftAsyncClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()


# --- Convenience Functions ---

def create_client(
    base_url: str = "http://localhost:8080",
    api_key: str | None = None,
    **kwargs
) -> RiftClient:
    """Create a configured RiftClient."""
    return RiftClient(RiftConfig(base_url=base_url, api_key=api_key, **kwargs))


async def create_async_client(
    base_url: str = "http://localhost:8080",
    api_key: str | None = None,
    **kwargs
) -> RiftAsyncClient:
    """Create a configured RiftAsyncClient."""
    return RiftAsyncClient(RiftConfig(base_url=base_url, api_key=api_key, **kwargs))