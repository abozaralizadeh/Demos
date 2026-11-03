import uuid
from datetime import datetime, timedelta, timezone

from demos.worker import cluster, merge_claims, propose_topics, update_agreements


def people(conn, n):
    ids = [uuid.uuid4() for _ in range(n)]
    for p in ids:
        conn.execute("INSERT INTO person (id) VALUES (%s)", (p,))
    return ids


def claim(conn, person, text, statement="rent_cap", side="against", topic="rent"):
    conn.execute(
        "INSERT INTO claim (person_id, topic_id, statement_id, side, text, language) VALUES (%s, %s, %s, %s, %s, 'en')",
        (person, topic, statement, side, text),
    )


def test_same_point_clusters_together():
    labels = cluster([
        "Landlords will leave the market if rents are capped",
        "If rents are capped landlords will leave the market",
        "The trams never come on time",
    ])
    assert labels[0] == labels[1] != labels[2]


def test_five_people_make_a_draft_never_an_approved_argument(conn):
    for p in people(conn, 5):
        claim(conn, p, "Landlords will leave the market if rents are capped")
    assert merge_claims(conn.cursor()) == 1
    row = conn.execute(
        "SELECT a.state, count(s.person_id) AS n FROM argument a JOIN argument_source s ON s.argument_id = a.id"
        " WHERE a.statement_id = 'rent_cap' GROUP BY a.id"
    ).fetchone()
    assert row == {"state": "draft", "n": 5}


def test_one_person_repeating_themselves_is_not_an_argument(conn):
    p = people(conn, 1)[0]
    for _ in range(8):
        claim(conn, p, "Landlords will leave the market if rents are capped")
    assert merge_claims(conn.cursor()) == 0


def test_new_topic_needs_twenty_people_and_stays_a_proposal(conn):
    for p in people(conn, 19):
        claim(conn, p, "The canals should be reopened across the city", None, None, None)
    assert propose_topics(conn.cursor()) == 0
    for p in people(conn, 1):
        claim(conn, p, "The canals should be reopened across the city", None, None, None)
    assert propose_topics(conn.cursor()) == 1
    assert conn.execute("SELECT count(*) AS n FROM topic WHERE id LIKE '%canal%'").fetchone()["n"] == 0


def agreement(conn, statement):
    return conn.execute("SELECT * FROM agreement WHERE statement_id = %s", (statement,)).fetchone()


def test_agreement_must_hold_then_can_lapse(conn):
    cur = conn.cursor()
    conn.execute("DELETE FROM agreement WHERE statement_id = 'str_main'")
    start = datetime.now(timezone.utc)
    update_agreements(cur, start)
    assert agreement(conn, "str_main")["state"] == "candidate"
    update_agreements(cur, start + timedelta(days=13))
    assert agreement(conn, "str_main")["state"] == "candidate"
    update_agreements(cur, start + timedelta(days=14))
    assert agreement(conn, "str_main")["state"] == "live"

    conn.execute("UPDATE stance SET value = 'disagree' WHERE statement_id = 'str_main' AND value = 'agree'")
    update_agreements(cur, start + timedelta(days=15))
    assert agreement(conn, "str_main")["state"] == "live"
    update_agreements(cur, start + timedelta(days=22))
    assert agreement(conn, "str_main")["state"] == "lapsed"


def test_one_sided_support_is_no_agreement(conn):
    update_agreements(conn.cursor())
    assert agreement(conn, "rent_main") is None
    assert agreement(conn, "cars_main") is None
