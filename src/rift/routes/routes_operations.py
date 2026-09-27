"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

from .support import _publish_event
import json
from rift.observability import log_event


def get_api_operations_incidents(h, request_id, timer, path, query):
    """Route if path == "/api/operations/incidents": (moved verbatim from api.py do_GET)."""
    # Tenant scoping: ?owner=<id> filters to one owner, ?mine=true
    # filters to the authenticated caller. Without either, listing
    # is workspace-visible (single-tenant assumption documented in
    # docs/security.md) so unacknowledged (owner-less) incidents
    # stay triageable.
    caller, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.operations import incident_store
        from rift.operations.incidents import IncidentStatus, IncidentSeverity, IncidentType

        status = (query.get("status") or [None])[0]
        severity = (query.get("severity") or [None])[0]
        type_ = (query.get("type") or [None])[0]
        owner = (query.get("owner") or [None])[0]
        if (query.get("mine") or [""])[0].lower() in ("1", "true", "yes"):
            owner = caller

        incidents = incident_store.list(
            status=IncidentStatus(status) if status else None,
            severity=IncidentSeverity(severity) if severity else None,
            type=IncidentType(type_) if type_ else None,
            owner=owner,
            limit=100,
        )
        h._send(200, json.dumps([i.to_dict() for i in incidents]), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "incidents_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True

    return False


def get_api_operations_incidents_action(h, request_id, timer, path, query):
    """Route if path.startswith("/api/operations/incidents/") and not path.endswith("/action"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        incident_id = parts[3]
        _, ok = h._identity(request_id)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        try:
            from rift.operations import incident_store
            incident = incident_store.get(incident_id)
            if incident:
                h._send(200, json.dumps(incident.to_dict()), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 200)
            else:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
        except Exception:
            h._send(500, json.dumps({"error": "incidents_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_operations_decisions(h, request_id, timer, path, query):
    """Route if path == "/api/operations/decisions": (moved verbatim from api.py do_GET)."""
    # Same tenant-scoping contract as the incident listing: ?owner=
    # filters (mapped to proposed_by here), ?mine=true scopes to
    # the caller; unfiltered listing stays workspace-visible.
    caller, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.operations import decision_store
        from rift.operations.decisions import DecisionStatus

        status = (query.get("status") or [None])[0]
        scenario_id = (query.get("scenario_id") or [None])[0]
        proposed_by = (query.get("owner") or [None])[0]
        if (query.get("mine") or [""])[0].lower() in ("1", "true", "yes"):
            proposed_by = caller

        decisions = decision_store.list(
            status=DecisionStatus(status) if status else None,
            scenario_id=scenario_id,
            proposed_by=proposed_by,
            limit=100,
        )
        h._send(200, json.dumps([d.to_dict() for d in decisions]), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "decisions_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True

    return False


def get_api_operations_decisions_action(h, request_id, timer, path, query):
    """Route if path.startswith("/api/operations/decisions/") and not path.endswith("/action"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        decision_id = parts[3]
        _, ok = h._identity(request_id)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        try:
            from rift.operations import decision_store
            decision = decision_store.get(decision_id)
            if decision:
                h._send(200, json.dumps(decision.to_dict()), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 200)
            else:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
        except Exception:
            h._send(500, json.dumps({"error": "decisions_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def post_api_operations_incidents(h, request_id, timer, path, query):
    """Route if path == "/api/operations/incidents": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    _, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.operations import incident_store
        from rift.operations.incidents import IncidentType, IncidentSeverity

        incident = incident_store.create(
            type=IncidentType(body.get("type", "manual")),
            severity=IncidentSeverity(body.get("severity", "medium")),
            title=body.get("title", ""),
            description=body.get("description", ""),
            trigger_alert_id=body.get("trigger_alert_id"),
            tags=body.get("tags", []),
        )
        _publish_event("incidents.lifecycle", {"event": "created", "incident": incident.to_dict()})
        h._send(201, json.dumps(incident.to_dict()), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except ValueError as exc:
        h._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
    except Exception:
        log_event("internal_error", request_id=request_id, route="incidents-create")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False


def post_api_operations_incidents_action(h, request_id, timer, path, query):
    """Route if path.startswith("/api/operations/incidents/") and path.endswith("/action"): (moved verbatim from api.py do_POST)."""
    parts = path.strip("/").split("/")
    if len(parts) == 5:
        incident_id = parts[3]
        body, raw = h._read_json()
        if body == "overflow":
            h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 413, "validation")
            return True
        if body is None:
            h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
        if not ok:
            h._finish(timer, request_id, "POST", path, 401, "auth")
            return True
        try:
            from rift.operations import incident_store
            from rift.operations.incidents import IncidentStatus

            incident = incident_store.get(incident_id)
            if not incident:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 404, "not_found")
                return True
            action = body.get("action", "")
            note = body.get("note", "")
            actor = caller or "anonymous"
            if action == "acknowledge":
                incident.acknowledge(actor, note)
            elif action == "investigate":
                incident.investigate(actor, note)
            elif action == "resolve":
                incident.resolve(actor, note)
            elif action == "close":
                incident.close(actor, note)
            elif action == "reopen":
                incident.reopen(actor, note)
            else:
                h._send(400, json.dumps({"error": "invalid_action"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            _publish_event("incidents.lifecycle", {"event": action, "incident": incident.to_dict()})
            h._send(200, json.dumps(incident.to_dict()), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 200)
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_action", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
        except Exception:
            log_event("internal_error", request_id=request_id, route="incidents-action")
            h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 500, "internal")
        return True

    return False


def post_api_operations_decisions_action(h, request_id, timer, path, query):
    """Route if path.startswith("/api/operations/decisions/") and path.endswith("/action"): (moved verbatim from api.py do_POST)."""
    parts = path.strip("/").split("/")
    if len(parts) == 5:
        decision_id = parts[3]
        body, raw = h._read_json()
        if body == "overflow":
            h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 413, "validation")
            return True
        if body is None:
            h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
        if not ok:
            h._finish(timer, request_id, "POST", path, 401, "auth")
            return True
        try:
            from rift.operations import decision_store
            from rift.operations.decisions import DecisionAction

            decision = decision_store.get(decision_id)
            if not decision:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 404, "not_found")
                return True
            action = body.get("action", "")
            note = body.get("note", "")
            actor = caller or "anonymous"
            if action == "accept":
                decision.accept(actor, note, body.get("guardian_verdict"))
            elif action == "reject":
                decision.reject(actor, note, body.get("guardian_verdict"))
            elif action == "override":
                decision.override(actor, note, body.get("guardian_verdict"))
            elif action == "request_review":
                decision.request_review(actor, note)
            elif action == "execute":
                decision.execute(actor, body.get("result", {}))
            else:
                h._send(400, json.dumps({"error": "invalid_action"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            _publish_event("decisions.lifecycle", {"event": action, "decision": decision.to_dict()})
            h._send(200, json.dumps(decision.to_dict()), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 200)
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_action", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
        except Exception:
            log_event("internal_error", request_id=request_id, route="decisions-action")
            h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 500, "internal")
        return True

    return False
