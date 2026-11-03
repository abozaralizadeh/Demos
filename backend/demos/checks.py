"""The checks a reply must pass before anyone hears it. See docs/LOGICAL-FLOW.md, flow 4."""

import re
from dataclasses import dataclass, field

from .config import THRESHOLDS

SLOT = re.compile(r"\{([a-z0-9_]+)\}")
DIGIT = re.compile(r"\d")

FIRST_PERSON = re.compile(
    r"\b(i think|i believe|i feel|in my opinion|personally|i would say"
    r"|penso che|credo che|secondo me|a mio parere|personalmente)\b",
    re.IGNORECASE,
)
CROWD_WORDS = re.compile(
    r"\b(most of us|(?<!not )many of us|some of us|few of us|most people|many people|people think"
    r"|everyone|la maggior parte di noi|(?<!non )molti di noi|alcuni di noi|in molti|tutti pensano)\b",
    re.IGNORECASE,
)
VALUE_WORDS = re.compile(
    r"\b(you should|the right thing|the right answer|obviously|clearly wrong"
    r"|dovresti|la cosa giusta|ovviamente)\b",
    re.IGNORECASE,
)
FORBIDDEN = re.compile(
    r"\b(vote for|you should vote|vota per|dovresti votare|kill them|ammazzateli)\b", re.IGNORECASE
)


@dataclass
class Number:
    value: str
    base: int
    kind: str = "percent"


@dataclass
class Evidence:
    id: str
    kind: str
    text: str = ""
    people: int = 0


@dataclass
class Sentence:
    kind: str
    text: str = ""
    evidence: list[str] = field(default_factory=list)
    ref: str | None = None


@dataclass
class Pack:
    move: str
    language: str
    evidence: dict[str, Evidence] = field(default_factory=dict)
    numbers: dict[str, Number] = field(default_factory=dict)
    template: list[Sentence] = field(default_factory=list)
    context: str = ""


def check_reply(sentences: list[Sentence], pack: Pack, supported=None) -> list[str]:
    """Return the reasons a reply fails. Empty means it passes.

    `supported` is an optional callable (sentence, evidence texts) -> bool used
    for the separate does-it-say-more-than-its-evidence check.
    """
    failures = []
    if not sentences:
        failures.append("empty reply")

    for s in sentences:
        if s.kind in ("argument", "fact", "bridge"):
            item = pack.evidence.get(s.ref or "")
            if item is None or item.kind != s.kind:
                failures.append(f"unknown {s.kind} {s.ref}")
            elif s.kind == "argument" and item.people < THRESHOLDS.use_argument:
                failures.append(f"argument {item.id} has too few people")
            continue

        if DIGIT.search(SLOT.sub("", s.text)):
            failures.append(f"number typed by the writer: {s.text!r}")

        for slot in SLOT.findall(s.text):
            number = pack.numbers.get(slot)
            if number is None:
                failures.append(f"unknown number slot {slot}")
            elif number.kind == "percent" and number.base < THRESHOLDS.show_percent:
                failures.append(f"number {slot} sits on too small a base")
            elif number.kind == "count" and number.base < THRESHOLDS.show_count:
                failures.append(f"count {slot} is too small to show")

        if FIRST_PERSON.search(s.text):
            failures.append(f"first-person opinion: {s.text!r}")
        if VALUE_WORDS.search(s.text):
            failures.append(f"view on values: {s.text!r}")
        if FORBIDDEN.search(s.text):
            failures.append(f"breaks a content rule: {s.text!r}")

        if s.kind == "claim":
            if not s.evidence:
                failures.append(f"claim with no evidence: {s.text!r}")
            unknown = [e for e in s.evidence if e not in pack.evidence]
            if unknown:
                failures.append(f"unknown evidence {unknown}")
            known = [pack.evidence[e] for e in s.evidence if e in pack.evidence]
            counted = [e for e in known if e.kind == "count"]
            if counted and max(e.people for e in counted) < THRESHOLDS.say_we:
                failures.append(f"too few people behind: {s.text!r}")
            if supported and known and not supported(s.text, [e.text for e in known]):
                failures.append(f"says more than its evidence: {s.text!r}")
        elif CROWD_WORDS.search(s.text):
            failures.append(f"claim about people with no evidence: {s.text!r}")

    return failures


def fill_slots(text: str, numbers: dict[str, Number]) -> str:
    return SLOT.sub(lambda m: numbers[m.group(1)].value, text)
