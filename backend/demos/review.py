"""The review console: the part of Demos run by people."""

import hmac
from datetime import date, datetime, timezone
from html import escape as e

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import THRESHOLDS, settings
from .counts import agreement_card

router = APIRouter(prefix="/review")
basic = HTTPBasic()


def reviewer(credentials: HTTPBasicCredentials = Depends(basic)) -> str:
    if not hmac.compare_digest(credentials.password, settings().review_token):
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def db():
    from .api import db as api_db

    yield from api_db()


def form(action: str, label: str, fields: str = "") -> str:
    return f"<form method=post action='/review/{action}' style='display:inline'>{fields}<button>{e(label)}</button></form> "


@router.get("", response_class=HTMLResponse)
def console(who: str = Depends(reviewer), conn=Depends(db)):
    cur = conn.cursor()
    reports = cur.execute(
        "SELECT r.*, t.text FROM report r LEFT JOIN turn t ON t.id = r.turn_id"
        " WHERE r.state = 'open' ORDER BY r.created_at"
    ).fetchall()
    drafts = cur.execute(
        "SELECT a.*, t.text_en AS statement, count(s.person_id) AS people FROM argument a"
        " JOIN statement t ON t.id = a.statement_id LEFT JOIN argument_source s ON s.argument_id = a.id"
        " WHERE a.state = 'draft' GROUP BY a.id, t.text_en ORDER BY a.id"
    ).fetchall()
    topics = cur.execute("SELECT * FROM proposed_topic WHERE state = 'open' ORDER BY id").fetchall()
    sends = cur.execute(
        "SELECT a.id, count(r.person_id) AS n FROM agreement a JOIN send_request r ON r.agreement_id = a.id"
        " WHERE a.state = 'live' AND NOT EXISTS (SELECT 1 FROM agreement_action x WHERE x.agreement_id = a.id"
        " AND x.kind = 'send') GROUP BY a.id HAVING count(r.person_id) >= %s",
        (THRESHOLDS.send_requests,),
    ).fetchall()
    audit = cur.execute(
        "SELECT id, move, text, evidence_ids FROM turn WHERE speaker = 'world'"
        " AND move IN ('where_you_stand', 'challenge', 'inform', 'bridge') ORDER BY random() LIMIT 10"
    ).fetchall()
    failures = cur.execute("SELECT move, reasons, at FROM reply_failure ORDER BY id DESC LIMIT 10").fetchall()
    elections = cur.execute("SELECT * FROM election ORDER BY vote_date").fetchall()

    out = ["<!doctype html><meta charset=utf-8><title>Demos review</title>",
           "<body style='font-family:system-ui;max-width:900px;margin:auto;padding:20px'>",
           f"<h1>Review</h1><p>Signed in as {e(who)}</p>"]

    out.append(f"<h2>Reports ({len(reports)})</h2>")
    for r in reports:
        out.append(f"<p><b>#{r['id']}</b> {e(r['reason'])}<br>{e(r['text'] or '(turn deleted)')}<br>Evidence: {e(', '.join(r['evidence_ids']))}<br>")
        hidden = f"<input type=hidden name=id value={r['id']}>"
        for decision in ("keep", "pull"):
            out.append(form("report", decision, hidden + f"<input type=hidden name=decision value={decision}>"))
        out.append("</p>")

    out.append(f"<h2>Draft arguments ({len(drafts)})</h2>")
    for a in drafts:
        hidden = f"<input type=hidden name=id value={a['id']}>"
        out.append(f"<p><b>{e(a['side'])}</b> on {e(a['statement'])}, {a['people']} people<br>{e(a['text_en'])}<br>")
        out.append(form("approve", "Approve", hidden) + form("retire", "Retire", hidden) + "</p>")

    out.append(f"<h2>Proposed topics ({len(topics)})</h2>")
    for t in topics:
        hidden = f"<input type=hidden name=id value={t['id']}>"
        out.append(f"<p>{t['people']} people: {e(t['sample_text'])}<br>{form('topic-reject', 'Reject', hidden)}</p>")

    out.append(f"<h2>Agreements ready to send ({len(sends)})</h2>")
    for s in sends:
        card = agreement_card(cur, s["id"], "en")
        hidden = f"<input type=hidden name=id value={s['id']}>"
        out.append(f"<p>{e(card['text'])}, {s['n']} requests<br>{form('send', 'Mark as sent', hidden + '<input name=target placeholder=Recipient required>')}</p>")

    out.append("<h2>Election calendar</h2>")
    for x in elections:
        out.append(f"<p>{e(x['area'])}: {x['vote_date']}, polls close {x['polls_close']}, topics {e(', '.join(x['topic_ids']))}</p>")
    out.append(form("election", "Add vote",
                    "<input name=area value=milan> <input type=date name=vote_date required>"
                    " <input type=datetime-local name=polls_close required> <input name=topics placeholder='rent,wages' required>"))

    out.append("<h2>Audit sample</h2>")
    for t in audit:
        out.append(f"<p><b>{e(t['move'])}</b> {e(t['text'])}<br><small>{e(', '.join(t['evidence_ids']))}</small></p>")

    out.append("<h2>Recent reply failures</h2>")
    for f in failures:
        out.append(f"<p>{e(f['move'])}: {e('; '.join(f['reasons']))}</p>")
    return "".join(out)


def back() -> RedirectResponse:
    return RedirectResponse("/review", status_code=303)


@router.post("/approve")
def approve(id: int = Form(), who: str = Depends(reviewer), conn=Depends(db)):
    conn.execute("UPDATE argument SET state = 'approved', reviewed_by = %s WHERE id = %s", (who, id))
    return back()


@router.post("/retire")
def retire(id: int = Form(), who: str = Depends(reviewer), conn=Depends(db)):
    conn.execute(
        "UPDATE argument SET state = 'retired', reviewed_by = %s, retired_reason = 'review' WHERE id = %s", (who, id)
    )
    return back()


@router.post("/report")
def decide_report(id: int = Form(), decision: str = Form(), who: str = Depends(reviewer), conn=Depends(db)):
    report = conn.execute("SELECT * FROM report WHERE id = %s", (id,)).fetchone()
    if not report:
        raise HTTPException(404)
    if decision == "pull":
        ids = [int(x.split(":")[1]) for x in report["evidence_ids"] if x.startswith("argument:")]
        conn.execute(
            "UPDATE argument SET state = 'retired', reviewed_by = %s, retired_reason = 'report' WHERE id = ANY(%s)",
            (who, ids),
        )
    conn.execute(
        "UPDATE report SET state = 'closed', decision = %s, decided_at = %s WHERE id = %s",
        (decision, datetime.now(timezone.utc), id),
    )
    return back()


@router.post("/topic-reject")
def reject_topic(id: int = Form(), who: str = Depends(reviewer), conn=Depends(db)):
    conn.execute("UPDATE proposed_topic SET state = 'rejected' WHERE id = %s", (id,))
    return back()


@router.post("/send")
def mark_sent(id: int = Form(), target: str = Form(), who: str = Depends(reviewer), conn=Depends(db)):
    conn.execute(
        "INSERT INTO agreement_action (agreement_id, kind, target, reviewed_by) VALUES (%s, 'send', %s, %s)",
        (id, target, who),
    )
    return back()


@router.post("/election")
def add_election(
    area: str = Form(), vote_date: date = Form(), polls_close: datetime = Form(), topics: str = Form(),
    who: str = Depends(reviewer), conn=Depends(db),
):
    conn.execute(
        "INSERT INTO election (area, vote_date, polls_close, topic_ids) VALUES (%s, %s, %s, %s)",
        (area, vote_date, polls_close, [t.strip() for t in topics.split(",") if t.strip()]),
    )
    return back()
