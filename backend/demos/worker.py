"""demos-worker. Turns talk into arguments and numbers, and enforces the rules that run on a clock."""

import logging
import time
from datetime import datetime, timedelta, timezone

from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from . import logs
from .config import THRESHOLDS
from .counts import tally, topic_groups, LIVE
from .db import connect, migrate

log = logging.getLogger("demos.worker")

SAME_POINT = 0.75


def cluster(texts: list[str]) -> list[int]:
    """Group sentences that make the same point. Works across Italian and English spelling."""
    if len(texts) < 2:
        return [0] * len(texts)
    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(texts)
    model = AgglomerativeClustering(
        n_clusters=None, distance_threshold=SAME_POINT, metric="cosine", linkage="average"
    )
    return model.fit_predict(vectors.toarray()).tolist()


def merge_claims(cur) -> int:
    """New claims become draft arguments once enough different people make the same point."""
    made = 0
    groups = cur.execute(
        "SELECT DISTINCT statement_id, side FROM claim"
        " WHERE argument_id IS NULL AND statement_id IS NOT NULL AND side IS NOT NULL"
    ).fetchall()
    for g in groups:
        claims = cur.execute(
            "SELECT c.*, s.topic_id AS statement_topic FROM claim c JOIN statement s ON s.id = c.statement_id"
            " WHERE c.argument_id IS NULL AND c.statement_id = %s AND c.side = %s ORDER BY c.id",
            (g["statement_id"], g["side"]),
        ).fetchall()
        labels = cluster([c["text"] for c in claims])
        for label in set(labels):
            members = [c for c, l in zip(claims, labels) if l == label]
            people = {c["person_id"] for c in members}
            if len(people) < THRESHOLDS.use_argument:
                continue
            text = max(members, key=lambda c: len(c["text"]))["text"]
            summary = text[:80].rstrip(" .,")
            argument = cur.execute(
                "INSERT INTO argument (topic_id, statement_id, side, summary_en, summary_it, text_en, text_it)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (members[0]["statement_topic"], g["statement_id"], g["side"], summary, summary, text, text),
            ).fetchone()
            for person in people:
                cur.execute(
                    "INSERT INTO argument_source (argument_id, person_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (argument["id"], person),
                )
            cur.execute(
                "UPDATE claim SET argument_id = %s WHERE id = ANY(%s)",
                (argument["id"], [c["id"] for c in members]),
            )
            made += 1
    return made


def propose_topics(cur) -> int:
    """Words that fit no topic can start a new one, once enough people raise it. A person approves."""
    since = datetime.now(timezone.utc) - timedelta(days=THRESHOLDS.new_topic_days)
    claims = cur.execute(
        "SELECT * FROM claim WHERE topic_id IS NULL AND created_at > %s ORDER BY id", (since,)
    ).fetchall()
    made = 0
    labels = cluster([c["text"] for c in claims]) if claims else []
    for label in set(labels):
        members = [c for c, l in zip(claims, labels) if l == label]
        people = {c["person_id"] for c in members}
        sample = max(members, key=lambda c: len(c["text"]))["text"]
        known = cur.execute("SELECT 1 FROM proposed_topic WHERE sample_text = %s", (sample,)).fetchone()
        if len(people) >= THRESHOLDS.new_topic_people and not known:
            cur.execute(
                "INSERT INTO proposed_topic (sample_text, people) VALUES (%s, %s)", (sample, len(people))
            )
            made += 1
    return made


def update_links(cur) -> None:
    """A line on the Map: topics the same people talk about."""
    cur.execute("DELETE FROM topic_link")
    cur.execute(
        f"""
        WITH who AS (
            SELECT DISTINCT t.topic_id, s.person_id FROM stance s
            JOIN statement t ON t.id = s.statement_id WHERE {LIVE}
        ), size AS (SELECT topic_id, count(*) AS n FROM who GROUP BY topic_id)
        INSERT INTO topic_link (topic_a, topic_b, strength)
        SELECT a.topic_id, b.topic_id,
               count(*)::real / (sa.n + sb.n - count(*))
        FROM who a JOIN who b ON a.person_id = b.person_id AND a.topic_id < b.topic_id
        JOIN size sa ON sa.topic_id = a.topic_id JOIN size sb ON sb.topic_id = b.topic_id
        GROUP BY a.topic_id, b.topic_id, sa.n, sb.n
        HAVING count(*) >= %s
        """,
        (THRESHOLDS.show_percent,),
    )


def passes_bar(cur, statement_id: str, topic_id: str) -> tuple[bool, list[tuple[str, float, int]]]:
    overall = tally(cur, statement_id)
    rows = []
    groups_over = 0
    for g in topic_groups(cur, topic_id):
        t = tally(cur, statement_id, g["id"])
        rows.append((g["label_en"], t.share("agree"), t.base))
        if t.base >= THRESHOLDS.agreement_group_base and t.share("agree") >= THRESHOLDS.agreement_group:
            groups_over += 1
    rows.append(("overall", overall.share("agree"), overall.base))
    ok = (
        overall.base >= THRESHOLDS.show_percent
        and overall.share("agree") >= THRESHOLDS.agreement_overall
        and groups_over >= 2
    )
    return ok, rows


def update_agreements(cur, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    hold = timedelta(days=THRESHOLDS.agreement_hold_days)
    lapse = timedelta(days=THRESHOLDS.agreement_lapse_days)
    statements = cur.execute(
        "SELECT s.id, s.topic_id FROM statement s JOIN topic t ON t.id = s.topic_id WHERE t.state = 'live'"
    ).fetchall()
    for s in statements:
        ok, rows = passes_bar(cur, s["id"], s["topic_id"])
        a = cur.execute("SELECT * FROM agreement WHERE statement_id = %s", (s["id"],)).fetchone()
        if a is None:
            if ok:
                cur.execute(
                    "INSERT INTO agreement (statement_id, topic_id, state, since) VALUES (%s, %s, 'candidate', %s)",
                    (s["id"], s["topic_id"], now),
                )
            continue

        state, since, below = a["state"], a["since"], a["below_since"]
        if state == "candidate":
            if not ok:
                state = "dropped"
            elif now - since >= hold:
                state = "live"
                cur.execute("UPDATE agreement SET live_since = %s WHERE id = %s", (now, a["id"]))
        elif state == "dropped" and ok:
            state, since = "candidate", now
        elif state == "live":
            if ok:
                below = None
            else:
                below = below or now
                if now - below >= lapse:
                    state = "lapsed"
        elif state == "lapsed":
            if not ok:
                below = below or now
            elif below is not None:
                below, since = None, now
            elif now - since >= hold:
                state = "live"

        cur.execute(
            "UPDATE agreement SET state = %s, since = %s, below_since = %s WHERE id = %s",
            (state, since, below, a["id"]),
        )
        if state in ("live", "lapsed"):
            done = cur.execute(
                "SELECT 1 FROM agreement_snapshot WHERE agreement_id = %s AND at::date = %s::date LIMIT 1",
                (a["id"], now),
            ).fetchone()
            if not done:
                for label, share, base in rows:
                    cur.execute(
                        "INSERT INTO agreement_snapshot (agreement_id, label, support_pct, base, at)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (a["id"], label, round(share * 100, 1), base, now),
                    )


def apply_retention(cur) -> int:
    return cur.execute("DELETE FROM turn WHERE delete_after < now()").rowcount


def run_once(conn) -> None:
    cur = conn.cursor()
    merged = merge_claims(cur)
    proposed = propose_topics(cur)
    update_links(cur)
    update_agreements(cur)
    expired = apply_retention(cur)
    conn.commit()
    if merged or proposed or expired:
        log.info("drafts=%s proposals=%s expired_turns=%s", merged, proposed, expired)


def main() -> None:
    logs.setup("demos-worker")
    with connect() as conn:
        migrate(conn)
    while True:
        started = time.monotonic()
        try:
            with connect() as conn:
                run_once(conn)
        except Exception:
            log.exception("worker round failed")
        time.sleep(max(5.0, 60.0 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
