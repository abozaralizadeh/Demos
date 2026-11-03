"""Reading what a person said: safety, intent, views, identifying details."""

import re
import unicodedata
from dataclasses import dataclass

DANGER = re.compile(
    r"\b(kill myself|end my life|want to die|suicide|hurt myself|harm myself"
    r"|uccidermi|togliermi la vita|voglio morire|suicid\w+|farmi del male"
    r"|kill (him|her|them)|hurt (him|her|them)|ucciderlo|ucciderla|ammazzarlo|ammazzarla)\b",
    re.IGNORECASE,
)
DISTRESS = re.compile(
    r"\b(i can't take|i cant take|too much for me|i'm crying|non ce la faccio|sto piangendo)\b",
    re.IGNORECASE,
)
STOP = re.compile(
    r"\b(not now|stop|enough|that's all|bye|goodbye|basta|non ora|non adesso|ciao|fine)\b",
    re.IGNORECASE,
)
YES = re.compile(
    r"^\W*(yes|yeah|yep|right|correct|exactly|that's it|that is right|sure"
    r"|sì|si|esatto|giusto|certo|proprio così|va bene|ok|okay)\b",
    re.IGNORECASE,
)
NO = re.compile(r"^\W*(no|nope|not really|wrong|that's wrong|non proprio|sbagliato|per niente)\b", re.IGNORECASE)
WANT_FACTS = re.compile(
    r"\b(is that true|is that even true|source|prove it|numbers|data"
    r"|è vero|fonte|dimostralo|numeri|dati)\b",
    re.IGNORECASE,
)
MORE_CHALLENGE = re.compile(
    r"\b(challenge me|what else|tell me more against|sfidami|cos'altro)\b", re.IGNORECASE
)
# Bare "no", "never" and "mai" aren't here: "my school has no heating" backs more money for schools.
NEGATION = re.compile(
    r"\b(not|don't|dont|doesn't|shouldn't|disagree|against|non|contrario|contraria|sbagliato)\b",
    re.IGNORECASE,
)
PARTLY = re.compile(r"\b(partly|somewhat|in part|kind of|in parte|abbastanza)\b", re.IGNORECASE)
UNSURE = re.compile(
    r"\b(not sure|unsure|maybe|don't know|dont know|perhaps|forse|non so|incerto|incerta)\b",
    re.IGNORECASE,
)

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d")
TAX_CODE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)
NAMED = re.compile(
    r"\b(my name is|i am called|mi chiamo|sono il signor|sono la signora)\s+\S+", re.IGNORECASE
)


@dataclass
class HeardView:
    statement_id: str
    topic_id: str
    value: str
    text: str


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in plain if not unicodedata.combining(c))


def in_danger(text: str) -> bool:
    return bool(DANGER.search(text))


def seems_distressed(text: str) -> bool:
    return bool(DISTRESS.search(text))


def wants_to_stop(text: str) -> bool:
    return bool(STOP.search(text)) and len(text.split()) <= 5


def says_yes(text: str) -> bool:
    return bool(YES.search(text))


def says_no(text: str) -> bool:
    return bool(NO.search(text))


def wants_facts(text: str) -> bool:
    return bool(WANT_FACTS.search(text))


def wants_more_challenge(text: str) -> bool:
    return bool(MORE_CHALLENGE.search(text))


def scrub(text: str) -> str:
    """Remove the details that could identify someone before words are kept as a claim."""
    for pattern in (EMAIL, PHONE, TAX_CODE, NAMED):
        text = pattern.sub("[removed]", text)
    return text


def read_value(sentence: str) -> str:
    if UNSURE.search(sentence):
        return "unsure"
    if PARTLY.search(sentence):
        return "partly"
    if NEGATION.search(sentence):
        return "disagree"
    return "agree"


def sentences_of(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def match(text: str, keywords: list[str]) -> bool:
    folded = fold(text)
    return any(re.search(r"\b" + re.escape(fold(k)), folded) for k in keywords)


def extract_views(text: str, statements: list[dict]) -> list[HeardView]:
    """The plain extractor. It only ever matches known statements by their keywords."""
    views: dict[str, HeardView] = {}
    for sentence in sentences_of(text):
        for s in statements:
            if s["id"] not in views and match(sentence, s["keywords"]):
                views[s["id"]] = HeardView(s["id"], s["topic_id"], read_value(sentence), sentence)
    return list(views.values())


def extract_groups(text: str, groups: list[dict]) -> list[str]:
    return [g["id"] for g in groups if match(text, g["keywords"])]
