from demos import openings
from demos.checks import Sentence
from demos.config import settings
from demos.counts import is_paused, map_data, tally, you_data, agreement_card
from demos.engine import Engine
from demos.writer import Declined

RENT = "Rent in Milan is out of control. I pay half my salary and it keeps going up."


def reload(conn, person):
    return conn.execute("SELECT * FROM person WHERE id = %s", (person["id"],)).fetchone()


def to_mirror(engine, person):
    talk = engine.start(person)
    assert engine.say(person, talk.conversation_id, RENT).move == "listen"
    return talk.conversation_id, engine.say(person, talk.conversation_id, "It just keeps climbing, the rent.")


def test_a_full_talk_follows_the_design(conn, person):
    e = Engine(conn)
    cid, mirror = to_mirror(e, person)

    assert mirror.move == "mirror"
    assert [r["claim"] for r in mirror.mirror["rows"] if r["stance_id"]] == ["Rent is the main problem"]
    assert any("renters" in r["claim"] for r in mirror.mirror["rows"])
    assert not reload(conn, person)["unlocked"]

    stand = e.say(person, cid, "Yes, that's it.")
    assert stand.move == "where_you_stand"
    assert stand.unlocked
    counts = tally(conn.cursor(), "rent_main")
    assert f"{counts.percent('agree')}% of us in Milan agree" in stand.lines[0]
    assert f"About {counts.percent('disagree')}% of us say the real problem is wages" in stand.lines[1]

    challenge = e.say(person, cid, "Why?")
    assert challenge.move == "challenge"
    assert challenge.theme == "white"
    assert "rent is the symptom" in challenge.lines[1]
    assert f"{counts.percent('disagree')}% of us in Milan" in challenge.foot

    inform = e.say(person, cid, "Is that even true?")
    assert inform.move == "inform"
    assert inform.data["placeholder"] and inform.data["source"] == "[SOURCE NAME], [YEAR]"

    bridge = e.say(person, cid, "Hm, ok.")
    assert bridge.move == "bridge"
    assert bridge.bridge and bridge.bridge.endswith(".")

    close = e.say(person, cid, "Yes")
    assert close.move == "close"
    assert close.ended


def test_a_guess_never_reaches_public_numbers(conn, person):
    cur = conn.cursor()
    before = tally(cur, "rent_main")
    e = Engine(conn)
    cid, _ = to_mirror(e, person)
    assert tally(cur, "rent_main").base == before.base
    e.say(person, cid, "Yes")
    assert tally(cur, "rent_main").base == before.base + 1


def test_no_means_it_is_dropped(conn, person):
    cur = conn.cursor()
    before = tally(cur, "rent_main").base
    e = Engine(conn)
    cid, _ = to_mirror(e, person)
    e.say(person, cid, "No, that's wrong")
    assert tally(cur, "rent_main").base == before
    assert not reload(conn, person)["unlocked"]


def test_a_tap_fixes_a_view_and_counts(conn, person):
    e = Engine(conn)
    cid, mirror = to_mirror(e, person)
    row = next(r for r in mirror.mirror["rows"] if r["stance_id"])
    result = e.fix(person, cid, row["stance_id"], "partly")
    assert result["word"] == "Partly"
    live = conn.execute(
        "SELECT value, state FROM stance WHERE id = %s", (row["stance_id"],)
    ).fetchone()
    assert live == {"value": "partly", "state": "corrected"}


def test_changing_your_mind_moves_the_numbers_and_credits_the_argument(conn, person):
    cur = conn.cursor()
    e = Engine(conn)
    cid, _ = to_mirror(e, person)
    e.say(person, cid, "Yes")
    agree = tally(cur, "rent_main").agree
    assert e.say(person, cid, "Why?").move == "challenge"

    change = e.say(person, cid, "No, rent is not the main thing after all.")
    assert change.move == "mirror"
    e.say(person, cid, "Yes")
    assert tally(cur, "rent_main").agree == agree - 1
    assert conn.execute(
        "SELECT count(*) AS n FROM exposure WHERE person_id = %s AND view_changed", (person["id"],)
    ).fetchone()["n"] == 1
    moved = you_data(cur, reload(conn, person))["moved"]
    assert moved["old_value"] == "agree" and moved["now_value"] == "disagree"
    assert "wages" in moved["because"]


def test_a_person_in_danger_stops_the_debate_and_feeds_nothing(conn, person):
    e = Engine(conn)
    talk = e.start(person)
    result = e.say(person, talk.conversation_id, "The rent is too much, I want to end my life")
    assert result.move == "safety"
    assert "112" in result.lines[1]
    assert conn.execute("SELECT count(*) AS n FROM stance WHERE person_id = %s", (person["id"],)).fetchone()["n"] == 0
    assert conn.execute("SELECT count(*) AS n FROM claim WHERE person_id = %s", (person["id"],)).fetchone()["n"] == 0
    turn = conn.execute(
        "SELECT excluded FROM turn WHERE conversation_id = %s AND speaker = 'person'", (talk.conversation_id,)
    ).fetchone()
    assert turn["excluded"]
    words = conn.execute("SELECT count(*) AS n FROM safety_event").fetchone()
    assert words["n"] >= 1


def test_thin_topic_says_so(conn, person):
    e = Engine(conn)
    talk = e.start(person)
    e.say(person, talk.conversation_id, "Schools here are falling apart.")
    e.say(person, talk.conversation_id, "My school has no heating.")
    result = e.say(person, talk.conversation_id, "Yes")
    assert result.move == "thin"
    assert result.lines[0] == "Not many of us have talked about schools yet."
    assert result.data["title"] == "Schools in Milan"
    assert result.lines[-1] == "Want to be one of the first?"


def test_unknown_subject_is_honest(conn, person):
    e = Engine(conn)
    talk = e.start(person)
    for line in ("I keep thinking about the moon.", "It looks closer lately.", "Quite strange really."):
        result = e.say(person, talk.conversation_id, line)
    assert result.move == "thin"
    assert "We don't know." in result.lines


class LyingWriter:
    def __init__(self):
        self.calls = 0

    def write(self, pack, feedback=None):
        self.calls += 1
        return [Sentence("claim", "Exactly 97% of us love this.", list(pack.evidence))]


class DecliningWriter:
    def write(self, pack, feedback=None):
        raise Declined()


class BrokenWriter:
    def write(self, pack, feedback=None):
        raise RuntimeError("down")


def stand_with(conn, person, writer):
    e = Engine(conn, writer=writer)
    cid, _ = to_mirror(e, person)
    return e, e.say(person, cid, "Yes")


def test_an_invented_number_never_reaches_a_person(conn, person):
    writer = LyingWriter()
    _, result = stand_with(conn, person, writer)
    assert writer.calls >= 2
    assert not any("97" in line for line in result.lines)
    assert conn.execute("SELECT count(*) AS n FROM reply_failure").fetchone()["n"] >= 1


def test_model_declining_or_failing_still_gives_a_checked_reply(conn, person):
    for writer in (DecliningWriter(), BrokenWriter()):
        _, result = stand_with(conn, person, writer)
        assert result.lines
        assert result.move == "where_you_stand"
        person = reload(conn, person)
        conn.execute("UPDATE stance SET valid_to = now() WHERE person_id = %s", (person["id"],))


def test_election_pause_hides_numbers_everywhere(conn, person):
    conn.execute(
        "INSERT INTO election (area, vote_date, polls_close, topic_ids)"
        " VALUES ('milan', now() + interval '3 days', now() + interval '4 days', %s)",
        (["rent", "short_rentals"],),
    )
    cur = conn.cursor()
    assert is_paused(cur, "rent")
    e = Engine(conn)
    cid, _ = to_mirror(e, person)
    result = e.say(person, cid, "Yes")
    assert not any("%" in line for line in result.lines)
    rent = next(t for t in map_data(cur, "en")["topics"] if t["id"] == "rent")
    assert rent["paused"] and rent["gap"] is None
    agreement = conn.execute("SELECT id FROM agreement WHERE statement_id = 'str_main'").fetchone()
    assert agreement_card(cur, agreement["id"], "en")["meters"] == []


def test_map_matches_the_design_shape(conn):
    topics = {t["id"]: t for t in map_data(conn.cursor(), "en")["topics"]}
    assert topics["cars"]["gap"] > 0.6
    assert topics["short_rentals"]["gap"] < 0.3
    assert topics["schools"]["thin"]


def test_map_lines_stay_few(conn):
    data = map_data(conn.cursor(), "en")
    ends = [t for l in data["links"] for t in (l["topic_a"], l["topic_b"])]
    assert data["links"] and max(ends.count(t) for t in set(ends)) <= 2
    italy = {t["id"] for t in map_data(conn.cursor(), "en", "italy")["topics"]}
    assert italy == {"min_wage", "pensions", "young_leaving", "nuclear"}


def test_close_opening_stays_in_your_area_even_in_preview(conn, person, monkeypatch):
    # Found in the simulator: with preview on, Home offered a World topic "in your area".
    monkeypatch.setattr(settings(), "preview_features", True)
    cur = conn.cursor()
    areas = set()
    while (opening := openings.pick(cur, person)) and opening["kind"] == "close":
        areas.add(cur.execute("SELECT area FROM topic WHERE id = %s", (opening["topic_id"],)).fetchone()["area"])
    assert areas == {"milan"}


def test_the_agreement_card_is_computed_not_typed(conn):
    cur = conn.cursor()
    a = conn.execute("SELECT id FROM agreement WHERE statement_id = 'str_main'").fetchone()
    card = agreement_card(cur, a["id"], "en")
    meters = {m["label"]: m["pct"] for m in card["meters"]}
    assert meters["Overall"] == tally(cur, "str_main").percent("agree")
    assert set(meters) == {"Renters", "Owners", "Overall"}


def test_italian_talk(conn, person):
    conn.execute("UPDATE person SET language = 'it' WHERE id = %s", (person["id"],))
    person = reload(conn, person)
    e = Engine(conn)
    talk = e.start(person)
    e.say(person, talk.conversation_id, "Gli affitti a Milano sono fuori controllo.")
    mirror = e.say(person, talk.conversation_id, "Pago l'affitto e sale sempre.")
    assert mirror.lines == ["Ecco cosa abbiamo sentito. Giusto?"]
    stand = e.say(person, talk.conversation_id, "Sì")
    assert "di noi a Milano" in stand.lines[0]
