"""demos-api. Accounts, talks, Map, You, Agreements."""

import html
import logging
import uuid
from dataclasses import asdict
from datetime import date, datetime
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from . import logs, openings, tokens
from .config import THRESHOLDS, settings
from .copy import say
from .counts import agreement_card, map_data, people_total, you_data
from .db import connect, migrate
from .engine import Engine

log = logging.getLogger("demos.api")
app = FastAPI(title="demos-api")
CONSENT_VERSION = "2026-11-02"
PURPOSES = ("opinions", "ai_processing")
pool: ConnectionPool | None = None


@app.on_event("startup")
def startup():
    global pool
    logs.setup("demos-api")
    with connect() as conn:
        migrate(conn)
    pool = ConnectionPool(settings().database_url, kwargs={"row_factory": dict_row}, min_size=1, max_size=10)
    from .review import router

    app.include_router(router)


@app.on_event("shutdown")
def shutdown():
    if pool:
        pool.close()


def db():
    with pool.connection() as conn:
        yield conn


def current_person(authorization: str = Header(default=""), conn=Depends(db)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    payload = tokens.verify(settings().session_secret, token)
    person = payload and conn.execute("SELECT * FROM person WHERE id = %s", (payload["person_id"],)).fetchone()
    if not person or person["status"] != "active":
        raise HTTPException(401)
    return person


def consented(person=Depends(current_person), conn=Depends(db)) -> dict:
    have = conn.execute(
        "SELECT count(DISTINCT purpose) AS n FROM consent"
        " WHERE person_id = %s AND withdrawn_at IS NULL AND purpose = ANY(%s)",
        (person["id"], list(PURPOSES)),
    ).fetchone()["n"]
    if have < len(PURPOSES):
        raise HTTPException(403, "consent needed")
    return person


def unlocked(person=Depends(consented)) -> dict:
    if not person["unlocked"]:
        raise HTTPException(403, "talk first")
    return person


# Accounts


class SessionIn(BaseModel):
    assertion: str
    language: Literal["it", "en"] = "it"


@app.post("/v1/session")
def create_session(body: SessionIn, conn=Depends(db)):
    payload = tokens.verify(settings().assertion_secret, body.assertion)
    if not payload:
        raise HTTPException(401)
    conn.execute(
        "INSERT INTO person (id, language) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
        (payload["person_id"], body.language),
    )
    return {"token": tokens.sign(settings().session_secret, {"person_id": payload["person_id"]}, 60 * 60 * 24 * 90)}


@app.post("/v1/consent")
def give_consent(person=Depends(current_person), conn=Depends(db)):
    for purpose in PURPOSES:
        conn.execute(
            "INSERT INTO consent (person_id, purpose, text_version) VALUES (%s, %s, %s)",
            (person["id"], purpose, CONSENT_VERSION),
        )
    return {"ok": True}


@app.post("/v1/consent/withdraw")
def withdraw_consent(person=Depends(current_person), conn=Depends(db)):
    """Works like delete, except the sign-in stays, so the person can agree again later."""
    pid = person["id"]
    cur = conn.cursor()
    cur.execute("UPDATE consent SET withdrawn_at = now() WHERE person_id = %s AND withdrawn_at IS NULL", (pid,))
    for table in ("conversation", "stance", "group_member", "claim", "argument_source", "exposure",
                  "bridge_source", "send_request", "petition_signature", "opening_seen"):
        cur.execute(f"DELETE FROM {table} WHERE person_id = %s", (pid,))
    # Reminders stop too: there's nothing for the World to tell someone it no longer listens to.
    cur.execute(
        "UPDATE person SET unlocked = false, anonymous = true, display_name = NULL, notifications = false WHERE id = %s",
        (pid,),
    )
    retire_thin_arguments(cur)
    return {"ok": True}


class SettingsIn(BaseModel):
    language: Literal["it", "en"] | None = None
    notifications: bool | None = None
    anonymous: bool | None = None
    display_name: str | None = None


@app.patch("/v1/settings")
def change_settings(body: SettingsIn, person=Depends(current_person), conn=Depends(db)):
    conn.execute(
        "UPDATE person SET language = COALESCE(%s, language), notifications = COALESCE(%s, notifications)"
        " WHERE id = %s",
        (body.language, body.notifications, person["id"]),
    )
    if body.anonymous is not None or body.display_name is not None:
        if not settings().preview_features:
            raise HTTPException(404)
        anonymous = person["anonymous"] if body.anonymous is None else body.anonymous
        name = " ".join((body.display_name or person["display_name"] or "").split())[:40]
        if not anonymous and len(name) < 2:
            raise HTTPException(422, "a name is needed to stop being anonymous")
        conn.execute(
            "UPDATE person SET anonymous = %s, display_name = %s WHERE id = %s",
            (anonymous, None if anonymous else name, person["id"]),
        )
        if anonymous:
            # A petition needs a name, so going back to anonymous takes the name off them.
            conn.execute("DELETE FROM petition_signature WHERE person_id = %s", (person["id"],))
    return {"ok": True}


@app.get("/v1/open")
def open_app(person=Depends(current_person), conn=Depends(db)):
    cur = conn.cursor()
    has_consent = cur.execute(
        "SELECT 1 FROM consent WHERE person_id = %s AND withdrawn_at IS NULL LIMIT 1", (person["id"],)
    ).fetchone()
    opening = openings.pick(cur, person) if has_consent and person["unlocked"] else None
    cur.execute("UPDATE person SET last_seen_at = now() WHERE id = %s", (person["id"],))
    return {
        "people": people_total(cur),
        "sample": settings().sample_data,
        "consented": bool(has_consent),
        "unlocked": person["unlocked"],
        "language": person["language"],
        "notifications": person["notifications"],
        "preview": settings().preview_features,
        "anonymous": person["anonymous"],
        "display_name": person["display_name"],
        "opening": opening,
    }


def retire_thin_arguments(cur) -> None:
    cur.execute(
        "UPDATE argument SET state = 'retired', retired_reason = 'too few people left' WHERE state = 'approved'"
        " AND (SELECT count(*) FROM argument_source s WHERE s.argument_id = argument.id) < %s",
        (THRESHOLDS.use_argument,),
    )


def forget_person(conn, person_id) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM person WHERE id = %s", (person_id,))
    retire_thin_arguments(cur)


@app.delete("/v1/me")
def delete_me(person=Depends(current_person), conn=Depends(db)):
    forget_person(conn, person["id"])
    conn.commit()
    try:
        httpx.delete(
            f"{settings().identity_url}/internal/person/{person['id']}",
            headers={"x-service-token": settings().service_token},
            timeout=5,
        ).raise_for_status()
    except httpx.HTTPError:
        log.error("identity link not removed for a deleted person")
        raise HTTPException(502, "Your data is gone, but your sign-in wasn't removed. Please try again.")
    return {"ok": True}


@app.get("/v1/export")
def export_me(person=Depends(current_person), conn=Depends(db)):
    pid = person["id"]
    tables = {
        "consents": "SELECT purpose, text_version, given_at, withdrawn_at FROM consent WHERE person_id = %s",
        "stances": "SELECT statement_id, value, state, valid_from, valid_to FROM stance WHERE person_id = %s",
        "groups": "SELECT group_id, since FROM group_member WHERE person_id = %s",
        "transcripts": "SELECT t.speaker, t.text, t.created_at FROM turn t JOIN conversation c"
        " ON c.id = t.conversation_id WHERE c.person_id = %s ORDER BY t.id",
        "claims": "SELECT text, created_at FROM claim WHERE person_id = %s",
        "arguments_heard": "SELECT argument_id, heard_at, view_changed FROM exposure WHERE person_id = %s",
        "petitions_signed": "SELECT agreement_id, at FROM petition_signature WHERE person_id = %s",
    }
    data = {name: conn.execute(sql, (pid,)).fetchall() for name, sql in tables.items()}
    keep = ("language", "area", "joined_at", "notifications", "anonymous", "display_name")
    return {"person": {k: person[k] for k in keep}, **data}


# Talking


class StartIn(BaseModel):
    topic_id: str | None = None
    opened_by: Literal["person", "news", "needs", "close", "daily", "map"] = "person"


class SayIn(BaseModel):
    text: str


class FixIn(BaseModel):
    stance_id: int
    value: Literal["agree", "partly", "unsure", "disagree"]


@app.post("/v1/talk")
def start_talk(body: StartIn, person=Depends(consented), conn=Depends(db)):
    return asdict(Engine(conn).start(person, body.opened_by, body.topic_id))


@app.post("/v1/talk/{conversation_id}/say")
def say_something(conversation_id: uuid.UUID, body: SayIn, person=Depends(consented), conn=Depends(db)):
    text = body.text.strip()[:2000]
    if not text:
        raise HTTPException(422, "nothing said")
    try:
        return asdict(Engine(conn).say(person, conversation_id, text))
    except LookupError:
        raise HTTPException(404)


@app.post("/v1/talk/{conversation_id}/fix")
def fix_view(conversation_id: uuid.UUID, body: FixIn, person=Depends(consented), conn=Depends(db)):
    try:
        return Engine(conn).fix(person, conversation_id, body.stance_id, body.value)
    except LookupError:
        raise HTTPException(404)


class ReportIn(BaseModel):
    turn_id: int
    reason: str = "reported in the app"


@app.post("/v1/report")
def report(body: ReportIn, person=Depends(consented), conn=Depends(db)):
    turn = conn.execute(
        "SELECT t.id, t.evidence_ids FROM turn t JOIN conversation c ON c.id = t.conversation_id"
        " WHERE t.id = %s AND c.person_id = %s",
        (body.turn_id, person["id"]),
    ).fetchone()
    if not turn:
        raise HTTPException(404)
    conn.execute(
        "INSERT INTO report (reporter_id, turn_id, evidence_ids, reason) VALUES (%s, %s, %s, %s)",
        (person["id"], turn["id"], turn["evidence_ids"], body.reason[:500]),
    )
    return {"message": say(person["language"], "report_ok")}


# Map, You, Agreements


@app.get("/v1/facts/{fact_id}")
def get_fact(fact_id: int, person=Depends(consented), conn=Depends(db)):
    lang = person["language"]
    f = conn.execute(
        f"SELECT f.*, t.title_{lang} AS topic FROM fact f JOIN topic t ON t.id = f.topic_id"
        " WHERE f.id = %s AND f.reviewed_by IS NOT NULL",
        (fact_id,),
    ).fetchone()
    if not f:
        raise HTTPException(404)
    return {
        "id": f["id"],
        "topic": f["topic"],
        "title": f[f"title_{lang}"],
        "items": [{"label": f[f"label_{lang}"], "value": f["value"]}],
        "source_name": f["source_name"],
        "year": f["year"],
        "url": f["source_url"],
        "placeholder": f["is_placeholder"],
        "reviewed": f["reviewed_by"] != "sample",
        "review_due": f["review_due"],
    }


@app.get("/v1/map")
def get_map(area: Literal["milan", "italy", "world"] = "milan", person=Depends(unlocked), conn=Depends(db)):
    if area != "milan" and not settings().preview_features:
        raise HTTPException(404)
    return map_data(conn.cursor(), person["language"], area)


@app.get("/v1/you")
def get_you(person=Depends(unlocked), conn=Depends(db)):
    return you_data(conn.cursor(), person)


@app.get("/v1/agreements/{agreement_id}")
def get_agreement(agreement_id: int, person=Depends(unlocked), conn=Depends(db)):
    cur = conn.cursor()
    card = agreement_card(cur, agreement_id, person["language"])
    if not card:
        raise HTTPException(404)
    asked = cur.execute(
        "SELECT 1 FROM send_request WHERE agreement_id = %s AND person_id = %s", (agreement_id, person["id"])
    ).fetchone()
    petition = None
    if settings().preview_features:
        signed = cur.execute(
            "SELECT 1 FROM petition_signature WHERE agreement_id = %s AND person_id = %s",
            (agreement_id, person["id"]),
        ).fetchone()
        petition = {"signatures": len(signers(cur, agreement_id)), "signed": bool(signed)}
    return {**card, "asked": bool(asked), "url": f"/a/{agreement_id}", "petition": petition}


def signers(cur, agreement_id: int) -> list[str]:
    rows = cur.execute(
        "SELECT p.display_name FROM petition_signature s JOIN person p ON p.id = s.person_id"
        " WHERE s.agreement_id = %s AND NOT p.anonymous AND p.display_name IS NOT NULL ORDER BY s.at",
        (agreement_id,),
    ).fetchall()
    return [r["display_name"] for r in rows]


@app.post("/v1/agreements/{agreement_id}/sign")
def sign_petition(agreement_id: int, person=Depends(unlocked), conn=Depends(db)):
    """Signing again takes the name off. A petition is named support, so anonymous people can't sign."""
    if not settings().preview_features:
        raise HTTPException(404)
    a = conn.execute("SELECT state FROM agreement WHERE id = %s", (agreement_id,)).fetchone()
    if not a or a["state"] != "live":
        raise HTTPException(409, "not a live Agreement")
    if person["anonymous"] or not person["display_name"]:
        raise HTTPException(409, "a petition needs your name")
    gone = conn.execute(
        "DELETE FROM petition_signature WHERE agreement_id = %s AND person_id = %s RETURNING 1",
        (agreement_id, person["id"]),
    ).fetchone()
    if not gone:
        conn.execute(
            "INSERT INTO petition_signature (agreement_id, person_id) VALUES (%s, %s)", (agreement_id, person["id"])
        )
    return {"signed": not gone}


@app.post("/v1/agreements/{agreement_id}/send-request")
def ask_to_send(agreement_id: int, person=Depends(unlocked), conn=Depends(db)):
    a = conn.execute("SELECT state, topic_id FROM agreement WHERE id = %s", (agreement_id,)).fetchone()
    if not a or a["state"] != "live":
        raise HTTPException(409, "not a live Agreement")
    conn.execute(
        "INSERT INTO send_request (agreement_id, person_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (agreement_id, person["id"]),
    )
    return {"ok": True}


@app.get("/a/{agreement_id}", response_class=HTMLResponse)
def public_agreement(agreement_id: int, lang: Literal["it", "en"] = "it", conn=Depends(db)):
    card = agreement_card(conn.cursor(), agreement_id, lang)
    if not card or card["state"] not in ("live", "lapsed"):
        raise HTTPException(404)
    rows = "".join(
        f"<p>{html.escape(m['label'])}: <b>{m['pct']}%</b> <small>of {m['base']}</small></p>" for m in card["meters"]
    )
    note = "People on Demos, not all of Milan." if lang == "en" else "Persone su Demos, non tutta Milano."
    sample = "<p><b>Sample data</b></p>" if settings().sample_data else ""
    names = signers(conn.cursor(), agreement_id) if settings().preview_features else []
    signed = ""
    if names:
        head = "Signed by" if lang == "en" else "Firmato da"
        signed = f"<p style='color:#A3A3A0'>{head}: {html.escape(', '.join(names))}</p>"
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        f"<title>Demos</title><body style='background:#000;color:#F5F5F3;font-family:system-ui;"
        f"max-width:560px;margin:auto;padding:32px 20px'>{sample}<h1 style='font-weight:400'>"
        f"{html.escape(card['text'])}</h1>{rows}{signed}"
        f"<p style='color:#A3A3A0'>{note} {date.today().isoformat()}</p>"
    )


@app.get("/health")
def health(conn=Depends(db)):
    conn.execute("SELECT 1")
    return {"ok": True, "at": datetime.now().isoformat()}
