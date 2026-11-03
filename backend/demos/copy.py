"""Every fixed sentence the World can say, in Italian and English."""

COPY = {
    "en": {
        "listen_open": "What's on your mind?",
        "listen_more": "Tell us more. What makes you say that?",
        "listen_why": "What would have to change for you?",
        "listen_topic": "{topic}. Where do you stand?",
        "mirror_heard": "So this is what we heard. Right?",
        "mirror_hint": "Not quite? Just say so, or tap one to fix it.",
        "mirror_thanks": "Thanks. We've fixed that.",
        "you_are": "You are one of the {group}",
        "stand_yes": "{pct}% of us in {place} agree: {statement}.",
        "stand_no": "{pct}% of us in {place} disagree: {statement}.",
        "stand_other": "About {other_pct}% of us say {summary}. Want to hear why?",
        "stand_source": "From people in {place}",
        "stand_paused": "We've paused our numbers here until the vote is over.",
        "challenge_intro": "Let me speak as the people who disagree with you.",
        "challenge_foot": "Built only from what this group said. {pct}% of us in {place}.",
        "inform_intro": "Here's what the numbers say. This part is data, not what any of us think.",
        "bridge_intro": "Here's something both groups might accept.",
        "bridge_ask": "Would you?",
        "thin_topic": "Not many of us have talked about {topic} yet.",
        "thin_general": "Not many of us have talked about this yet.",
        "thin_facts": "Here's what studies and polls say.",
        "thin_unknown": "We don't know.",
        "thin_invite": "Want to be one of the first?",
        "close": "Thank you. Your words are with us now.",
        "fallback": "We don't know yet.",
        "safety_1": "This sounds really hard, and it matters more than any debate.",
        "safety_2": "You don't have to carry this alone. Telefono Amico Italia is there on 02 2327 2327. In danger right now, call 112.",
        "safety_3": "We're here if you want to keep talking.",
        "place_milan": "Milan",
        "report_ok": "Thanks. A person will look at this.",
    },
    "it": {
        "listen_open": "A cosa stai pensando?",
        "listen_more": "Raccontaci di più. Perché lo dici?",
        "listen_why": "Cosa dovrebbe cambiare per te?",
        "listen_topic": "{topic}. Tu da che parte stai?",
        "mirror_heard": "Ecco cosa abbiamo sentito. Giusto?",
        "mirror_hint": "Non proprio? Dillo pure, o tocca una riga per correggerla.",
        "mirror_thanks": "Grazie. L'abbiamo corretto.",
        "you_are": "Sei tra {group}",
        "stand_yes": "Il {pct}% di noi a {place} è d'accordo: {statement}.",
        "stand_no": "Il {pct}% di noi a {place} non è d'accordo: {statement}.",
        "stand_other": "Circa il {other_pct}% di noi dice che {summary}. Vuoi sapere perché?",
        "stand_source": "Da persone di {place}",
        "stand_paused": "Abbiamo sospeso i nostri numeri qui fino alla fine del voto.",
        "challenge_intro": "Lascia che parli come chi non è d'accordo con te.",
        "challenge_foot": "Costruito solo da ciò che ha detto questo gruppo. Il {pct}% di noi a {place}.",
        "inform_intro": "Ecco cosa dicono i numeri. Questi sono dati, non ciò che pensa qualcuno di noi.",
        "bridge_intro": "Ecco qualcosa che entrambi i gruppi potrebbero accettare.",
        "bridge_ask": "Tu lo accetteresti?",
        "thin_topic": "Non molti di noi hanno parlato di {topic}, finora.",
        "thin_general": "Non molti di noi hanno parlato di questo, finora.",
        "thin_facts": "Ecco cosa dicono studi e sondaggi.",
        "thin_unknown": "Non lo sappiamo.",
        "thin_invite": "Vuoi essere tra i primi?",
        "close": "Grazie. Le tue parole ora sono con noi.",
        "fallback": "Non lo sappiamo ancora.",
        "safety_1": "Sembra davvero difficile, e conta più di qualsiasi dibattito.",
        "safety_2": "Non devi affrontarlo da solo o da sola. Telefono Amico Italia risponde allo 02 2327 2327. Se sei in pericolo adesso, chiama il 112.",
        "safety_3": "Siamo qui, se vuoi continuare a parlare.",
        "place_milan": "Milano",
        "report_ok": "Grazie. Una persona lo controllerà.",
    },
}

VALUE_WORDS = {
    "en": {"agree": "Agree", "partly": "Partly", "unsure": "Unsure", "disagree": "Disagree"},
    "it": {"agree": "D'accordo", "partly": "In parte", "unsure": "Incerto", "disagree": "Contrario"},
}


def say(language: str, key: str, **values) -> str:
    text = COPY.get(language, COPY["en"])[key]
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text
