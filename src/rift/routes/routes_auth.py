"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

import json
from rift.observability import log_event


def get_api_auth_session_info(h, request_id, timer, path, query):
    """Route if path == "/api/auth/session-info": (moved verbatim from api.py do_GET)."""
    # Which principal (if any) the current request authenticates as,
    # and by which mechanism. Never echoes secrets.
    caller, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    from rift.auth_jwt import jwt_mode_enabled
    from rift.sessions import parse_session_cookie, sessions
    mechanism = "caller-asserted (open dev)"
    if jwt_mode_enabled():
        mechanism = "verified-jwt"
    elif h.headers.get("Authorization"):
        mechanism = "bearer-token"
    elif sessions.has(parse_session_cookie(h.headers.get("Cookie"))):
        mechanism = "session-cookie"
    h._send(200, json.dumps({"user_id": caller, "mechanism": mechanism}), request_id=request_id)
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def post_api_auth_session(h, request_id, timer, path, query):
    """Route if path == "/api/auth/session": (moved verbatim from api.py do_POST)."""
    # Exchange a service token for an HttpOnly session cookie so
    # browsers stop keeping the token in localStorage (XSS blast
    # radius). Service-token mode only; JWT mode keeps using
    # Authorization headers managed client-side.
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if not isinstance(body, dict):
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    from rift.auth import extract_bearer
    from rift.sessions import (
        cookie_secure, sessions,
        session_cookie_header, verify_service_token,
    )
    raw_token = body.get("token")
    token = raw_token if isinstance(raw_token, str) else extract_bearer(h.headers)
    if not verify_service_token(token):
        h._send(401, json.dumps({"error": "unauthorized"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    user_id = body.get("user_id")
    user_id = user_id.strip() if isinstance(user_id, str) and user_id.strip() else None
    if user_id is not None and len(user_id) > 128:
        h._send(400, json.dumps({"error": "user_id too long"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    try:
        session_id, expires_at = sessions.create(user_id)
        h._send(200, json.dumps({"user_id": user_id, "expires_at": expires_at}),
                   request_id=request_id,
                   extra_headers={"Set-Cookie": session_cookie_header(session_id, expires_at, cookie_secure())})
        h._finish(timer, request_id, "POST", path, 200)
    except Exception:
        log_event("internal_error", request_id=request_id, route="auth-session")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False


def post_api_auth_logout(h, request_id, timer, path, query):
    """Route if path == "/api/auth/logout": (moved verbatim from api.py do_POST)."""
    from rift.sessions import clear_session_cookie_header, cookie_secure, parse_session_cookie, sessions
    sessions.destroy(parse_session_cookie(h.headers.get("Cookie")))
    h._send(200, json.dumps({"logged_out": True}), request_id=request_id,
               extra_headers={"Set-Cookie": clear_session_cookie_header(cookie_secure())})
    h._finish(timer, request_id, "POST", path, 200)
    return True

    return False
