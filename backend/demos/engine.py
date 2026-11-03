"""One talk with the World: hear, choose a move, build evidence, write, check, say."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from psycopg.types.json import Jsonb

from . import understand as heard
from .checks import Evidence, Number, Pack, Sentence, check_reply, fill_slots
from .config import THRESHOLDS, settings
from .copy import VALUE_WORDS, say
from .counts import LIVE, is_paused, tally, topic_people
from .moves import Move, TalkFacts, next_move
from .writer import ClaudeReader, ClaudeWriter, Declined, TemplateWriter, has_key

log = logging.getLogger("demos.engine")

COUNTED = ("confirmed", "corrected")


@dataclass
class Result:
    conversation_id: str
    move: str
    lines: list[str] = field(default_factory=list)
    theme: str = "dark"
    mirror: dict | None = None
    data: dict | None = None
    foot: str | None = None
    source: str | None = None
    bridge: str | None = None
    ended: bool = False
    turn_id: int | None = None
    unlocked: bool = False


class Engine:
    def __init__(self, conn, writer=None, reader=None):
        self.conn = conn
        self.cur = conn.cursor()
        self.writer = writer or (ClaudeWriter() if has_key() else TemplateWriter())
        self.reader = reader or (ClaudeReader() if has_key() else None)

    # Starting a talk

    def start(self, person: dict, opened_by: str = "person", topic_id: str | None = None) -> Result:
        cid = uuid.uuid4()
        lang = person["language"]
        state = {"person_turns": 0}
        if topic_id:
            title = self.cur.execute(
                f"SELECT title_{lang} AS t FROM topic WHERE id = %s", (topic_id,)
            ).fetchone()
            line = say(lang, "listen_topic", topic=title["t"]) if title else say(lang, "listen_open")
        else:
            line = say(lang, "listen_open")
        self.cur.execute(
            "INSERT INTO conversation (id, person_id, opened_by, topic_id, state) VALUES (%s, %s, %s, %s, %s)",
            (cid, person["id"], opened_by, topic_id, Jsonb(state)),
        )
        turn_id = self._save_turn(cid, "world", line, Move.LISTEN, [])
        self.conn.commit()
        return Result(str(cid), Move.LISTEN, [line], turn_id=turn_id, unlocked=person["unlocked"])

    # One turn

    def say(self, person: dict, conversation_id: str, text: str) -> Result:
        talk = self.cur.execute(
            "SELECT * FROM conversation WHERE id = %s AND person_id = %s AND ended_at IS NULL",
            (conversation_id, person["id"]),
        ).fetchone()
        if not talk:
            raise LookupError("no such talk")
        st = talk["state"]
        lang = person["language"]
        st["person_turns"] = st.get("person_turns", 0) + 1

        danger = heard.in_danger(text)
        turn_id = self._save_turn(talk["id"], "person", text, None, [], excluded=danger)

        if danger:
            self.cur.execute("INSERT INTO safety_event (kind) VALUES ('danger')")
            st["distressed"] = True
            return self._finish(talk, st, person, self._safety(talk, lang))

        if heard.seems_distressed(text):
            st["distressed"] = True

        replied = self._handle_reply(person, st, text)
        if not replied:
            self._take_in(person, talk, st, text, turn_id)

        topic_id = st.get("topic_id") or talk["topic_id"]
        focus = st.get("focus")
        unheard = self._unheard_argument(person, topic_id, focus) if topic_id else None
        fact = self._unheard_fact(st, topic_id) if topic_id else None
        bridge = self._open_bridge(person, topic_id) if topic_id else None
        base = tally(self.cur, focus).base if focus else 0

        facts = TalkFacts(
            wants_to_stop=heard.wants_to_stop(text),
            person_turns=st["person_turns"],
            views_heard=st.get("views_heard", 0),
            unmirrored_views=len(st.get("pending", [])) + len(st.get("pending_groups", [])),
            mirrored=st.get("mirrored", False),
            has_topic=bool(topic_id),
            enough_people=bool(topic_id) and topic_people(self.cur, topic_id) >= THRESHOLDS.say_we and base >= THRESHOLDS.show_percent,
            thin_done=st.get("thin_done", False),
            told_where=st.get("told", False),
            challenged=st.get("challenged", False),
            wants_more_challenge=heard.wants_more_challenge(text),
            distressed=st.get("distressed", False),
            unheard_argument=unheard is not None,
            asked_for_facts=heard.wants_facts(text),
            informed=st.get("informed", False),
            fact_available=fact is not None,
            bridged=st.get("bridged", False),
            bridge_available=bridge is not None,
        )
        move = next_move(facts)
        result = self._run_move(move, person, talk, st, text, topic_id, focus, unheard, fact, bridge)
        return self._finish(talk, st, person, result, topic_id)

    def _finish(self, talk, st, person, result: Result, topic_id=None) -> Result:
        self.cur.execute(
            "UPDATE conversation SET state = %s, topic_id = COALESCE(%s, topic_id),"
            " ended_at = CASE WHEN %s THEN now() ELSE NULL END WHERE id = %s",
            (Jsonb(st), topic_id, result.ended, talk["id"]),
        )
        unlocked = self.cur.execute(
            "SELECT unlocked FROM person WHERE id = %s", (person["id"],)
        ).fetchone()
        result.unlocked = unlocked["unlocked"]
        self.conn.commit()
        return result

    # Hearing

    def _handle_reply(self, person, st, text) -> bool:
        """Deal with a yes or no to a pending Mirror or Bridge. True if that was all it was."""
        short = len(text.split()) <= 6
        if st.get("awaiting_bridge"):
            if heard.says_yes(text) or heard.says_no(text):
                value = "agree" if heard.says_yes(text) else "disagree"
                self._set_stance(person, st["awaiting_bridge"], value, "confirmed", st)
                st.pop("awaiting_bridge")
                return short
        if st.get("pending") or st.get("pending_groups"):
            if heard.says_yes(text):
                self._confirm_all(person, st)
                return short
            if heard.says_no(text) and short:
                for sid in st.get("pending", []):
                    self.cur.execute(
                        "UPDATE stance SET state = 'dropped', valid_to = now() WHERE id = %s", (sid,)
                    )
                st["pending"], st["pending_groups"] = [], []
                st["views_heard"] = 0 if not st.get("mirrored") else st.get("views_heard", 0)
                return True
        return False

    def _take_in(self, person, talk, st, text, turn_id) -> None:
        statements = self._statements(talk["topic_id"] or st.get("topic_id"))
        views = self._read(text, statements)
        groups = heard.extract_groups(text, self._groups())
        for v in views:
            self._note_view(person, st, v, turn_id)
        for g in groups:
            already = self.cur.execute(
                "SELECT 1 FROM group_member WHERE group_id = %s AND person_id = %s", (g, person["id"])
            ).fetchone()
            if not already and g not in st.get("pending_groups", []):
                st.setdefault("pending_groups", []).append(g)
        if not views and len(text.split()) >= 4:
            self._save_claim(person, turn_id, None, None, None, text)

    def _read(self, text, statements):
        if self.reader:
            try:
                return self.reader.views(text, statements)
            except Exception as e:
                log.warning("reader failed: %s", type(e).__name__)
        return heard.extract_views(text, statements)

    def _note_view(self, person, st, view, turn_id) -> None:
        # Saying the same thing twice before a Mirror is one view, and the latest wording wins.
        repeats = self.cur.execute(
            "UPDATE stance SET state = 'dropped', valid_to = now()"
            " WHERE id = ANY(%s) AND statement_id = %s RETURNING id",
            (st.get("pending", []), view.statement_id),
        ).fetchall()
        if repeats:
            gone = {r["id"] for r in repeats}
            st["pending"] = [sid for sid in st["pending"] if sid not in gone]
        current = self.cur.execute(
            f"SELECT s.value FROM stance s WHERE s.person_id = %s AND s.statement_id = %s AND {LIVE}",
            (person["id"], view.statement_id),
        ).fetchone()
        row = self.cur.execute(
            "INSERT INTO stance (person_id, statement_id, value, state, evidence_turn_id)"
            " VALUES (%s, %s, %s, 'inferred', %s) RETURNING id",
            (person["id"], view.statement_id, view.value, turn_id),
        ).fetchone()
        if not current or current["value"] != view.value:
            st.setdefault("pending", []).append(row["id"])
        else:
            self.cur.execute("UPDATE stance SET state = 'dropped', valid_to = now() WHERE id = %s", (row["id"],))
        st["views_heard"] = st.get("views_heard", 0) + 1
        st.setdefault("topic_id", view.topic_id)
        st.setdefault("focus", view.statement_id)
        side = {"agree": "for", "partly": "for", "disagree": "against"}.get(view.value)
        self._save_claim(person, turn_id, view.topic_id, view.statement_id, side, view.text)

    def _save_claim(self, person, turn_id, topic_id, statement_id, side, text) -> None:
        self.cur.execute(
            "INSERT INTO claim (person_id, turn_id, topic_id, statement_id, side, text, language)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (person["id"], turn_id, topic_id, statement_id, side, heard.scrub(text), person["language"]),
        )

    # Stances

    def _confirm_all(self, person, st) -> None:
        for sid in st.get("pending", []):
            row = self.cur.execute("SELECT * FROM stance WHERE id = %s", (sid,)).fetchone()
            if row and row["state"] == "inferred":
                self._settle(person, row, "confirmed")
        for g in st.get("pending_groups", []):
            self.cur.execute(
                "INSERT INTO group_member (group_id, person_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (g, person["id"]),
            )
        st["pending"], st["pending_groups"] = [], []
        st["mirrored"] = True
        self.cur.execute("UPDATE person SET unlocked = true WHERE id = %s", (person["id"],))

    def _settle(self, person, row, state, value=None) -> None:
        """Make a view count: close the old one and credit the argument that moved them, if any."""
        new_value = value or row["value"]
        old = self.cur.execute(
            f"SELECT s.* FROM stance s WHERE s.person_id = %s AND s.statement_id = %s AND s.id <> %s AND {LIVE}",
            (person["id"], row["statement_id"], row["id"]),
        ).fetchone()
        after = None
        if old:
            self.cur.execute("UPDATE stance SET valid_to = now() WHERE id = %s", (old["id"],))
            after = self._credit_change(person, row["statement_id"], old["value"], new_value)
        self.cur.execute(
            "UPDATE stance SET value = %s, state = %s, valid_from = now(), after_argument_id = %s WHERE id = %s",
            (new_value, state, after, row["id"]),
        )

    def _credit_change(self, person, statement_id, old_value, new_value):
        rank = {"disagree": 0, "unsure": 1, "partly": 1, "agree": 2}
        moved = rank[new_value] - rank[old_value]
        if moved == 0:
            return None
        side = "for" if moved > 0 else "against"
        hit = self.cur.execute(
            "SELECT e.id, e.argument_id FROM exposure e JOIN argument a ON a.id = e.argument_id"
            " WHERE e.person_id = %s AND a.statement_id = %s AND a.side = %s"
            " AND e.heard_at > now() - %s ORDER BY e.heard_at DESC LIMIT 1",
            (person["id"], statement_id, side, timedelta(days=THRESHOLDS.changed_view_days)),
        ).fetchone()
        if not hit:
            return None
        self.cur.execute("UPDATE exposure SET view_changed = true WHERE id = %s", (hit["id"],))
        return hit["argument_id"]

    def _set_stance(self, person, statement_id, value, state, st) -> None:
        row = self.cur.execute(
            "INSERT INTO stance (person_id, statement_id, value, state) VALUES (%s, %s, %s, 'inferred') RETURNING *",
            (person["id"], statement_id, value),
        ).fetchone()
        self._settle(person, row, state)

    def fix(self, person: dict, conversation_id: str, stance_id: int, value: str) -> dict:
        """A tap in Mirror. It's a correction, not a vote."""
        talk = self.cur.execute(
            "SELECT * FROM conversation WHERE id = %s AND person_id = %s", (conversation_id, person["id"])
        ).fetchone()
        row = self.cur.execute(
            "SELECT * FROM stance WHERE id = %s AND person_id = %s", (stance_id, person["id"])
        ).fetchone()
        if not talk or not row:
            raise LookupError("no such view")
        st = talk["state"]
        self._settle(person, row, "corrected", value)
        st["pending"] = [s for s in st.get("pending", []) if s != stance_id]
        if not st["pending"] and not st.get("pending_groups"):
            st["mirrored"] = True
            self.cur.execute("UPDATE person SET unlocked = true WHERE id = %s", (person["id"],))
        self.cur.execute("UPDATE conversation SET state = %s WHERE id = %s", (Jsonb(st), talk["id"]))
        self.conn.commit()
        return {"value": value, "word": VALUE_WORDS[person["language"]][value]}

    # Finding evidence

    def _statements(self, topic_id=None) -> list[dict]:
        # Italy and World topics only count when preview features are on.
        rows = self.cur.execute(
            "SELECT s.* FROM statement s JOIN topic t ON t.id = s.topic_id"
            " WHERE t.area = 'milan' OR %s OR t.id = %s",
            (settings().preview_features, topic_id),
        ).fetchall()
        return sorted(rows, key=lambda s: s["topic_id"] != topic_id)

    def _groups(self) -> list[dict]:
        return self.cur.execute("SELECT * FROM grp WHERE kind = 'life'").fetchall()

    def _unheard_argument(self, person, topic_id, focus):
        if not focus:
            return None
        mine = self.cur.execute(
            f"SELECT s.value FROM stance s WHERE s.person_id = %s AND s.statement_id = %s AND {LIVE}",
            (person["id"], focus),
        ).fetchone()
        if not mine or mine["value"] == "unsure":
            return None
        other = "against" if mine["value"] in ("agree", "partly") else "for"
        return self.cur.execute(
            "SELECT a.*, count(DISTINCT s.person_id) AS people FROM argument a"
            " JOIN argument_source s ON s.argument_id = a.id"
            " WHERE a.topic_id = %s AND a.statement_id = %s AND a.side = %s AND a.state = 'approved'"
            " AND NOT EXISTS (SELECT 1 FROM exposure e WHERE e.argument_id = a.id AND e.person_id = %s)"
            " GROUP BY a.id HAVING count(DISTINCT s.person_id) >= %s"
            " ORDER BY people DESC LIMIT 1",
            (topic_id, focus, other, person["id"], THRESHOLDS.use_argument),
        ).fetchone()

    def _unheard_fact(self, st, topic_id):
        sample = "" if settings().sample_data else "AND NOT is_placeholder"
        return self.cur.execute(
            f"SELECT * FROM fact WHERE topic_id = %s AND reviewed_by IS NOT NULL {sample}"
            " AND NOT (id = ANY(%s)) ORDER BY id LIMIT 1",
            (topic_id, st.get("facts_seen", [])),
        ).fetchone()

    def _open_bridge(self, person, topic_id):
        return self.cur.execute(
            f"SELECT b.*, t.text_en, t.text_it FROM bridge b JOIN statement t ON t.id = b.statement_id"
            f" WHERE b.topic_id = %s AND b.state = 'approved' AND NOT EXISTS ("
            f"SELECT 1 FROM stance s WHERE s.person_id = %s AND s.statement_id = b.statement_id AND {LIVE})"
            " LIMIT 1",
            (topic_id, person["id"]),
        ).fetchone()

    # Moves

    def _run_move(self, move, person, talk, st, text, topic_id, focus, argument, fact, bridge) -> Result:
        lang = person["language"]
        result = Result(str(talk["id"]), move)
        place = say(lang, "place_milan")
        pack = Pack(move, lang, context=self._recent(talk["id"]))
        build = getattr(self, f"_build_{move.value}")
        build(pack, result, person, st, topic_id, focus, argument, fact, bridge, place)
        self._deliver(pack, result, talk, lang)
        if move == Move.CLOSE:
            result.ended = True
        return result

    def _deliver(self, pack, result, talk, lang) -> None:
        reasons: list[str] = []
        sentences = None
        for attempt in range(2):
            try:
                draft = self.writer.write(pack, reasons or None)
            except Declined:
                reasons = ["model declined"]
                break
            except Exception as e:
                log.warning("writer failed: %s", type(e).__name__)
                reasons = ["model failed"]
                break
            reasons = check_reply(draft, pack, self._supported())
            if not reasons:
                sentences = draft
                break
        if sentences is None and not isinstance(self.writer, TemplateWriter):
            if not check_reply(pack.template, pack):
                sentences = pack.template
        if reasons:
            self.cur.execute(
                "INSERT INTO reply_failure (move, reasons) VALUES (%s, %s)", (pack.move, reasons)
            )
        if sentences is None:
            log.warning("reply fell back on move %s", pack.move)
            sentences = [Sentence("frame", say(lang, "fallback"))]
            result.mirror = result.data = result.bridge = result.foot = None
            result.theme = "dark"

        lines, evidence = [], []
        for s in sentences:
            if s.kind in ("argument", "fact", "bridge"):
                lines.append(pack.evidence[s.ref].text)
                evidence.append(s.ref)
            else:
                lines.append(fill_slots(s.text, pack.numbers))
                evidence.extend(s.evidence)
        result.lines = lines
        if result.foot:
            result.foot = fill_slots(result.foot, pack.numbers)
        if result.data and result.data.get("foot"):
            result.data["foot"] = fill_slots(result.data["foot"], pack.numbers)
        result.turn_id = self._save_turn(talk["id"], "world", " ".join(lines), pack.move, evidence)

    def _supported(self):
        return self.reader.supported if self.reader else None

    def _build_listen(self, pack, result, person, st, *_):
        key = "listen_more" if st["person_turns"] <= 1 else "listen_why"
        pack.template = [Sentence("question", say(pack.language, key))]

    def _build_mirror(self, pack, result, person, st, topic_id, focus, *_):
        lang = pack.language
        rows = []
        for sid in st.get("pending", []):
            row = self.cur.execute(
                f"SELECT s.id, s.value, t.text_{lang} AS claim FROM stance s"
                " JOIN statement t ON t.id = s.statement_id WHERE s.id = %s AND s.state = 'inferred'",
                (sid,),
            ).fetchone()
            if row:
                rows.append(
                    {"stance_id": row["id"], "claim": row["claim"], "value": row["value"],
                     "word": VALUE_WORDS[lang][row["value"]]}
                )
        for g in st.get("pending_groups", []):
            label = self.cur.execute(f"SELECT label_{lang} AS l FROM grp WHERE id = %s", (g,)).fetchone()
            rows.append({"stance_id": None, "claim": say(lang, "you_are", group=label["l"]), "value": None, "word": ""})
        last = self.cur.execute(
            "SELECT text FROM turn WHERE conversation_id = (SELECT conversation_id FROM turn WHERE id ="
            " (SELECT max(id) FROM turn WHERE speaker = 'person' AND conversation_id IN"
            " (SELECT id FROM conversation WHERE person_id = %s))) AND speaker = 'person' ORDER BY id DESC LIMIT 1",
            (person["id"],),
        ).fetchone()
        result.mirror = {"heard": last["text"] if last else "", "rows": rows, "hint": say(lang, "mirror_hint")}
        pack.template = [Sentence("frame", say(lang, "mirror_heard"))]

    def _build_where_you_stand(self, pack, result, person, st, topic_id, focus, argument, fact, bridge, place):
        lang = pack.language
        st["told"] = True
        if is_paused(self.cur, topic_id):
            pack.template = [Sentence("frame", say(lang, "stand_paused"))]
            return
        statement = self.cur.execute(f"SELECT text_{lang} AS t FROM statement WHERE id = %s", (focus,)).fetchone()["t"]
        counts = tally(self.cur, focus)
        mine = self.cur.execute(
            f"SELECT s.value FROM stance s WHERE s.person_id = %s AND s.statement_id = %s AND {LIVE}",
            (person["id"], focus),
        ).fetchone()
        side = "disagree" if mine and mine["value"] == "disagree" else "agree"
        evidence_id = f"count:{focus}"
        pack.evidence[evidence_id] = Evidence(evidence_id, "count", statement, counts.base)
        pack.numbers["pct"] = Number(str(counts.percent(side)), counts.base)
        key = "stand_no" if side == "disagree" else "stand_yes"
        pack.template = [
            Sentence("claim", say(lang, key, place=place, statement=statement.rstrip(".").lower()), [evidence_id])
        ]
        if argument:
            opposite = "agree" if side == "disagree" else "disagree"
            pack.numbers["other_pct"] = Number(str(counts.percent(opposite)), counts.base)
            result.data = {"bar": counts.percent(opposite), "base": counts.base}
            pack.template.append(
                Sentence("claim", say(lang, "stand_other", summary=argument[f"summary_{lang}"]), [evidence_id])
            )
        result.source = say(lang, "stand_source", place=place)
        result.data = result.data or {"base": counts.base}

    def _build_challenge(self, pack, result, person, st, topic_id, focus, argument, fact, bridge, place):
        lang = pack.language
        st["challenged"] = True
        ref = f"argument:{argument['id']}"
        pack.evidence[ref] = Evidence(ref, "argument", argument[f"text_{lang}"], argument["people"])
        pack.template = [Sentence("frame", say(lang, "challenge_intro")), Sentence("argument", ref=ref)]
        result.theme = "white"
        if not is_paused(self.cur, topic_id):
            counts = tally(self.cur, focus)
            value = "disagree" if argument["side"] == "against" else "agree"
            pack.numbers["pct"] = Number(str(counts.percent(value)), counts.base)
            result.foot = say(lang, "challenge_foot", place=place)
        self.cur.execute(
            "INSERT INTO exposure (person_id, argument_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (person["id"], argument["id"]),
        )

    def _data_block(self, pack, fact):
        lang = pack.language
        ref = f"fact:{fact['id']}"
        text = f"{fact[f'title_{lang}']}: {fact[f'label_{lang}']} {fact['value']}"
        pack.evidence[ref] = Evidence(ref, "fact", text)
        return ref, {
            "fact_id": fact["id"],
            "title": fact[f"title_{lang}"],
            "items": [{"label": fact[f"label_{lang}"], "value": fact["value"]}],
            "source": f"{fact['source_name']}, {fact['year']}",
            "url": fact["source_url"],
            "placeholder": fact["is_placeholder"],
        }

    def _build_inform(self, pack, result, person, st, topic_id, focus, argument, fact, bridge, place):
        st["informed"] = True
        st.setdefault("facts_seen", []).append(fact["id"])
        ref, result.data = self._data_block(pack, fact)
        pack.template = [Sentence("frame", say(pack.language, "inform_intro")), Sentence("fact", ref=ref)]

    def _build_bridge(self, pack, result, person, st, topic_id, focus, argument, fact, bridge, place):
        lang = pack.language
        st["bridged"] = True
        st["awaiting_bridge"] = bridge["statement_id"]
        ref = f"bridge:{bridge['id']}"
        # Statements are stored as claims without a full stop. Said aloud, it's a sentence.
        text = bridge[f"text_{lang}"].rstrip()
        text = text if text[-1:] in ".?!" else text + "."
        pack.evidence[ref] = Evidence(ref, "bridge", text)
        result.bridge = text
        pack.template = [
            Sentence("frame", say(lang, "bridge_intro")),
            Sentence("bridge", ref=ref),
            Sentence("question", say(lang, "bridge_ask")),
        ]

    def _build_thin(self, pack, result, person, st, topic_id, focus, argument, fact, bridge, place):
        lang = pack.language
        st["thin_done"] = True
        if topic_id:
            title = self.cur.execute(f"SELECT title_{lang} AS t FROM topic WHERE id = %s", (topic_id,)).fetchone()["t"]
            first = say(lang, "thin_topic", topic=title.lower())
        else:
            first = say(lang, "thin_general")
        pack.template = [Sentence("frame", first)]
        if fact:
            st.setdefault("facts_seen", []).append(fact["id"])
            ref, result.data = self._data_block(pack, fact)
            pack.template += [Sentence("frame", say(lang, "thin_facts")), Sentence("fact", ref=ref)]
        else:
            pack.template.append(Sentence("frame", say(lang, "thin_unknown")))
        pack.template.append(Sentence("question", say(lang, "thin_invite")))

    def _build_close(self, pack, result, *_):
        pack.template = [Sentence("frame", say(pack.language, "close"))]

    def _safety(self, talk, lang) -> Result:
        lines = [say(lang, "safety_1"), say(lang, "safety_2"), say(lang, "safety_3")]
        turn_id = self._save_turn(talk["id"], "world", " ".join(lines), Move.SAFETY, [])
        return Result(str(talk["id"]), Move.SAFETY, lines, turn_id=turn_id)

    # Saving

    def _save_turn(self, conversation_id, speaker, text, move, evidence, excluded=False) -> int:
        return self.cur.execute(
            "INSERT INTO turn (conversation_id, speaker, text, move, evidence_ids, excluded, delete_after)"
            " VALUES (%s, %s, %s, %s, %s, %s, now() + %s) RETURNING id",
            (conversation_id, speaker, text, move, evidence, excluded, timedelta(days=THRESHOLDS.transcript_days)),
        ).fetchone()["id"]

    def _recent(self, conversation_id) -> str:
        rows = self.cur.execute(
            "SELECT speaker, text FROM turn WHERE conversation_id = %s AND NOT excluded ORDER BY id DESC LIMIT 8",
            (conversation_id,),
        ).fetchall()
        return "\n".join(f"{r['speaker']}: {r['text']}" for r in reversed(rows))
