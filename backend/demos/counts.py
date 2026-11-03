"""Every public number comes from here, computed from live confirmed stances."""

from dataclasses import dataclass
from math import sqrt

from .config import THRESHOLDS

LIVE = "s.valid_to IS NULL AND s.state IN ('confirmed', 'corrected')"


@dataclass
class Tally:
    agree: int = 0
    partly: int = 0
    unsure: int = 0
    disagree: int = 0

    @property
    def base(self) -> int:
        return self.agree + self.partly + self.unsure + self.disagree

    def share(self, value: str) -> float:
        return getattr(self, value) / self.base if self.base else 0.0

    def percent(self, value: str) -> int:
        return round(self.share(value) * 100)


def tally(cur, statement_id: str, group_id: str | None = None) -> Tally:
    join = "JOIN group_member m ON m.person_id = s.person_id AND m.group_id = %(g)s" if group_id else ""
    rows = cur.execute(
        f"SELECT s.value, count(*) AS n FROM stance s {join}"
        f" WHERE s.statement_id = %(s)s AND {LIVE} GROUP BY s.value",
        {"s": statement_id, "g": group_id},
    ).fetchall()
    return Tally(**{r["value"]: r["n"] for r in rows})


def topic_people(cur, topic_id: str) -> int:
    return cur.execute(
        f"SELECT count(DISTINCT s.person_id) AS n FROM stance s"
        f" JOIN statement t ON t.id = s.statement_id WHERE t.topic_id = %s AND {LIVE}",
        (topic_id,),
    ).fetchone()["n"]


def people_total(cur) -> int:
    return cur.execute("SELECT count(*) AS n FROM person WHERE status = 'active'").fetchone()["n"]


def is_paused(cur, topic_id: str, area: str = "milan") -> bool:
    return bool(
        cur.execute(
            "SELECT 1 FROM election WHERE area = %s AND %s = ANY(topic_ids)"
            " AND now() >= vote_date - interval '15 days' AND now() < polls_close",
            (area, topic_id),
        ).fetchone()
    )


def topic_groups(cur, topic_id: str) -> list[dict]:
    return cur.execute(
        "SELECT * FROM grp WHERE topic_id = %s AND kind = 'life' ORDER BY id", (topic_id,)
    ).fetchall()


def topic_gap(cur, topic: dict) -> float | None:
    """How far apart two groups are on a topic's main statement. 0 is agreed, 1 is divided."""
    groups = topic_groups(cur, topic["id"])
    if len(groups) < 2 or not topic["main_statement_id"]:
        return None
    tallies = [tally(cur, topic["main_statement_id"], g["id"]) for g in groups[:2]]
    if any(t.base < THRESHOLDS.show_percent for t in tallies):
        return None
    return min(1.0, abs(tallies[0].share("agree") - tallies[1].share("agree")) / 0.8)


def map_data(cur, language: str, area: str = "milan") -> dict:
    topics = cur.execute(
        "SELECT * FROM topic WHERE area = %s AND state IN ('live', 'forming') ORDER BY id", (area,)
    ).fetchall()
    items = []
    for t in topics:
        people = topic_people(cur, t["id"])
        if people < THRESHOLDS.show_count:
            continue
        paused = is_paused(cur, t["id"], area)
        thin = people < THRESHOLDS.map_solid
        gap = None if thin or paused else topic_gap(cur, t)
        agreement = cur.execute(
            "SELECT id FROM agreement WHERE topic_id = %s AND state = 'live' LIMIT 1", (t["id"],)
        ).fetchone()
        items.append(
            {
                "id": t["id"],
                "label": t[f"title_{language}"],
                "x": t["layout_x"],
                "y": t["layout_y"],
                "tilt": t["tilt"],
                "radius": max(27, round(3.43 * sqrt(people))),
                "gap": gap,
                "thin": thin,
                "paused": paused,
                "people": people,
                "agreement_id": agreement["id"] if agreement else None,
            }
        )
    links = cur.execute(
        "SELECT topic_a, topic_b, strength FROM topic_link WHERE strength >= %s ORDER BY strength DESC",
        (THRESHOLDS.map_link_min,),
    ).fetchall()
    shown = {i["id"]: 0 for i in items}
    kept = []
    # Strongest first, and no topic gets more than a couple of lines, so the Map stays readable.
    for l in links:
        a, b = l["topic_a"], l["topic_b"]
        if a in shown and b in shown and max(shown[a], shown[b]) < THRESHOLDS.map_links_per_topic:
            shown[a] += 1
            shown[b] += 1
            kept.append(l)
    return {"topics": items, "links": kept}


def agreement_card(cur, agreement_id: int, language: str) -> dict | None:
    row = cur.execute(
        "SELECT a.*, s.text_en, s.text_it FROM agreement a"
        " JOIN statement s ON s.id = a.statement_id WHERE a.id = %s",
        (agreement_id,),
    ).fetchone()
    if not row:
        return None
    paused = is_paused(cur, row["topic_id"])
    meters = []
    if not paused:
        for g in topic_groups(cur, row["topic_id"]):
            t = tally(cur, row["statement_id"], g["id"])
            if t.base >= THRESHOLDS.show_percent:
                meters.append(
                    {"label": g[f"label_{language}"].capitalize(), "pct": t.percent("agree"), "base": t.base}
                )
        overall = tally(cur, row["statement_id"])
        if overall.base >= THRESHOLDS.show_percent:
            label = "Overall" if language == "en" else "Totale"
            meters.append({"label": label, "pct": overall.percent("agree"), "base": overall.base})
    sent = cur.execute(
        "SELECT sent_at FROM agreement_action WHERE agreement_id = %s AND kind = 'send'"
        " ORDER BY sent_at DESC LIMIT 1",
        (agreement_id,),
    ).fetchone()
    requests = cur.execute(
        "SELECT count(*) AS n FROM send_request WHERE agreement_id = %s", (agreement_id,)
    ).fetchone()["n"]
    return {
        "id": row["id"],
        "text": row[f"text_{language}"],
        "state": row["state"],
        "paused": paused,
        "meters": meters,
        "sent": bool(sent),
        "requests": requests,
        "requests_needed": THRESHOLDS.send_requests,
    }


def you_data(cur, person: dict) -> dict:
    language, pid = person["language"], person["id"]
    views = cur.execute(
        f"SELECT s.id AS stance_id, s.value, t.text_{language} AS claim FROM stance s"
        f" JOIN statement t ON t.id = s.statement_id"
        f" WHERE s.person_id = %s AND {LIVE} ORDER BY s.valid_from DESC LIMIT 20",
        (pid,),
    ).fetchall()
    travel = cur.execute(
        "SELECT count(DISTINCT e.person_id) AS heard,"
        " count(DISTINCT e.person_id) FILTER (WHERE e.view_changed) AS changed"
        " FROM exposure e JOIN argument_source a ON a.argument_id = e.argument_id"
        " WHERE a.person_id = %s AND e.person_id <> %s",
        (pid, pid),
    ).fetchone()
    words = cur.execute(
        "SELECT c.text FROM claim c JOIN argument_source a"
        " ON a.argument_id = c.argument_id AND a.person_id = c.person_id"
        " WHERE c.person_id = %s ORDER BY c.created_at DESC LIMIT 1",
        (pid,),
    ).fetchone()
    moved = cur.execute(
        f"SELECT s.value AS now_value, old.value AS old_value, t.text_{language} AS claim,"
        f" a.summary_{language} AS because FROM stance s"
        " JOIN stance old ON old.person_id = s.person_id AND old.statement_id = s.statement_id"
        " AND old.valid_to IS NOT NULL AND old.state IN ('confirmed', 'corrected')"
        " JOIN statement t ON t.id = s.statement_id"
        " LEFT JOIN argument a ON a.id = s.after_argument_id"
        f" WHERE s.person_id = %s AND {LIVE} AND old.value <> s.value"
        " ORDER BY s.valid_from DESC LIMIT 1",
        (pid,),
    ).fetchone()
    bridges = cur.execute(
        "SELECT count(*) AS n FROM bridge_source WHERE person_id = %s", (pid,)
    ).fetchone()["n"]
    agreements = cur.execute(
        "SELECT DISTINCT a.id FROM agreement a JOIN stance s ON s.statement_id = a.statement_id"
        f" WHERE s.person_id = %s AND {LIVE} AND s.value IN ('agree', 'partly')"
        " AND a.state IN ('live', 'lapsed')",
        (pid,),
    ).fetchall()
    return {
        "views": views,
        "travel": {**travel, "words": words["text"] if words else None},
        "moved": moved,
        "bridges": bridges,
        "agreements": [agreement_card(cur, a["id"], language) for a in agreements],
    }
