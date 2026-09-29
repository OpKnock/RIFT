"""Data-driven state estimation for scenario world models (numpy-only).

Where an analytical transition exists but is rough (e.g. the deterministic
dither in the traffic/powergrid transitions), a small MLP surrogate can
learn the smooth dynamics from simulated rollouts. The estimator NEVER
replaces the analytical model silently:

- every prediction carries provenance (``source`` is ``"neural"`` or
  ``"analytical-fallback"``),
- predictions far from the training hull abstain back to the analytical
  transition instead of extrapolating,
- training is fully deterministic (fixed seed, fixed schedule), so two
  fits on the same data produce bitwise-identical weights,
- the clinical twin (``rift.health.twin``) is intentionally NOT wired to
  this: patient-state estimation stays analytical until governed
  clinical validation exists (see V7).

Only numpy is required; no torch/TF/JAX dependency is introduced.
"""
from __future__ import annotations

import math

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy is a hard repo dependency
    _np = None


def _require_numpy():
    if _np is None:
        raise ImportError("numpy is required for neural state estimation")
    return _np


def _tanh(np, z):
    return np.tanh(z)


def _tanh_derivative(np, z):
    t = np.tanh(z)
    return 1.0 - t * t


class MLPRegressor:
    """Tiny deterministic MLP for regression (full-batch gradient descent)."""

    def __init__(self, layers: tuple, seed: int = 7):
        np = _require_numpy()
        if len(layers) < 3:
            raise ValueError("layers must be (in, hidden..., out)")
        self.layers = tuple(int(v) for v in layers)
        self.seed = int(seed)
        rng = np.random.default_rng(self.seed)
        self.weights = []
        self.biases = []
        for fan_in, fan_out in zip(self.layers[:-1], self.layers[1:]):
            scale = math.sqrt(2.0 / (fan_in + fan_out))
            self.weights.append(rng.normal(0.0, scale, size=(fan_in, fan_out)))
            self.biases.append(np.zeros(fan_out))

    def forward(self, x):
        np = _require_numpy()
        activations = [np.asarray(x, dtype=float)]
        pre_activations = []
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            z = activations[-1] @ w + b
            pre_activations.append(z)
            activations.append(_tanh(np, z) if i < len(self.weights) - 1 else z)
        return activations, pre_activations

    def predict(self, x):
        activations, _ = self.forward(x)
        return activations[-1]

    def fit(self, x, y, iterations: int = 400, learning_rate: float = 0.05) -> dict:
        np = _require_numpy()
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.ndim != 2 or y.ndim != 2 or x.shape[0] != y.shape[0] or x.shape[0] == 0:
            raise ValueError("x and y must be non-empty 2D arrays with matching rows")
        if x.shape[1] != self.layers[0] or y.shape[1] != self.layers[-1]:
            raise ValueError("data width does not match network layers")
        n = x.shape[0]
        initial = float(np.mean((self.predict(x) - y) ** 2))
        for _ in range(int(iterations)):
            activations, pre_activations = self.forward(x)
            delta = (2.0 / n) * (activations[-1] - y)
            for i in reversed(range(len(self.weights))):
                grad_w = activations[i].T @ delta
                grad_b = delta.sum(axis=0)
                if i > 0:
                    delta = (delta @ self.weights[i].T) * _tanh_derivative(np, pre_activations[i - 1])
                # Clip for stability on steep surrogate targets.
                grad_w = np.clip(grad_w, -5.0, 5.0)
                grad_b = np.clip(grad_b, -5.0, 5.0)
                self.weights[i] -= learning_rate * grad_w
                self.biases[i] -= learning_rate * grad_b
        final = float(np.mean((self.predict(x) - y) ** 2))
        return {"initial_mse": initial, "final_mse": final, "iterations": int(iterations)}


def rollout_dataset(scenario, policies: list, steps: int = 6) -> tuple:
    """Deterministic (x, y) pairs: x=[state..., policy...], y=next state.

    Starts from the scenario's initial state and rolls each policy forward
    ``steps`` transitions. Feature order follows sorted state keys so it is
    stable across runs; policy order follows sorted policy keys.
    """
    np = _require_numpy()
    state_keys = sorted(scenario.initial_state.keys())
    policy_keys = sorted({k for p in policies for k in p.keys()})
    xs, ys = [], []
    for policy in policies:
        full_policy = {k: float(policy.get(k, 0.0)) for k in policy_keys}
        state = dict(scenario.initial_state)
        for _ in range(max(1, int(steps))):
            nxt = scenario.transition(dict(state), dict(full_policy))
            xs.append([float(state[k]) for k in state_keys] +
                      [float(full_policy[k]) for k in policy_keys])
            ys.append([float(nxt[k]) for k in state_keys])
            state = nxt
    return np.array(xs), np.array(ys), state_keys, policy_keys


def _normalize(np, x, mean, scale):
    return (x - mean) / scale


def fit_world_estimator(scenario, policies: list, seed: int = 7,
                        hidden: tuple = (16, 16), iterations: int = 400,
                        abstain_quantile: float = 0.99) -> dict:
    """Fit a surrogate for ``scenario.transition`` and return a bundle.

    The bundle is JSON-safe except for the fitted ``model`` object itself.
    ``abstain_distance`` is the training-hull distance quantile above which
    predictions abstain back to the analytical transition.
    """
    np = _require_numpy()
    x_raw, y_raw, state_keys, policy_keys = rollout_dataset(scenario, policies)
    x_mean, x_scale = x_raw.mean(axis=0), x_raw.std(axis=0)
    y_mean, y_scale = y_raw.mean(axis=0), y_raw.std(axis=0)
    x_scale[x_scale == 0.0] = 1.0
    y_scale[y_scale == 0.0] = 1.0
    model = MLPRegressor((x_raw.shape[1],) + tuple(hidden) + (y_raw.shape[1],), seed=seed)
    stats = model.fit(_normalize(np, x_raw, x_mean, x_scale),
                      _normalize(np, y_raw, y_mean, y_scale),
                      iterations=iterations)
    train_pred = (model.predict(_normalize(np, x_raw, x_mean, x_scale)) * y_scale + y_mean)
    residuals = np.abs(train_pred - y_raw).max(axis=1)
    distances = np.sqrt(((_normalize(np, x_raw, x_mean, x_scale) ** 2)).sum(axis=1))
    return {
        "model": model,
        "scenario_name": getattr(scenario, "name", "unknown"),
        "seed": int(seed),
        "state_keys": state_keys,
        "policy_keys": policy_keys,
        "x_mean": x_mean.tolist(),
        "x_scale": x_scale.tolist(),
        "y_mean": y_mean.tolist(),
        "y_scale": y_scale.tolist(),
        "train_mse": stats["final_mse"],
        "train_residual_max": float(residuals.max()),
        "abstain_distance": float(np.quantile(distances, abstain_quantile)),
        "train_rows": int(x_raw.shape[0]),
    }


def predict_with_estimator(bundle: dict, scenario, state: dict, policy: dict) -> dict:
    """Predict next state; abstain to analytical when far from training data."""
    np = _require_numpy()
    model = bundle["model"]
    state_keys, policy_keys = bundle["state_keys"], bundle["policy_keys"]
    x = np.array([[float(state.get(k, 0.0)) for k in state_keys] +
                  [float(policy.get(k, 0.0)) for k in policy_keys]])
    x_mean = np.array(bundle["x_mean"])
    x_scale = np.array(bundle["x_scale"])
    distance = float(np.sqrt((((x - x_mean) / x_scale) ** 2).sum()))
    if distance > float(bundle["abstain_distance"]):
        analytical = scenario.transition(dict(state), {k: float(policy.get(k, 0.0)) for k in policy_keys})
        return {"prediction": {k: float(analytical.get(k, 0.0)) for k in state_keys},
                "source": "analytical-fallback",
                "abstained": True,
                "distance": distance,
                "abstain_distance": float(bundle["abstain_distance"]),
                "provenance": {"estimator": "analytical-transition",
                               "reason": "outside training hull"}}
    xn = (x - x_mean) / x_scale
    y = model.predict(xn) * np.array(bundle["y_scale"]) + np.array(bundle["y_mean"])
    return {"prediction": {k: float(v) for k, v in zip(state_keys, y[0].tolist())},
            "source": "neural",
            "abstained": False,
            "distance": distance,
            "abstain_distance": float(bundle["abstain_distance"]),
            "provenance": {"estimator": "mlp-surrogate",
                           "scenario": bundle["scenario_name"],
                           "seed": bundle["seed"],
                           "train_mse": bundle["train_mse"]}}
