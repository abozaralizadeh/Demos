"""How the World picks its next move. See docs/LOGICAL-FLOW.md, flow 3."""

from dataclasses import dataclass
from enum import StrEnum


class Move(StrEnum):
    LISTEN = "listen"
    MIRROR = "mirror"
    THIN = "thin"
    WHERE_YOU_STAND = "where_you_stand"
    CHALLENGE = "challenge"
    INFORM = "inform"
    BRIDGE = "bridge"
    CLOSE = "close"
    SAFETY = "safety"


@dataclass(frozen=True)
class TalkFacts:
    in_danger: bool = False
    wants_to_stop: bool = False
    person_turns: int = 0
    views_heard: int = 0
    unmirrored_views: int = 0
    mirrored: bool = False
    has_topic: bool = False
    enough_people: bool = False
    thin_done: bool = False
    told_where: bool = False
    challenged: bool = False
    wants_more_challenge: bool = False
    distressed: bool = False
    unheard_argument: bool = False
    asked_for_facts: bool = False
    informed: bool = False
    fact_available: bool = False
    bridged: bool = False
    bridge_available: bool = False


def next_move(t: TalkFacts) -> Move:
    if t.in_danger:
        return Move.SAFETY
    if t.wants_to_stop:
        return Move.CLOSE

    if t.views_heard == 0:
        if t.person_turns >= 3:
            return Move.THIN if not t.thin_done else Move.CLOSE
        return Move.LISTEN
    if t.unmirrored_views:
        if t.person_turns < 2:
            return Move.LISTEN
        return Move.MIRROR

    if not t.has_topic or not t.enough_people:
        return Move.THIN if not t.thin_done else Move.CLOSE
    if t.asked_for_facts and t.fact_available and not t.informed:
        return Move.INFORM
    if not t.told_where:
        return Move.WHERE_YOU_STAND

    may_challenge = (not t.challenged or t.wants_more_challenge) and not t.distressed
    if may_challenge and t.unheard_argument:
        return Move.CHALLENGE
    if t.fact_available and not t.informed:
        return Move.INFORM
    if t.bridge_available and not t.bridged:
        return Move.BRIDGE
    return Move.CLOSE
