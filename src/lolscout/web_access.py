from __future__ import annotations

import base64
import binascii
import hmac
import os

from fastapi.responses import PlainTextResponse


def access_denial(request) -> PlainTextResponse | None:
    if request.url.path in {"/api/health", "/riot.txt", "/privacy", "/terms"} or request.url.path.startswith(("/assets/", "/static/")):
        return None
    mode = os.getenv("MMRLOL_ACCESS_MODE", "prototype").strip().lower()
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    admin_token = os.getenv("MMRLOL_ADMIN_TOKEN", "")
    if scheme.lower() == "bearer" and admin_token and hmac.compare_digest(value.encode(), admin_token.encode()):
        return None
    if mode == "public" and os.getenv("RIOT_KEY_TYPE", "").strip().lower() == "production":
        return None
    if mode not in {"prototype", "private"}:
        return PlainTextResponse("Acceso publico pendiente de configurar una clave de produccion.", status_code=503, headers={"Cache-Control": "no-store"})
    password = os.getenv("MMRLOL_VIEWER_PASSWORD", "")
    username = os.getenv("MMRLOL_VIEWER_USER", "mmr")
    # Direct local development remains usable; hosted deployments fail closed.
    if not password and not os.getenv("RENDER") and request.client and request.client.host in {"127.0.0.1", "::1"}:
        return None
    if not password:
        return PlainTextResponse("Prototipo pendiente de configurar el acceso privado.", status_code=503, headers={"Cache-Control": "no-store"})
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8") if scheme.lower() == "basic" else ""
    except (ValueError, UnicodeError, binascii.Error):
        decoded = ""
    supplied_user, _, supplied_password = decoded.partition(":")
    if hmac.compare_digest(supplied_user.encode(), username.encode()) and hmac.compare_digest(supplied_password.encode(), password.encode()):
        return None
    return PlainTextResponse("Acceso privado MMRQ Challenge.", status_code=401, headers={"WWW-Authenticate": 'Basic realm="MMRQ Challenge", charset="UTF-8"', "Cache-Control": "no-store"})
