"""demos-identity. The only part that knows who a person really is.

It keeps a keyed hash and a random person ID, and throws everything else away.
The real SPID and CIE broker isn't connected yet. Until then /verify/dev stands
in for it, and it only exists when DEMOS_DEV_IDENTITY is on.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import logs, tokens
from .config import settings
from .db import IDENTITY_SCHEMA, connect, migrate

log = logging.getLogger("demos.identity")
app = FastAPI(title="demos-identity")


@app.on_event("startup")
def startup():
    logs.setup("demos-identity")
    with connect(settings().identity_database_url) as conn:
        migrate(conn, IDENTITY_SCHEMA)


def vault():
    with connect(settings().identity_database_url) as conn:
        yield conn


def id_hash(tax_code: str) -> str:
    key = settings().identity_pepper.encode()
    return hmac.new(key, tax_code.strip().upper().encode(), hashlib.sha256).hexdigest()


def over_18(born: date, today: date | None = None) -> bool:
    today = today or date.today()
    return (today.year - born.year) - ((today.month, today.day) < (born.month, born.day)) >= 18


def link_person(conn, tax_code: str, method: str) -> tuple[str, bool]:
    key = id_hash(tax_code)
    row = conn.execute("SELECT * FROM identity_link WHERE id_hash = %s", (key,)).fetchone()
    if row:
        banned = conn.execute(
            "SELECT 1 FROM identity_link WHERE id_hash = %s AND banned_until > now()", (key,)
        ).fetchone()
        if banned:
            raise HTTPException(403, "This account is banned for now.")
        return str(row["person_id"]), False
    person_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO identity_link (id_hash, person_id, method) VALUES (%s, %s, %s)",
        (key, person_id, method),
    )
    conn.commit()
    return str(person_id), True


class DevCheck(BaseModel):
    tax_code: str
    born: date


@app.post("/verify/dev")
def verify_dev(check: DevCheck, conn=Depends(vault)):
    if not settings().dev_identity:
        raise HTTPException(404)
    if not over_18(check.born):
        raise HTTPException(403, "under 18")
    person_id, new = link_person(conn, check.tax_code, "dev")
    log.info("verified new=%s", new)
    assertion = tokens.sign(settings().assertion_secret, {"person_id": person_id}, 120)
    return {"assertion": assertion, "new": new}


@app.delete("/internal/person/{person_id}")
def forget(person_id: str, x_service_token: str = Header(), conn=Depends(vault)):
    if not hmac.compare_digest(x_service_token, settings().service_token):
        raise HTTPException(403)
    conn.execute(
        "DELETE FROM identity_link WHERE person_id = %s"
        " AND (banned_until IS NULL OR banned_until < now())",
        (person_id,),
    )
    conn.commit()
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True}
