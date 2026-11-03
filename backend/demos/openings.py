"""What the World says first when someone opens the app. See docs/LOGICAL-FLOW.md, flow 8."""

from datetime import date

from .config import THRESHOLDS
from .counts import LIVE, is_paused, tally

COPY = {
    "en": {
        "close": "We are very close to an agreement on {topic} in your area. Not everyone is sure yet. What's missing for you?",
        "needs": "People who think like you haven't answered this argument yet. Can you help?",
        "news": "Since we last talked, {n} people joined the {topic} topic.",
        "news_more": "One new argument goes against what you said. Want to hear it?",
        "daily": "Today's question",
        "other_side": "From the other side",
    },
    "it": {
        "close": "Siamo molto vicini a un accordo su {topic} nella tua zona. Non tutti sono convinti. Cosa manca per te?",
        "needs": "Chi la pensa come te non ha ancora risposto a questo argomento. Puoi aiutare?",
        "news": "Dall'ultima volta, {n} persone si sono unite al tema {topic}.",
        "news_more": "C'è un nuovo argomento contro ciò che hai detto. Vuoi sentirlo?",
        "daily": "La domanda di oggi",
        "other_side": "Dall'altra parte",
    },
}


def _seen(cur, person, key) -> bool:
    return bool(
        cur.execute(
            "SELECT 1 FROM opening_seen WHERE person_id = %s AND opening_key = %s", (person["id"], key)
        ).fetchone()
    )


def _close(cur, person, text):
    lang = person["language"]
    rows = cur.execute(
        f"SELECT t.id, t.main_statement_id AS sid, t.title_{lang} AS title FROM topic t"
        # Only the person's own area, even in preview: the line says "in your area".
        " WHERE t.state = 'live' AND t.main_statement_id IS NOT NULL AND t.area = %s"
        " AND NOT EXISTS (SELECT 1 FROM agreement a WHERE a.statement_id = t.main_statement_id"
        " AND a.state IN ('live', 'lapsed'))",
        (person["area"],),
    ).fetchall()
    for r in rows:
        counts = tally(cur, r["sid"])
        share = counts.share("agree")
        near = THRESHOLDS.agreement_overall - THRESHOLDS.close_margin <= share
        if counts.base < THRESHOLDS.show_percent or not near or is_paused(cur, r["id"]):
            continue
        mine = cur.execute(
            f"SELECT s.value FROM stance s WHERE s.person_id = %s AND s.statement_id = %s AND {LIVE}",
            (person["id"], r["sid"]),
        ).fetchone()
        key = f"close:{r['sid']}"
        if (not mine or mine["value"] == "unsure") and not _seen(cur, person, key):
            line = text["close"].replace("{topic}", r["title"].lower())
            return key, {"kind": "close", "lines": [line], "topic_id": r["id"]}
    return None


def _needs(cur, person, text):
    lang = person["language"]
    rows = cur.execute(
        f"SELECT a.id, a.topic_id, a.summary_{lang} AS summary, a.created_at, s.value FROM argument a"
        f" JOIN stance s ON s.statement_id = a.statement_id AND s.person_id = %s AND {LIVE}"
        " WHERE a.state = 'approved' AND ((a.side = 'against' AND s.value IN ('agree', 'partly'))"
        " OR (a.side = 'for' AND s.value = 'disagree'))"
        " AND NOT EXISTS (SELECT 1 FROM exposure e WHERE e.argument_id = a.id AND e.person_id = %s)",
        (person["id"], person["id"]),
    ).fetchall()
    for r in rows:
        key = f"needs:{r['id']}"
        if _seen(cur, person, key):
            continue
        answered = cur.execute(
            "SELECT 1 FROM claim c JOIN argument a ON a.statement_id = c.statement_id"
            " WHERE a.id = %s AND c.side = (CASE a.side WHEN 'for' THEN 'against' ELSE 'for' END)"
            " AND c.created_at > a.created_at LIMIT 1",
            (r["id"],),
        ).fetchone()
        if not answered:
            return key, {
                "kind": "needs",
                "lines": [text["needs"]],
                # Summaries are lower case so they fit inside a sentence. On their own they start with a capital.
                "quote": r["summary"][:1].upper() + r["summary"][1:],
                "quote_label": text["other_side"],
                "topic_id": r["topic_id"],
            }
    return None


def _news(cur, person, text):
    lang = person["language"]
    rows = cur.execute(
        f"SELECT t.id, t.title_{lang} AS title, count(DISTINCT n.person_id) AS n FROM stance mine"
        " JOIN statement st ON st.id = mine.statement_id JOIN topic t ON t.id = st.topic_id"
        " JOIN statement same ON same.topic_id = t.id"
        " JOIN stance n ON n.statement_id = same.id AND n.valid_from > %s AND n.person_id <> %s"
        " AND n.valid_to IS NULL AND n.state IN ('confirmed', 'corrected')"
        " WHERE mine.person_id = %s AND mine.valid_to IS NULL AND mine.state IN ('confirmed', 'corrected')"
        " GROUP BY t.id, t.title_en, t.title_it ORDER BY n DESC LIMIT 1",
        (person["last_seen_at"], person["id"], person["id"]),
    ).fetchall()
    for r in rows:
        key = f"news:{r['id']}:{date.today()}"
        if r["n"] >= THRESHOLDS.show_count and not _seen(cur, person, key):
            line = text["news"].replace("{n}", f"{r['n']:,}").replace("{topic}", r["title"].lower())
            return key, {"kind": "news", "lines": [line], "topic_id": r["id"]}
    return None


def _daily(cur, person, text):
    lang = person["language"]
    rows = cur.execute(
        f"SELECT t.id, t.topic_id, t.question_{lang} AS question FROM statement t"
        " WHERE t.question_en IS NOT NULL ORDER BY t.id"
    ).fetchall()
    if not rows:
        return None
    today = date.today()
    r = rows[today.toordinal() % len(rows)]
    key = f"daily:{today}"
    if _seen(cur, person, key):
        return None
    return key, {"kind": "daily", "label": text["daily"], "lines": [r["question"]], "topic_id": r["topic_id"]}


def pick(cur, person: dict) -> dict | None:
    """One opening at most. The order is flow 8's."""
    text = COPY.get(person["language"], COPY["en"])
    for finder in (_close, _needs, _news, _daily):
        found = finder(cur, person, text)
        if found:
            key, opening = found
            cur.execute(
                "INSERT INTO opening_seen (person_id, opening_key) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (person["id"], key),
            )
            return opening
    return None
