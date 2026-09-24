"""FHIR clinical resources beyond Observation: Patient, Condition,
MedicationRequest/Statement, Encounter, Device.

Same honesty rules as the Observation adapter: typed handlers extract what
the resource actually asserts; anything else is reported, never guessed.
Bundle pagination, authenticated extraction with retry/backoff, and
ingestion manifests make the boundary operable against real servers —
tested here against a locally served paginated fixture, since no live
FHIR server is configured.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from datetime import date

from .ehr import KNOWN_CONDITIONS, KNOWN_MEDICATIONS


def _codings_text(resource: dict, *paths: str) -> list[str]:
    """Collect code+display strings from CodeableConcept fields."""
    texts: list[str] = []
    for path in paths:
        node = resource.get(path) or {}
        if isinstance(node, dict) and node.get("text"):
            texts.append(str(node["text"]))
        for coding in (node.get("coding") or []):
            if isinstance(coding, dict):
                if coding.get("display"):
                    texts.append(str(coding["display"]))
                if coding.get("code"):
                    texts.append(str(coding["code"]))
    return texts


def _slug(text: str) -> str:
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def parse_patient(resource: dict, reference_date: str = "2026-09-24") -> tuple[dict, list[str]]:
    """Extract demographics. Age derives from birthDate at reference_date
    (explicit, deterministic — never 'today' implicitly)."""
    issues: list[str] = []
    if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
        return {}, ["not a Patient resource"]
    out: dict = {"patient_id": resource.get("id") or "unknown-patient"}
    birth = resource.get("birthDate")
    if isinstance(birth, str) and len(birth) >= 4:
        try:
            born = date.fromisoformat(birth[:10])
            ref = date.fromisoformat(reference_date[:10])
            out["age"] = float(max(0, (ref - born).days // 365))
        except ValueError:
            issues.append(f"unparseable birthDate {birth!r}")
    else:
        issues.append("missing birthDate: age left unknown")
    gender = resource.get("gender")
    out["sex"] = {"male": "M", "female": "F"}.get(gender, gender if isinstance(gender, str) else None)
    return out, issues


def parse_condition(resource: dict) -> tuple[str | None, list[str]]:
    """Return a normalized condition slug, or (None, [reasons])."""
    if not isinstance(resource, dict) or resource.get("resourceType") != "Condition":
        return None, ["not a Condition resource"]
    status = ((resource.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code", "")
    texts = _codings_text(resource, "code")
    slug = next((_slug(t) for t in texts if _slug(t) in KNOWN_CONDITIONS), None)
    if slug is None:
        searchable = " / ".join(texts) if texts else "uncoded"
        return None, [f"unmapped condition '{searchable}' (status {status or 'unknown'}): kept out, not guessed"]
    if status and status not in ("active", "recurrence", "relapse"):
        return None, [f"condition '{slug}' not active (status {status}): excluded"]
    return slug, []


def parse_medication(resource: dict) -> tuple[str | None, list[str]]:
    """MedicationRequest or MedicationStatement → normalized slug or rejection."""
    if not isinstance(resource, dict) or resource.get("resourceType") not in (
            "MedicationRequest", "MedicationStatement"):
        return None, ["not a MedicationRequest/Statement resource"]
    texts: list[str] = []
    med = resource.get("medicationCodeableConcept") or {}
    texts.extend(_codings_text({"m": med}, "m"))
    ref = resource.get("medicationReference")
    if isinstance(ref, dict) and isinstance(ref.get("display"), str):
        texts.append(ref["display"])
    slug = next((_slug(t) for t in texts if _slug(t) in KNOWN_MEDICATIONS), None)
    if slug is None:
        searchable = " / ".join(texts) if texts else "uncoded"
        return None, [f"unmapped medication '{searchable}': kept out, not guessed"]
    status = resource.get("status", "")
    if status and status not in ("active", "completed", "on-hold"):
        return None, [f"medication '{slug}' not current (status {status}): excluded"]
    return slug, []


def parse_encounter(resource: dict) -> tuple[dict | None, list[str]]:
    """Encounter → {id, start, end, status} or rejection."""
    if not isinstance(resource, dict) or resource.get("resourceType") != "Encounter":
        return None, ["not an Encounter resource"]
    period = resource.get("period") or {}
    if not isinstance(period.get("start"), str):
        return None, ["encounter without start time: excluded"]
    return {"id": resource.get("id"), "start": period["start"],
            "end": period.get("end"), "status": resource.get("status")}, []


def parse_device(resource: dict) -> tuple[dict | None, list[str]]:
    """Device → {id, type, status, patient} or rejection."""
    if not isinstance(resource, dict) or resource.get("resourceType") != "Device":
        return None, ["not a Device resource"]
    type_texts = _codings_text(resource, "type")
    patient = resource.get("patient") or {}
    patient_id = patient.get("reference", "").split("/")[-1] if isinstance(patient, dict) else None
    return {"id": resource.get("id"),
            "type": type_texts[0] if type_texts else "unknown-device-type",
            "status": resource.get("status"),
            "patient_id": patient_id}, []


def bundle_to_ehr(bundle: dict, reference_date: str = "2026-09-24") -> tuple[dict, list[str]]:
    """Build a raw EHR dict from a Bundle's Patient + Conditions + Medications.

    Feeds directly into ehr.normalize_ehr: the FHIR → twin path with no
    invented mappings. Unknown/unmapped entries are reported as issues.
    """
    issues: list[str] = []
    resources = [e.get("resource", {}) for e in (bundle.get("entry") or []) if isinstance(e, dict)] \
        if isinstance(bundle, dict) else []
    raw: dict = {"conditions": [], "medications": []}
    for res in resources:
        kind = res.get("resourceType")
        if kind == "Patient":
            demo, problems = parse_patient(res, reference_date)
            raw.update({k: v for k, v in demo.items() if v is not None})
            issues.extend(problems)
        elif kind == "Condition":
            slug, problems = parse_condition(res)
            if slug:
                raw["conditions"].append(slug)
            issues.extend(problems)
        elif kind in ("MedicationRequest", "MedicationStatement"):
            slug, problems = parse_medication(res)
            if slug:
                raw["medications"].append(slug)
            issues.extend(problems)
    return raw, issues


def extract_pages(first_bundle: dict) -> tuple[list[dict], list[str]]:
    """Split a Bundle's entries into (resources, issues); next-page URLs are
    returned separately so callers — not this parser — decide fetching."""
    issues: list[str] = []
    if not isinstance(first_bundle, dict) or first_bundle.get("resourceType") != "Bundle":
        return [], ["not a FHIR Bundle"]
    resources = []
    for entry in first_bundle.get("entry", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
            resources.append(entry["resource"])
        else:
            issues.append("bundle entry without resource: skipped")
    next_urls = [l.get("url") for l in (first_bundle.get("link") or [])
                 if isinstance(l, dict) and l.get("relation") == "next" and l.get("url")]
    return resources, issues + ([f"next-page: {u}" for u in next_urls])


class FhirError(Exception):
    """Classified extraction failure: auth, network, server, client, or format."""


def _private_fetch_allowed() -> bool:
    import os as _os

    return _os.getenv("RIFT_ALLOW_PRIVATE_FETCH", "false").strip().lower() in ("1", "true", "yes")


def checked_open(url: str, token: str | None, timeout_s: int):
    """SSRF-hardened fetch primitive: https/http only, no redirects, no
    private-network targets unless RIFT_ALLOW_PRIVATE_FETCH=true (dev/test).

    Pagination next-links come from remote servers, so every hop — not just
    the first URL — passes through this gate.
    """
    import ipaddress as _ipaddress
    import socket as _socket
    from urllib.parse import urlparse as _urlparse

    parsed = _urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FhirError(f"security: refusing non-HTTP(S) fetch target {parsed.scheme!r}")
    if not parsed.hostname:
        raise FhirError("security: fetch target has no hostname")
    try:
        infos = _socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                    type=_socket.SOCK_STREAM)
    except OSError as exc:
        raise FhirError(f"network: DNS resolution failed for {parsed.hostname}") from exc
    for info in infos:
        try:
            if not _ipaddress.ip_address(info[4][0]).is_global:
                if not _private_fetch_allowed():
                    raise FhirError(
                        "security: refusing non-public fetch target "
                        f"({parsed.hostname}); set RIFT_ALLOW_PRIVATE_FETCH=true for dev/test only")
                break
        except ValueError as exc:
            raise FhirError(f"network: unparsable resolved address for {parsed.hostname}") from exc
    request = urllib.request.Request(url, headers={"Accept": "application/fhir+json"})
    if token:
        request.add_header("Authorization", "Bearer " + token.strip())
    opener = urllib.request.build_opener(NoRedirectHandler)
    return opener.open(request, timeout=timeout_s)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirects off: a 3xx from a FHIR server is an explicit error, never a
    silent hop — pagination links are re-validated per hop instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"redirect refused ({code})", headers, fp)


def fetch_bundle(url: str, token: str | None = None, *, timeout_s: int = 20,
                 max_retries: int = 3) -> dict:
    """GET one Bundle page with bearer auth, retry/backoff, classified errors.

    Retries 429/5xx with exponential backoff; 401/403 raise auth errors
    immediately (retrying those is pointless); other 4xx raise client
    errors. No token storage here — callers pass short-lived tokens.
    Every hop passes SSRF checks (see checked_open).
    """
    import time as _time

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with checked_open(url, token, timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise FhirError(f"auth: FHIR server refused credentials ({exc.code})") from exc
            if exc.code == 404:
                raise FhirError("client: Bundle not found (404)") from exc
            if exc.code in (429,) or 500 <= exc.code < 600:
                last_error = exc
            else:
                raise FhirError(f"client: unexpected status {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except FhirError:
            raise
        if attempt < max_retries:
            _time.sleep(min(2 ** attempt, 8))
    raise FhirError(f"network: fetch failed after {max_retries + 1} attempts: {last_error}")


def fetch_all_pages(url: str, token: str | None = None, *, timeout_s: int = 20,
                    max_pages: int = 25) -> tuple[list[dict], dict]:
    """Follow Bundle pagination up to max_pages. Returns (resources, manifest).

    The manifest records source URL, pages fetched, per-page counts, and
    next-page truncation — the audit trail for an extraction run.
    """
    manifest: dict = {"source_url": url, "pages": [], "truncated": False}
    resources: list[dict] = []
    current: str | None = url
    while current is not None and len(manifest["pages"]) < max_pages:
        bundle = fetch_bundle(current, token, timeout_s=timeout_s)
        page_resources, _ = extract_pages(bundle)
        resources.extend(page_resources)
        manifest["pages"].append({"url": current, "resources": len(page_resources)})
        next_links = [l.get("url") for l in (bundle.get("link") or [])
                      if isinstance(l, dict) and l.get("relation") == "next" and l.get("url")]
        current = next_links[0] if next_links else None
    if current is not None:
        manifest["truncated"] = True
    manifest["total_resources"] = len(resources)
    return resources, manifest
