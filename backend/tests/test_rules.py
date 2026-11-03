from demos.checks import Evidence, Number, Pack, Sentence, check_reply, fill_slots
from demos.moves import Move, TalkFacts, next_move
from demos.understand import extract_views, in_danger, read_value, scrub, wants_to_stop


def facts(**kw):
    base = dict(person_turns=2, views_heard=1, mirrored=True, has_topic=True, enough_people=True)
    return TalkFacts(**{**base, **kw})


def test_danger_beats_everything():
    assert next_move(facts(in_danger=True, wants_to_stop=True)) == Move.SAFETY


def test_stop_always_works():
    assert next_move(facts(wants_to_stop=True, unheard_argument=True)) == Move.CLOSE


def test_listens_until_there_is_a_view():
    assert next_move(TalkFacts(person_turns=1)) == Move.LISTEN


def test_mirror_comes_before_any_challenge():
    move = next_move(facts(unmirrored_views=2, told_where=True, unheard_argument=True))
    assert move == Move.MIRROR


def test_thin_topic_takes_the_honest_path():
    assert next_move(facts(enough_people=False)) == Move.THIN
    assert next_move(facts(enough_people=False, thin_done=True)) == Move.CLOSE


def test_only_one_challenge_unless_asked():
    done = facts(told_where=True, challenged=True, unheard_argument=True)
    assert next_move(done) != Move.CHALLENGE
    asked = facts(told_where=True, challenged=True, unheard_argument=True, wants_more_challenge=True)
    assert next_move(asked) == Move.CHALLENGE


def test_no_challenge_for_someone_distressed():
    assert next_move(facts(told_where=True, unheard_argument=True, distressed=True)) != Move.CHALLENGE


def test_order_after_mirror():
    assert next_move(facts()) == Move.WHERE_YOU_STAND
    assert next_move(facts(told_where=True, unheard_argument=True)) == Move.CHALLENGE
    assert next_move(facts(told_where=True, challenged=True, fact_available=True)) == Move.INFORM
    assert next_move(facts(told_where=True, informed=True, bridge_available=True)) == Move.BRIDGE
    assert next_move(facts(told_where=True, bridged=True)) == Move.CLOSE


def pack():
    p = Pack("where_you_stand", "en")
    p.evidence["count:rent"] = Evidence("count:rent", "count", "Rent is the main problem", 600)
    p.evidence["count:small"] = Evidence("count:small", "count", "x", 12)
    p.evidence["argument:1"] = Evidence("argument:1", "argument", "We think...", 40)
    p.evidence["argument:2"] = Evidence("argument:2", "argument", "One person's idea", 2)
    p.numbers["pct"] = Number("64", 600)
    p.numbers["tiny"] = Number("50", 12)
    return p


def test_good_claim_passes():
    ok = [Sentence("claim", "{pct}% of us agree.", ["count:rent"])]
    assert check_reply(ok, pack()) == []
    assert fill_slots(ok[0].text, pack().numbers) == "64% of us agree."


def test_writer_cannot_type_a_number():
    assert check_reply([Sentence("claim", "64% of us agree.", ["count:rent"])], pack())


def test_writer_cannot_invent_a_slot():
    assert check_reply([Sentence("claim", "{made_up}% of us agree.", ["count:rent"])], pack())


def test_percent_on_a_small_base_fails():
    assert check_reply([Sentence("claim", "{tiny}% of us agree.", ["count:rent"])], pack())


def test_claim_needs_real_evidence():
    assert check_reply([Sentence("claim", "Rent went up.")], pack())
    assert check_reply([Sentence("claim", "Rent went up.", ["count:nope"])], pack())


def test_we_needs_enough_people():
    assert check_reply([Sentence("claim", "We all think so.", ["count:small"])], pack())


def test_world_has_no_opinions():
    assert check_reply([Sentence("frame", "I think rent is too high.")], pack())
    assert check_reply([Sentence("frame", "Secondo me è giusto.")], pack())
    assert check_reply([Sentence("frame", "You should agree with that.")], pack())


def test_crowd_claims_cannot_hide_in_a_frame():
    assert check_reply([Sentence("frame", "Most of us want this.")], pack())
    assert check_reply([Sentence("question", "Why do many of us say that?")], pack())


def test_saying_few_people_talked_is_fine():
    assert check_reply([Sentence("frame", "Not many of us have talked about this yet.")], pack()) == []
    assert check_reply([Sentence("frame", "Non molti di noi ne hanno parlato.")], pack()) == []


def test_no_voting_advice():
    assert check_reply([Sentence("frame", "You should vote for her.")], pack())


def test_arguments_must_be_approved_and_backed():
    assert check_reply([Sentence("argument", ref="argument:1")], pack()) == []
    assert check_reply([Sentence("argument", ref="argument:2")], pack())
    assert check_reply([Sentence("argument", ref="argument:99")], pack())


def test_empty_reply_fails():
    assert check_reply([], pack())


def test_overreaching_sentence_fails_the_support_check():
    never = lambda sentence, evidence: False
    assert check_reply([Sentence("claim", "{pct}% agree.", ["count:rent"])], pack(), never)


def test_danger_in_both_languages():
    assert in_danger("I want to end my life")
    assert in_danger("voglio morire")
    assert not in_danger("this rent is killing me financially")


def test_stop_needs_a_short_sentence():
    assert wants_to_stop("not now")
    assert not wants_to_stop("we should stop raising the rent every single year")


def test_reading_a_view():
    assert read_value("Rent should be capped") == "agree"
    assert read_value("Rent should not be capped") == "disagree"
    assert read_value("Maybe rent should be capped") == "unsure"
    assert read_value("In parte hai ragione") == "partly"
    # Found in the simulator: a problem described with "no" is support, not disagreement.
    assert read_value("My kids' school has no heating this winter.") == "agree"
    assert read_value("I don't think schools need more money") == "disagree"


def test_keywords_match_accents_and_stems():
    statements = [{"id": "a", "topic_id": "t", "keywords": ["affitt"]}]
    assert extract_views("Gli affitti sono troppo alti", statements)[0].statement_id == "a"
    assert extract_views("Non c'entra nulla", statements) == []


def test_identifying_details_are_removed():
    text = "Mi chiamo Giulia, scrivimi a giulia@example.it o 333 1234567"
    clean = scrub(text)
    assert "Giulia" not in clean and "example.it" not in clean and "1234567" not in clean
