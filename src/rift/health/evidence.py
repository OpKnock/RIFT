"""Versioned evidence bundles: one artifact per validation claim.

A bundle joins metrics, calibration, model identity, dataset references,
and the deployment gate into a single manifest with content hashes, plus
human-readable Markdown. Signing is HMAC-SHA256 with RIFT_EVIDENCE_KEY
when configured; otherwise the bundle is explicitly marked unsigned —
never silently presented as attested.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

BUNDLE_VERSION = "evidence-bundle-v1"


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def build_bundle(*, model: dict, dataset: dict, metrics: dict,
                 calibration: dict, gate: dict, notes: str = "") -> dict:
    """Assemble a versioned evidence bundle (unsigned by default)."""
    body = {
        "bundle_version": BUNDLE_VERSION,
        "model": model,
        "dataset": dataset,
        "metrics": metrics,
        "calibration": calibration,
        "deployment_gate": gate,
        "notes": notes,
    }
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "content_hash": _sha256_hex(body),
        "signed": False,
        "signature": None,
    }
    return {"manifest": manifest, "body": body}


def sign_bundle(bundle: dict, key: str | None = None) -> dict:
    """Attach an HMAC-SHA256 signature over the manifest content hash.

    Key defaults to RIFT_EVIDENCE_SIGNING_KEY. Without a key the bundle is
    returned unchanged and stays explicitly unsigned.
    """
    secret = (key if key is not None else os.getenv("RIFT_EVIDENCE_SIGNING_KEY", "")).strip()
    if not secret:
        return bundle
    signed = json.loads(json.dumps(bundle))
    signed["manifest"] = dict(signed["manifest"])
    signed["manifest"]["signed"] = True
    signed["manifest"]["signature"] = hmac.new(
        secret.encode("utf-8"), signed["manifest"]["content_hash"].encode("ascii"),
        hashlib.sha256).hexdigest()
    return signed


def verify_bundle(bundle: dict, key: str | None = None) -> dict:
    """Verify bundle integrity and, when signed, authenticity."""
    try:
        manifest, body = bundle["manifest"], bundle["body"]
    except (KeyError, TypeError):
        return {"valid": False, "reason": "malformed bundle envelope"}
    if _sha256_hex(body) != manifest.get("content_hash"):
        return {"valid": False, "reason": "content hash mismatch: body altered"}
    secret = (key if key is not None else os.getenv("RIFT_EVIDENCE_SIGNING_KEY", "")).strip()
    if not manifest.get("signed"):
        return {"valid": True, "signed": False,
                "reason": "unsigned bundle: integrity ok, no authenticity claim"}
    if not secret:
        return {"valid": False, "reason": "signed bundle but no key available to verify"}
    expected = hmac.new(secret.encode("utf-8"), manifest["content_hash"].encode("ascii"),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, manifest.get("signature") or ""):
        return {"valid": False, "reason": "signature mismatch"}
    return {"valid": True, "signed": True, "reason": "signature verified"}


def render_markdown(bundle: dict) -> str:
    """Human-readable one-page rendering of the bundle body."""
    body = bundle.get("body", {})
    manifest = bundle.get("manifest", {})
    model = body.get("model", {})
    dataset = body.get("dataset", {})
    metrics = body.get("metrics", {})
    calibration = body.get("calibration", {})
    gate = body.get("deployment_gate", {})
    lines = [
        "# Evidence bundle",
        "",
        f"Model: {model.get('model_id', '?')} (weights `{str(model.get('weights_digest', '?'))[:12]}…)",
        f"Dataset: {dataset.get('source_id', '?')} — {dataset.get('days_evaluated', '?')} days, "
        f"{dataset.get('events', '?')} events",
        f"Metrics: agreement {metrics.get('event_agreement', '?')}, "
        f"Brier {metrics.get('brier_calibrated', '?')}, "
        f"ECE {metrics.get('ece_calibrated', '?')}",
        f"Calibration: {calibration.get('method', '?')} (fit {calibration.get('fit_window', '?')})",
        f"Deployment gate: {gate.get('clinical_use', '?')}",
        f"Bundle: {manifest.get('bundle_version', '?')} "
        f"{'(signed)' if manifest.get('signed') else '(UNSIGNED — integrity only)'}",
        f"Content hash: `{manifest.get('content_hash', '?')}`",
        "",
        body.get("notes", ""),
    ]
    return "\n".join(lines)


def write_bundle(bundle: dict, directory) -> dict:
    """Persist validation.json + validation.md to a directory.

    Returns {"validation.json": sha256, "validation.md": sha256,
    "directory": str}. Raises ValueError when the bundle fails
    verification first — corrupt bundles are never written as artifacts.
    Parent directories are created; existing files with the same content
    are simply overwritten identically (deterministic output).
    """
    from pathlib import Path as _Path

    verification = verify_bundle(bundle)
    if not verification.get("valid"):
        raise ValueError(f"refusing to write invalid bundle: {verification.get('reason')}")
    target = _Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    written: dict = {"directory": str(target)}
    payloads = {
        "validation.json": json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        "validation.md": render_markdown(bundle) + "\n",
    }
    for name, text in payloads.items():
        path = target / name
        path.write_text(text, encoding="utf-8")
        written[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return written
