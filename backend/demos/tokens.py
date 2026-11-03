"""Small signed tokens: identity assertions and app sessions."""

import base64
import hashlib
import hmac
import json
import time


def sign(secret: str, payload: dict, seconds: int) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps({**payload, "exp": int(time.time()) + seconds}).encode()
    ).decode()
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify(secret: str, token: str) -> dict | None:
    body, _, mac = token.partition(".")
    good = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, mac):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body))
    except ValueError:
        return None
    return payload if payload.get("exp", 0) > time.time() else None
