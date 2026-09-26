"""Performance & Scale: parallelization, caching, workers, scheduling (Phase 12).

Provides:
- Parallel execution of simulations, perturbations, policy evaluation
- Distributed simulation capability with worker pools
- Background job queues with prioritization
- Progress streaming for long-running operations
- Checkpointing and resumable simulations
- Deterministic caching (simulation results, optimizer results)
- Incremental recalculation
- Resource-aware scheduling (CPU/GPU/accelerator abstraction)
- Workload prioritization and resource limits
- Execution timeouts and graceful degradation
- Benchmarked performance targets
"""
from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import json
import os
import pickle
import threading
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


# --- Resource Types ---

class ResourceType(Enum):
    CPU = "cpu"
    GPU = "gpu"
    ACCELERATOR = "accelerator"


@dataclass(frozen=True)
class ResourceSpec:
    """Resource requirements for a task."""
    cpus: float = 1.0
    gpus: float = 0.0
    memory_mb: int = 512
    accelerator_type: str | None = None
    accelerator_count: int = 0

    def to_dict(self) -> dict:
        return {
            "cpus": self.cpus,
            "gpus": self.gpus,
            "memory_mb": self.memory_mb,
            "accelerator_type": self.accelerator_type,
            "accelerator_count": self.accelerator_count,
        }


@dataclass(frozen=True)
class WorkerSpec:
    """Worker specification."""
    worker_id: str
    resource_type: ResourceType
    resources: ResourceSpec
    labels: dict[str, str] = field(default_factory=dict)
    max_concurrent: int = 1

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "resource_type": self.resource_type.value,
            "resources": self.resources.to_dict(),
            "labels": self.labels,
            "max_concurrent": self.max_concurrent,
        }


# --- Task Definitions ---

@dataclass
class Task(Generic[T]):
    """A unit of work to be executed."""
    task_id: str
    func: Callable[..., T]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: int = 0  # higher = more urgent
    resource_spec: ResourceSpec = field(default_factory=ResourceSpec)
    timeout_s: float | None = None
    retry_count: int = 0
    max_retries: int = 3
    checkpoint_data: bytes | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __hash__(self):
        return hash(self.task_id)


@dataclass
class TaskResult(Generic[R]):
    """Result of a task execution."""
    task_id: str
    success: bool
    result: R | None = None
    error: str | None = None
    duration_ms: float = 0.0
    worker_id: str | None = None
    checkpoint_data: bytes | None = None
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "worker_id": self.worker_id,
            "completed_at": self.completed_at,
        }


# --- Deterministic Cache ---

class DeterministicCache:
    """Thread-safe deterministic cache with TTL and size limits."""

    def __init__(
        self,
        max_size: int = 10000,
        ttl_s: float | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (value, timestamp)
        self._access_order: list[str] = []  # LRU tracking
        self._max_size = max_size
        self._ttl_s = ttl_s
        self._cache_dir = cache_dir
        self._hits = 0
        self._misses = 0

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Create deterministic cache key from function and arguments."""
        content = json.dumps({
            "func": func_name,
            "args": args,
            "kwargs": kwargs,
        }, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, func_name: str, args: tuple, kwargs: dict) -> Any | None:
        """Get cached value if exists and not expired."""
        key = self._make_key(func_name, args, kwargs)
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if self._ttl_s is None or (time.time() - timestamp) < self._ttl_s:
                    self._hits += 1
                    # Update LRU
                    if key in self._access_order:
                        self._access_order.remove(key)
                    self._access_order.append(key)
                    return value
                else:
                    # Expired
                    del self._cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)
            self._misses += 1
            return None

    def set(self, func_name: str, args: tuple, kwargs: dict, value: Any) -> None:
        """Set cached value."""
        key = self._make_key(func_name, args, kwargs)
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Remove LRU
                lru_key = self._access_order.pop(0)
                if lru_key in self._cache:
                    del self._cache[lru_key]
            self._cache[key] = (value, time.time())
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def invalidate(self, func_name: str, args: tuple, kwargs: dict) -> bool:
        """Invalidate a specific cache entry."""
        key = self._make_key(func_name, args, kwargs)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


# --- Checkpointing ---

@dataclass
class Checkpoint:
    """Simulation checkpoint for resumability."""
    checkpoint_id: str
    simulation_id: str
    step: int
    state: dict
    metadata: dict
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            canonical = json.dumps({
                "simulation_id": self.simulation_id,
                "step": self.step,
                "state": self.state,
            }, sort_keys=True, separators=(",", ":"), default=str)
            self.fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CheckpointManager:
    """Manage simulation checkpoints for resumability."""

    def __init__(self, checkpoint_dir: Path | None = None) -> None:
        self._checkpoint_dir = checkpoint_dir or Path("./checkpoints")
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, checkpoint: Checkpoint) -> Path:
        """Save checkpoint to disk."""
        filename = f"{checkpoint.simulation_id}_step_{checkpoint.step:06d}_{checkpoint.checkpoint_id[:8]}.pkl"
        filepath = self._checkpoint_dir / filename
        with self._lock:
            with open(filepath, "wb") as f:
                pickle.dump(checkpoint, f)
        return filepath

    def load(self, simulation_id: str, step: int | None = None) -> Checkpoint | None:
        """Load latest checkpoint for simulation."""
        with self._lock:
            files = list(self._checkpoint_dir.glob(f"{simulation_id}_step_*.pkl"))
            if not files:
                return None
            if step is not None:
                files = [f for f in files if f"_step_{step:06d}_" in f.name]
            if not files:
                return None
            latest = max(files, key=lambda f: f.stat().st_mtime)
            with open(latest, "rb") as f:
                return pickle.load(f)

    def list_checkpoints(self, simulation_id: str) -> list[Checkpoint]:
        """List all checkpoints for a simulation."""
        with self._lock:
            files = list(self._checkpoint_dir.glob(f"{simulation_id}_step_*.pkl"))
            checkpoints = []
            for f in files:
                try:
                    with open(f, "rb") as fp:
                        cp = pickle.load(fp)
                        checkpoints.append(cp)
                except Exception:
                    pass
            return sorted(checkpoints, key=lambda c: c.step)


# --- Job Queue with Prioritization ---

class Priority:
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


class JobQueue:
    """Thread-safe priority job queue with worker pool."""

    def __init__(self, max_workers: int = None, use_processes: bool = False) -> None:
        self._queue: list[tuple[int, int, Task]] = []  # (-priority, seq, task)
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False
        self._executor: ThreadPoolExecutor | ProcessPoolExecutor
        if use_processes:
            self._executor = ProcessPoolExecutor(max_workers=max_workers or os.cpu_count())
        else:
            self._executor = ThreadPoolExecutor(max_workers=max_workers or os.cpu_count())
        self._futures: dict[str, concurrent.futures.Future] = {}
        self._results: dict[str, TaskResult] = {}
        self._results_lock = threading.Lock()

    def submit(self, task: Task) -> str:
        """Submit a task to the queue."""
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Queue is shutdown")
            self._seq += 1
            heapq_entry = (-task.priority, self._seq, task)
            self._queue.append(heapq_entry)
            self._queue.sort(key=lambda x: (x[0], x[1]))  # priority, then FIFO
            self._condition.notify()
            return task.task_id

    def submit_batch(self, tasks: list[Task]) -> list[str]:
        """Submit multiple tasks."""
        return [self.submit(t) for t in tasks]

    def _worker_loop(self) -> None:
        """Worker loop that processes tasks."""
        while True:
            with self._condition:
                while not self._queue and not self._shutdown:
                    self._condition.wait(timeout=1.0)
                if self._shutdown and not self._queue:
                    return
                if not self._queue:
                    continue
                _, _, task = self._queue.pop(0)

            # Execute task
            start = time.time()
            try:
                result = task.func(*task.args, **task.kwargs)
                duration_ms = (time.time() - start) * 1000
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=True,
                    result=result,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                if task.retry_count < task.max_retries:
                    # Re-queue with incremented retry count
                    task.retry_count += 1
                    self.submit(task)
                    continue
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(e),
                    duration_ms=duration_ms,
                )

            with self._results_lock:
                self._results[task.task_id] = task_result

    def start_workers(self, num_workers: int = None) -> None:
        """Start worker threads."""
        num_workers = num_workers or self._executor._max_workers
        for _ in range(num_workers):
            self._executor.submit(self._worker_loop)

    def get_result(self, task_id: str, timeout: float | None = None) -> TaskResult | None:
        """Get task result, blocking until available."""
        start = time.time()
        while True:
            with self._results_lock:
                if task_id in self._results:
                    return self._results.pop(task_id)
            if timeout and (time.time() - start) > timeout:
                return None
            time.sleep(0.01)

    def wait_all(self, task_ids: list[str], timeout: float | None = None) -> dict[str, TaskResult]:
        """Wait for all tasks to complete."""
        results = {}
        remaining = set(task_ids)
        start = time.time()
        while remaining:
            with self._results_lock:
                for tid in list(remaining):
                    if tid in self._results:
                        results[tid] = self._results.pop(tid)
                        remaining.remove(tid)
            if not remaining:
                break
            if timeout and (time.time() - start) > timeout:
                break
            time.sleep(0.01)
        return results

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the queue."""
        with self._condition:
            self._shutdown = True
            self._condition.notify_all()
        self._executor.shutdown(wait=wait)


import heapq  # for priority queue


# --- Parallel Execution Helpers ---

def parallel_map(
    func: Callable[[T], R],
    items: list[T],
    max_workers: int | None = None,
    use_processes: bool = False,
    chunk_size: int = 1,
    timeout: float | None = None,
) -> list[R | Exception]:
    """Map function over items in parallel."""
    if use_processes:
        executor = ProcessPoolExecutor(max_workers=max_workers)
    else:
        executor = ThreadPoolExecutor(max_workers=max_workers)

    try:
        futures = []
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            futures.append(executor.submit(_map_chunk, func, chunk))

        results = []
        for f in as_completed(futures, timeout=timeout):
            try:
                results.extend(f.result())
            except Exception as e:
                results.append(e)
        return results
    finally:
        executor.shutdown(wait=True)


def _map_chunk(func: Callable[[T], R], items: list[T]) -> list[R]:
    return [func(item) for item in items]


def parallel_simulations(
    scenario_factory: Callable[[], Any],
    num_simulations: int,
    max_workers: int | None = None,
    use_processes: bool = False,
    seed_base: int = 0,
) -> list[Any]:
    """Run multiple simulations in parallel with different seeds."""
    def run_sim(i: int) -> Any:
        scenario = scenario_factory()
        if hasattr(scenario, "seed"):
            scenario.seed = seed_base + i
        return scenario.run()

    return parallel_map(run_sim, list(range(num_simulations)), max_workers, use_processes)


def parallel_perturbations(
    base_state: dict,
    perturbations: list[dict],
    transition_fn: Callable[[dict, dict], dict],
    max_workers: int | None = None,
) -> list[dict]:
    """Apply perturbations in parallel."""
    def apply_pert(p: dict) -> dict:
        state = {**base_state}
        state.update(p)
        return transition_fn(state, {})

    return parallel_map(apply_pert, perturbations, max_workers)


def parallel_policy_evaluation(
    policies: list[dict],
    evaluate_fn: Callable[[dict], float],
    max_workers: int | None = None,
) -> list[float]:
    """Evaluate multiple policies in parallel."""
    return parallel_map(evaluate_fn, policies, max_workers)


# --- Resource-Aware Scheduler ---

class ResourceScheduler:
    """Schedule tasks based on available resources."""

    def __init__(self, total_resources: ResourceSpec) -> None:
        self._total = total_resources
        self._allocated = ResourceSpec(0, 0, 0)
        self._lock = threading.Lock()

    def can_allocate(self, spec: ResourceSpec) -> bool:
        """Check if resources are available."""
        with self._lock:
            return (
                self._allocated.cpus + spec.cpus <= self._total.cpus and
                self._allocated.gpus + spec.gpus <= self._total.gpus and
                self._allocated.memory_mb + spec.memory_mb <= self._total.memory_mb
            )

    def allocate(self, spec: ResourceSpec) -> bool:
        """Allocate resources."""
        with self._lock:
            if self.can_allocate(spec):
                self._allocated.cpus += spec.cpus
                self._allocated.gpus += spec.gpus
                self._allocated.memory_mb += spec.memory_mb
                return True
            return False

    def release(self, spec: ResourceSpec) -> None:
        """Release resources."""
        with self._lock:
            self._allocated.cpus = max(0, self._allocated.cpus - spec.cpus)
            self._allocated.gpus = max(0, self._allocated.gpus - spec.gpus)
            self._allocated.memory_mb = max(0, self._allocated.memory_mb - spec.memory_mb)

    def available(self) -> ResourceSpec:
        """Get available resources."""
        with self._lock:
            return ResourceSpec(
                cpus=self._total.cpus - self._allocated.cpus,
                gpus=self._total.gpus - self._allocated.gpus,
                memory_mb=self._total.memory_mb - self._allocated.memory_mb,
            )

    def utilization(self) -> dict:
        """Get resource utilization."""
        with self._lock:
            return {
                "cpu": self._allocated.cpus / self._total.cpus if self._total.cpus > 0 else 0,
                "gpu": self._allocated.gpus / self._total.gpus if self._total.gpus > 0 else 0,
                "memory": self._allocated.memory_mb / self._total.memory_mb if self._total.memory_mb > 0 else 0,
            }


# --- Incremental Recalculation ---

class IncrementalCache:
    """Cache for incremental recalculation with dependency tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, Any] = {}
        self._dependencies: dict[str, set[str]] = {}  # key -> set of keys it depends on
        self._dependents: dict[str, set[str]] = {}  # key -> set of keys that depend on it
        self._timestamps: dict[str, float] = {}

    def set(self, key: str, value: Any, depends_on: list[str] | None = None) -> None:
        """Set a value with its dependencies."""
        with self._lock:
            self._values[key] = value
            self._timestamps[key] = time.time()
            deps = set(depends_on or [])
            self._dependencies[key] = deps
            for dep in deps:
                self._dependents.setdefault(dep, set()).add(key)

    def get(self, key: str) -> Any | None:
        """Get a value."""
        with self._lock:
            return self._values.get(key)

    def invalidate(self, key: str) -> list[str]:
        """Invalidate a key and all its dependents. Returns list of invalidated keys."""
        with self._lock:
            invalidated = []
            to_invalidate = {key}
            while to_invalidate:
                k = to_invalidate.pop()
                if k in self._values:
                    del self._values[k]
                    invalidated.append(k)
                to_invalidate.update(self._dependents.get(k, set()))
            return invalidated

    def get_stale_keys(self, max_age_s: float) -> list[str]:
        """Get keys older than max_age_s."""
        with self._lock:
            now = time.time()
            return [k for k, ts in self._timestamps.items() if now - ts > max_age_s]


# --- Performance Benchmarks ---

@dataclass(frozen=True)
class PerformanceTarget:
    """Performance target for a benchmark."""
    name: str
    operation: str
    target_ms: float
    max_ms: float
    throughput_per_s: float | None = None


@dataclass(frozen=True)
class BenchmarkResult:
    """Result of a performance benchmark."""
    target: PerformanceTarget
    actual_ms: float
    actual_throughput: float | None
    passed: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "target": {
                "name": self.target.name,
                "operation": self.target.operation,
                "target_ms": self.target.target_ms,
                "max_ms": self.target.max_ms,
                "throughput_per_s": self.target.throughput_per_s,
            },
            "actual_ms": self.actual_ms,
            "actual_throughput": self.actual_throughput,
            "passed": self.passed,
            "timestamp": self.timestamp,
            "details": self.details,
        }


DEFAULT_PERFORMANCE_TARGETS = [
    PerformanceTarget("demo_latency", "demo", 5000, 10000, 10),
    PerformanceTarget("twin_update", "twin_update", 100, 500, 100),
    PerformanceTarget("counterfactual_generation", "counterfactuals", 200, 1000, 50),
    PerformanceTarget("robust_ranking", "robust_ranking", 500, 2000, 20),
    PerformanceTarget("guardian_verification", "guardian", 50, 200, 500),
    PerformanceTarget("api_health", "health", 10, 50, 1000),
    PerformanceTarget("api_meta", "meta", 20, 100, 500),
]


def run_performance_benchmarks(
    targets: list[PerformanceTarget] | None = None,
    iterations: int = 10,
) -> list[BenchmarkResult]:
    """Run performance benchmarks against targets."""
    targets = targets or DEFAULT_PERFORMANCE_TARGETS
    results = []

    for target in targets:
        # Warmup
        for _ in range(3):
            _run_operation(target.operation)

        # Timed runs
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            _run_operation(target.operation)
            times.append((time.perf_counter() - start) * 1000)

        avg_ms = sum(times) / len(times)
        max_ms = max(times)
        throughput = 1000 / avg_ms if avg_ms > 0 else 0

        passed = avg_ms <= target.target_ms and max_ms <= target.max_ms
        if target.throughput_per_s:
            passed = passed and throughput >= target.throughput_per_s

        results.append(BenchmarkResult(
            target=target,
            actual_ms=avg_ms,
            actual_throughput=throughput,
            passed=passed,
            details={"min_ms": min(times), "max_ms": max_ms, "p50_ms": sorted(times)[len(times)//2]},
        ))

    return results


def _run_operation(operation: str) -> None:
    """Run a dummy operation for benchmarking."""
    # In real implementation, this would call actual RIFT operations
    time.sleep(0.001)  # Simulate work


# --- Graceful Degradation ---

class DegradationManager:
    """Manage graceful degradation under load."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._degradation_level = 0  # 0 = normal, 1 = reduced, 2 = minimal
        self._max_level = 2

    @property
    def level(self) -> int:
        with self._lock:
            return self._degradation_level

    def set_level(self, level: int) -> None:
        with self._lock:
            self._degradation_level = max(0, min(level, self._max_level))

    def should_degrade(self, metric: str, value: float, threshold: float) -> bool:
        """Check if degradation should be triggered."""
        return value > threshold

    def get_config(self) -> dict:
        """Get current degradation config."""
        with self._lock:
            return {
                "level": self._degradation_level,
                "max_perturbations": [20, 10, 5][self._degradation_level],
                "max_futures": [100, 50, 20][self._degradation_level],
                "max_tree_depth": [10, 5, 3][self._degradation_level],
                "enable_3d": self._degradation_level == 0,
                "enable_detailed_logging": self._degradation_level < 2,
            }


# Canonical instances
simulation_cache = DeterministicCache(max_size=5000, ttl_s=3600)
optimizer_cache = DeterministicCache(max_size=2000, ttl_s=7200)
checkpoint_manager = CheckpointManager()
job_queue = JobQueue()
resource_scheduler = ResourceScheduler(ResourceSpec(cpus=os.cpu_count() or 4, memory_mb=4096))
incremental_cache = IncrementalCache()
degradation_manager = DegradationManager()


# --- Context Managers for Resource Management ---

class TaskContext:
    """Context manager for task execution with resource tracking."""

    def __init__(
        self,
        task: Task,
        scheduler: ResourceScheduler,
        cache: DeterministicCache | None = None,
    ) -> None:
        self.task = task
        self.scheduler = scheduler
        self.cache = cache
        self._allocated = False
        self.start_time = 0.0

    def __enter__(self) -> "TaskContext":
        self.start_time = time.time()
        self._allocated = self.scheduler.allocate(self.task.resource_spec)
        if not self._allocated:
            raise RuntimeError(f"Failed to allocate resources for task {self.task.task_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (time.time() - self.start_time) * 1000
        if self._allocated:
            self.scheduler.release(self.task.resource_spec)
        # Could record metrics here


def cached_computation(cache: DeterministicCache, func_name: str | None = None):
    """Decorator for caching function results."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            name = func_name or func.__name__
            cached = cache.get(name, args, kwargs)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(name, args, kwargs, result)
            return result
        return wrapper
    return decorator