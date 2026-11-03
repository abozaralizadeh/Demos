"""Sample data, so the app has something real to compute from.

Every number in the app comes from these rows through the same code real data
will use. They are made up, so the app labels them "Sample data", and facts stay
as visible placeholders. Run with: python -m demos.seed
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from .config import settings
from .db import connect, migrate
from .worker import update_links

PEOPLE = 1240

# id, en, it, x, y, tilt, people, (group a, group b), agree % in each
TOPICS = [
    ("rent", "Rent", "Affitti", 140, 176, -18, 600, ("renters", "owners"), (80, 30)),
    ("wages", "Wages", "Stipendi", 292, 96, -12, 248, ("employees", "employers"), (85, 18)),
    ("cars", "Cars in the center", "Auto in centro", 300, 262, 25, 230, ("drivers", "non_drivers"), (10, 90)),
    ("transport", "Public transport", "Trasporti pubblici", 70, 58, 10, 150, ("riders", "non_riders"), (70, 38)),
    ("short_rentals", "Short-term rentals", "Affitti brevi", 108, 398, -8, 440, ("str_renters", "str_owners"), (71, 58)),
    ("bike_lanes", "Bike lanes", "Piste ciclabili", 272, 404, 14, 266, ("cyclists", "motorists"), (62, 56)),
    ("air", "Air quality", "Qualità dell'aria", 176, 44, 0, 110, ("parents", "non_parents"), (78, 59)),
    ("tourism", "Tourism", "Turismo", 196, 496, -20, 110, ("center", "outskirts"), (70, 30)),
    ("schools", "Schools", "Scuole", 330, 498, 0, 14, (), ()),
]

# Italy and World only show with preview features on. Same shape as TOPICS.
AREA_TOPICS = {
    "italy": [
        ("min_wage", "Minimum wage", "Salario minimo", 130, 150, -15, 420, ("low_paid", "business_owners"), (82, 35)),
        ("pensions", "Pensions", "Pensioni", 292, 110, 10, 260, ("over_60", "under_35"), (75, 40)),
        ("young_leaving", "Young people leaving", "Giovani che partono", 150, 390, 5, 300, ("leavers", "stayers"), (70, 64)),
        ("nuclear", "Nuclear power", "Nucleare", 292, 320, -20, 180, ("north", "south"), (55, 45)),
    ],
    "world": [
        ("climate", "Climate action", "Azione per il clima", 140, 170, 12, 380, ("young", "older"), (78, 60)),
        ("ai_jobs", "AI and jobs", "IA e lavoro", 288, 110, -10, 240, ("tech_workers", "other_workers"), (60, 25)),
        ("social_kids", "Social media for kids", "Social per i ragazzi", 160, 400, 0, 290, ("parents_w", "non_parents_w"), (80, 70)),
        ("remote", "Remote work", "Lavoro da remoto", 292, 330, 20, 170, ("office", "remote_workers"), (30, 88)),
    ],
}

GROUPS = {
    "renters": ("renters", "chi è in affitto", ["i rent", "my landlord", "my rent", "pay half my salary", "sono in affitto", "pago l'affitto", "il mio padrone di casa"]),
    "owners": ("owners", "i proprietari", ["i own my", "my flat is mine", "as a landlord", "sono proprietario", "sono proprietaria"]),
    "employees": ("employees", "i dipendenti", ["my salary", "my boss", "il mio stipendio", "il mio capo"]),
    "employers": ("employers", "i datori di lavoro", ["my company", "my employees", "la mia azienda", "i miei dipendenti"]),
    "drivers": ("drivers", "chi guida", ["i drive", "my car", "guido", "la mia auto"]),
    "non_drivers": ("people who don't drive", "chi non guida", ["i don't drive", "non guido"]),
    "riders": ("people who ride transit", "chi usa i mezzi", ["i take the metro", "i take the tram", "prendo la metro", "prendo il tram"]),
    "non_riders": ("people who don't ride transit", "chi non usa i mezzi", ["i never take the metro", "non prendo mai i mezzi"]),
    "str_renters": ("renters", "chi è in affitto", []),
    "str_owners": ("owners", "i proprietari", []),
    "cyclists": ("cyclists", "chi va in bici", ["i cycle", "my bike", "vado in bici", "la mia bici"]),
    "motorists": ("motorists", "chi va in auto", []),
    "parents": ("parents", "i genitori", ["my kids", "my children", "i miei figli"]),
    "non_parents": ("people without kids", "chi non ha figli", []),
    "center": ("people in the center", "chi vive in centro", ["i live in the center", "vivo in centro"]),
    "outskirts": ("people outside the center", "chi vive fuori dal centro", ["i live outside", "vivo in periferia"]),
    "low_paid": ("people on low pay", "chi guadagna poco", []),
    "business_owners": ("business owners", "chi ha un'impresa", []),
    "over_60": ("people over 60", "chi ha più di 60 anni", []),
    "under_35": ("people under 35", "chi ha meno di 35 anni", []),
    "leavers": ("people thinking of leaving", "chi pensa di partire", []),
    "stayers": ("people staying", "chi resta", []),
    "north": ("people in the north", "chi vive al nord", []),
    "south": ("people in the south", "chi vive al sud", []),
    "young": ("people under 30", "chi ha meno di 30 anni", []),
    "older": ("people over 30", "chi ha più di 30 anni", []),
    "tech_workers": ("people in tech", "chi lavora nella tecnologia", []),
    "other_workers": ("people in other jobs", "chi fa altri lavori", []),
    "parents_w": ("parents", "i genitori", []),
    "non_parents_w": ("people without kids", "chi non ha figli", []),
    "office": ("people who like the office", "chi preferisce l'ufficio", []),
    "remote_workers": ("people who work from home", "chi lavora da casa", []),
}

# id, topic, en, it, question en, question it, keywords, main?
STATEMENTS = [
    ("rent_main", "rent", "Rent is the main problem", "L'affitto è il problema principale", None, None, ["rent", "affitt", "canone"], True),
    ("rent_cap", "rent", "The city should cap rents", "Il Comune dovrebbe mettere un tetto agli affitti", None, None, ["cap", "tetto", "limite agli affitti"], False),
    ("rent_build", "rent", "Building more would fix it", "Costruire di più lo risolverebbe", None, None, ["build more", "building more", "costruire"], False),
    ("wages_main", "wages", "Pay in Milan is too low", "Gli stipendi a Milano sono troppo bassi", None, None, ["wage", "pay is", "salari", "stipendi", "stipendio"], True),
    ("cars_main", "cars", "The center should be car free", "Il centro dovrebbe essere senza auto", "Should the center be car free?", "Il centro dovrebbe essere senza auto?", ["car free", "cars in the center", "senza auto", "auto in centro", "area c"], True),
    ("transport_main", "transport", "Public transport should run later at night", "I mezzi pubblici dovrebbero fare più tardi la notte", "Should public transport run later at night?", "I mezzi dovrebbero fare più tardi la notte?", ["metro", "tram", "public transport", "mezzi pubblici", "trasporti"], True),
    ("str_main", "short_rentals", "Milan should limit short-term rentals in the center, with exceptions for residents", "Milano dovrebbe limitare gli affitti brevi in centro, con eccezioni per i residenti", None, None, ["short-term rental", "short term rental", "airbnb", "affitti brevi"], True),
    ("bike_main", "bike_lanes", "Milan should build more bike lanes", "Milano dovrebbe costruire più piste ciclabili", "Does Milan need more bike lanes?", "Milano ha bisogno di più piste ciclabili?", ["bike lane", "cycle lane", "pista ciclabile", "piste ciclabili"], True),
    ("air_main", "air", "Clean air should come before traffic", "L'aria pulita viene prima del traffico", None, None, ["air quality", "pollution", "smog", "inquinamento", "aria"], True),
    ("tourism_main", "tourism", "Milan has too many tourists", "A Milano ci sono troppi turisti", None, None, ["tourist", "turist"], True),
    ("schools_main", "schools", "Milan's schools need more money", "Le scuole di Milano hanno bisogno di più fondi", None, None, ["school", "scuol"], True),
    ("min_wage_main", "min_wage", "Italy should have a minimum wage", "L'Italia dovrebbe avere un salario minimo", None, None, ["minimum wage", "salario minimo"], True),
    ("pensions_main", "pensions", "Pensions take too much from young people", "Le pensioni pesano troppo sui giovani", None, None, ["pension", "pensioni"], True),
    ("young_main", "young_leaving", "Young people leave because pay is too low", "I giovani partono perché gli stipendi sono troppo bassi", None, None, ["brain drain", "young people leaving", "fuga dei cervelli", "giovani che partono"], True),
    ("nuclear_main", "nuclear", "Italy should go back to nuclear power", "L'Italia dovrebbe tornare al nucleare", None, None, ["nuclear", "nucleare"], True),
    ("climate_main", "climate", "Climate should come before growth", "Il clima viene prima della crescita", None, None, ["climate", "clima"], True),
    ("ai_jobs_main", "ai_jobs", "AI will take more jobs than it makes", "L'IA toglierà più lavoro di quanto ne crei", None, None, ["artificial intelligence", "intelligenza artificiale", "ai and jobs"], True),
    ("social_main", "social_kids", "Kids under 16 shouldn't be on social media", "I ragazzi sotto i 16 anni non dovrebbero stare sui social", None, None, ["social media", "social network"], True),
    ("remote_main", "remote", "People should be free to work from home", "Le persone dovrebbero poter lavorare da casa", None, None, ["remote work", "work from home", "smart working", "lavoro da remoto"], True),
]

# statement, side, summary en/it, text en/it, people
ARGUMENTS = [
    ("rent_main", "against", "the real problem is wages, not rent", "il vero problema sono gli stipendi, non gli affitti",
     "We think rent is the symptom. Pay in Milan hasn't kept up, so every rent feels too high. Cap rents and landlords walk away. Fix pay and the problem shrinks.",
     "Pensiamo che l'affitto sia il sintomo. Gli stipendi a Milano non hanno tenuto il passo, quindi ogni affitto sembra troppo alto. Metti un tetto e i proprietari se ne vanno. Sistema gli stipendi e il problema si riduce.", 112),
    ("rent_main", "for", "rent eats half of a salary, and raises won't catch it", "l'affitto si mangia metà stipendio, e gli aumenti non lo raggiungono",
     "We think no raise can catch rents that climb every year. When half your pay goes to the landlord, everything else is a detail.",
     "Pensiamo che nessun aumento possa raggiungere affitti che salgono ogni anno. Quando metà dello stipendio va al proprietario, tutto il resto è un dettaglio.", 140),
    ("cars_main", "against", "people outside the center still need to get in", "chi vive fuori dal centro deve comunque poterci arrivare",
     "We think a car free center only works for people who live near it. Night workers and people from the outskirts still need to get in.",
     "Pensiamo che un centro senza auto funzioni solo per chi ci vive vicino. Chi lavora di notte e chi viene dalla periferia deve comunque poterci arrivare.", 64),
    ("cars_main", "for", "the streets belong to the people walking them", "le strade sono di chi le cammina",
     "We think the center works better when the streets belong to the people walking them. Shops, air and safety all gain.",
     "Pensiamo che il centro funzioni meglio quando le strade sono di chi le cammina. Ci guadagnano negozi, aria e sicurezza.", 71),
]

FACTS = [
    ("rent", "Rent in Milan vs pay", "Affitti a Milano e stipendi", "Rent in Milan", "Affitti a Milano", "+[X]%"),
    ("rent", "Rent in Milan vs pay", "Affitti a Milano e stipendi", "Average pay", "Stipendio medio", "+[Y]%"),
    ("schools", "Schools in Milan", "Scuole a Milano", "[FINDING FROM A STUDY OR POLL]", "[RISULTATO DI UNO STUDIO O SONDAGGIO]", ""),
    ("cars", "Traffic in the center", "Traffico in centro", "Cars entering per day", "Auto al giorno", "[X]"),
]


def clear(cur) -> None:
    cur.execute(
        "TRUNCATE safety_event, reply_failure, opening_seen, election, proposed_topic, report, fact,"
        " agreement_action, petition_signature, send_request, agreement_snapshot, agreement, bridge_source, bridge, exposure,"
        " argument_source, claim, argument, stance, turn, conversation, group_member, grp, topic_link,"
        " statement, topic, consent, person CASCADE"
    )


def seed(conn) -> None:
    if not settings().sample_data:
        raise SystemExit("Sample data is off here. Refusing to seed.")
    rng = random.Random(20261102)
    cur = conn.cursor()
    clear(cur)

    people = [uuid.uuid4() for _ in range(PEOPLE)]
    with cur.copy("COPY person (id, is_sample, unlocked) FROM STDIN") as copy:
        for p in people:
            copy.write_row((p, True, True))

    every = [(t, "milan") for t in TOPICS] + [(t, area) for area, ts in AREA_TOPICS.items() for t in ts]
    for t, area in every:
        cur.execute(
            "INSERT INTO topic (id, title_en, title_it, layout_x, layout_y, tilt, area)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (*t[:6], area),
        )
    main_of = {}
    for sid, topic, en, it, q_en, q_it, keywords, is_main in STATEMENTS:
        cur.execute(
            "INSERT INTO statement (id, topic_id, text_en, text_it, question_en, question_it, keywords)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (sid, topic, en, it, q_en, q_it, keywords),
        )
        if is_main:
            main_of[topic] = sid
            cur.execute("UPDATE topic SET main_statement_id = %s WHERE id = %s", (sid, topic))

    for t, _ in every:
        for g in t[7]:
            en, it, keywords = GROUPS[g]
            cur.execute(
                "INSERT INTO grp (id, topic_id, label_en, label_it, keywords) VALUES (%s, %s, %s, %s, %s)",
                (g, t[0], en, it, keywords),
            )

    stances, members = [], []
    joined = datetime.now(timezone.utc) - timedelta(days=40)
    for (tid, _, _, _, _, _, size, groups, shares), _ in every:
        crowd = rng.sample(people, size)
        sid = main_of[tid]
        if not groups:
            stances += [(p, sid, rng.choice(["agree", "partly", "unsure"]), joined) for p in crowd]
            continue
        half = size // 2
        for group, share, part in zip(groups, shares, (crowd[:half], crowd[half:])):
            yes = round(share / 100 * len(part))
            for i, person in enumerate(part):
                if i < yes:
                    value = "agree"
                else:
                    # Rent's 18% against is the design's number, so most of the rest stay undecided there.
                    no_share = 0.45 if tid == "rent" else 0.7
                    value = "disagree" if rng.random() < no_share else rng.choice(["partly", "unsure"])
                stances.append((person, sid, value, joined))
                members.append((group, person))

    with cur.copy("COPY stance (person_id, statement_id, value, state, valid_from) FROM STDIN") as copy:
        for person, sid, value, at in stances:
            copy.write_row((person, sid, value, "confirmed", at))
    with cur.copy("COPY group_member (group_id, person_id, source) FROM STDIN") as copy:
        for group, person in members:
            copy.write_row((group, person, "sample"))

    for sid, side, s_en, s_it, t_en, t_it, n in ARGUMENTS:
        topic = next(s[1] for s in STATEMENTS if s[0] == sid)
        a = cur.execute(
            "INSERT INTO argument (topic_id, statement_id, side, summary_en, summary_it, text_en, text_it, state, reviewed_by, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', 'sample', %s) RETURNING id",
            (topic, sid, side, s_en, s_it, t_en, t_it, joined),
        ).fetchone()["id"]
        for p in rng.sample(people, n):
            cur.execute("INSERT INTO argument_source (argument_id, person_id) VALUES (%s, %s)", (a, p))

    for topic, ti_en, ti_it, l_en, l_it, value in FACTS:
        cur.execute(
            "INSERT INTO fact (topic_id, title_en, title_it, label_en, label_it, value, source_name, year, is_placeholder, reviewed_by)"
            " VALUES (%s, %s, %s, %s, %s, %s, '[SOURCE NAME]', '[YEAR]', true, 'sample')",
            (topic, ti_en, ti_it, l_en, l_it, value),
        )

    cur.execute("INSERT INTO bridge (topic_id, statement_id) VALUES ('rent', 'str_main')")
    long_ago = datetime.now(timezone.utc) - timedelta(days=21)
    agreement = cur.execute(
        "INSERT INTO agreement (statement_id, topic_id, state, since, live_since)"
        " VALUES ('str_main', 'short_rentals', 'live', %s, %s) RETURNING id",
        (long_ago, long_ago + timedelta(days=14)),
    ).fetchone()["id"]
    cur.execute(
        "INSERT INTO agreement_snapshot (agreement_id, label, support_pct, base, at) VALUES (%s, 'overall', 62, 400, %s)",
        (agreement, long_ago),
    )
    update_links(cur)
    conn.commit()


def main() -> None:
    with connect() as conn:
        migrate(conn)
        seed(conn)
    print(f"Seeded {PEOPLE} sample people.")


if __name__ == "__main__":
    main()
