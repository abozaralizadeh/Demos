import contextlib
import uuid

import pytest
from fastapi.testclient import TestClient

from demos import api, identity_service, tokens
from demos.config import settings
from demos.db import connect


@pytest.fixture(scope="module")
def client(seeded):
    with TestClient(api.app) as c:
        yield c


@pytest.fixture(scope="module")
def identity(seeded):
    with TestClient(identity_service.app) as c:
        yield c


def sign_in(client, identity, code=None):
    code = code or uuid.uuid4().hex[:16]
    check = identity.post("/verify/dev", json={"tax_code": code, "born": "1990-01-01"})
    assert check.status_code == 200
    token = client.post("/v1/session", json={"assertion": check.json()["assertion"], "language": "en"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}, code


def consent(client, h):
    assert client.post("/v1/consent", headers=h).status_code == 200


def test_under_18_is_turned_away(identity):
    assert identity.post("/verify/dev", json={"tax_code": "X", "born": "2015-01-01"}).status_code == 403


def test_one_person_one_account(client, identity):
    code = uuid.uuid4().hex
    first = identity.post("/verify/dev", json={"tax_code": code, "born": "1990-01-01"}).json()
    again = identity.post("/verify/dev", json={"tax_code": code.upper(), "born": "1990-01-01"}).json()
    assert first["new"] and not again["new"]
    a = tokens.verify(settings().assertion_secret, first["assertion"])
    b = tokens.verify(settings().assertion_secret, again["assertion"])
    assert a["person_id"] == b["person_id"]


def test_the_vault_holds_no_tax_code(identity):
    code = "RSSMRA80A01F205X"
    identity.post("/verify/dev", json={"tax_code": code, "born": "1980-01-01"})
    with connect(settings().identity_database_url) as conn:
        rows = conn.execute("SELECT * FROM identity_link").fetchall()
    assert rows and not any(code in str(r) for r in rows)


def test_forged_tokens_are_refused(client):
    assert client.get("/v1/open", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    forged = tokens.sign("wrong", {"person_id": str(uuid.uuid4())}, 100)
    assert client.get("/v1/open", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert client.post("/v1/session", json={"assertion": forged}).status_code == 401


def test_no_talk_without_consent(client, identity):
    h, _ = sign_in(client, identity)
    assert client.post("/v1/talk", headers=h, json={}).status_code == 403
    consent(client, h)
    assert client.post("/v1/talk", headers=h, json={}).status_code == 200


def test_map_and_you_unlock_after_mirror(client, identity):
    h, _ = sign_in(client, identity)
    consent(client, h)
    assert client.get("/v1/map", headers=h).status_code == 403
    cid = client.post("/v1/talk", headers=h, json={}).json()["conversation_id"]
    client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "Rent is too high in Milan."})
    client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "The rent keeps going up."})
    done = client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "Yes"}).json()
    assert done["unlocked"]
    assert len(client.get("/v1/map", headers=h).json()["topics"]) >= 8
    assert client.get("/v1/you", headers=h).json()["views"]
    assert client.get("/v1/open", headers=h).json()["unlocked"]


def test_someone_else_cannot_touch_my_talk(client, identity):
    mine, _ = sign_in(client, identity)
    theirs, _ = sign_in(client, identity)
    consent(client, mine)
    consent(client, theirs)
    cid = client.post("/v1/talk", headers=mine, json={}).json()
    assert client.post(f"/v1/talk/{cid['conversation_id']}/say", headers=theirs, json={"text": "hi"}).status_code == 404
    assert client.post("/v1/report", headers=theirs, json={"turn_id": cid["turn_id"]}).status_code == 404


def test_people_can_report_a_reply(client, identity):
    h, _ = sign_in(client, identity)
    consent(client, h)
    talk = client.post("/v1/talk", headers=h, json={}).json()
    assert client.post("/v1/report", headers=h, json={"turn_id": talk["turn_id"]}).status_code == 200


def test_delete_really_deletes(client, identity):
    h, code = sign_in(client, identity)
    consent(client, h)
    cid = client.post("/v1/talk", headers=h, json={}).json()["conversation_id"]
    secret = "Rent is unique-marker-words too high."
    client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": secret})
    export = client.get("/v1/export", headers=h).json()
    assert any("unique-marker-words" in t["text"] for t in export["transcripts"])

    pid = tokens.verify(settings().session_secret, h["Authorization"].removeprefix("Bearer "))["person_id"]
    real = api.identity_client
    api.identity_client = lambda: contextlib.nullcontext(identity)
    try:
        assert client.delete("/v1/me", headers=h).status_code == 200
    finally:
        api.identity_client = real

    assert client.get("/v1/open", headers=h).status_code == 401
    with connect() as conn:
        for table in ("consent", "stance", "claim", "conversation"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE person_id = %s", (pid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM turn WHERE text LIKE '%unique-marker-words%'").fetchone()["n"] == 0
    with connect(settings().identity_database_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM identity_link WHERE person_id = %s", (pid,)).fetchone()["n"] == 0


def test_public_agreement_page_needs_no_account(client):
    with connect() as conn:
        a = conn.execute("SELECT id FROM agreement WHERE state = 'live' LIMIT 1").fetchone()
    page = client.get(f"/a/{a['id']}?lang=en")
    assert page.status_code == 200
    assert "not all of Milan" in page.text and "Set-Cookie" not in page.headers


def unlock(client, h) -> str:
    cid = client.post("/v1/talk", headers=h, json={}).json()["conversation_id"]
    client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "Rent is too high in Milan."})
    client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "The rent keeps going up."})
    assert client.post(f"/v1/talk/{cid}/say", headers=h, json={"text": "Yes"}).json()["unlocked"]
    return cid


def test_withdrawing_consent_drops_views_but_keeps_the_sign_in(client, identity):
    h, _ = sign_in(client, identity)
    consent(client, h)
    unlock(client, h)
    pid = tokens.verify(settings().session_secret, h["Authorization"].removeprefix("Bearer "))["person_id"]
    client.patch("/v1/settings", headers=h, json={"notifications": True})
    assert client.post("/v1/consent/withdraw", headers=h).status_code == 200
    opened = client.get("/v1/open", headers=h).json()
    assert not opened["consented"] and not opened["unlocked"] and not opened["notifications"]
    assert client.post("/v1/talk", headers=h, json={}).status_code == 403
    with connect() as conn:
        for table in ("stance", "conversation", "claim"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE person_id = %s", (pid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM consent WHERE person_id = %s AND withdrawn_at IS NULL", (pid,)).fetchone()["n"] == 0
    consent(client, h)
    assert client.get("/v1/open", headers=h).json()["consented"]


def test_source_detail_says_when_a_fact_is_a_placeholder(client, identity):
    h, _ = sign_in(client, identity)
    consent(client, h)
    with connect() as conn:
        fid = conn.execute("SELECT id FROM fact WHERE topic_id = 'rent' ORDER BY id LIMIT 1").fetchone()["id"]
    fact = client.get(f"/v1/facts/{fid}", headers=h).json()
    assert fact["placeholder"] and fact["source_name"] == "[SOURCE NAME]" and not fact["reviewed"]
    assert client.get("/v1/facts/999999", headers=h).status_code == 404


def test_preview_features_stay_off_by_default(client, identity):
    h, _ = sign_in(client, identity)
    consent(client, h)
    unlock(client, h)
    assert not client.get("/v1/open", headers=h).json()["preview"]
    assert client.get("/v1/map?area=italy", headers=h).status_code == 404
    assert client.patch("/v1/settings", headers=h, json={"anonymous": False, "display_name": "Ada"}).status_code == 404
    with connect() as conn:
        a = conn.execute("SELECT id FROM agreement WHERE state = 'live' LIMIT 1").fetchone()["id"]
    assert client.post(f"/v1/agreements/{a}/sign", headers=h).status_code == 404
    assert client.get(f"/v1/agreements/{a}", headers=h).json()["petition"] is None


def test_a_petition_needs_a_name_and_going_anonymous_takes_it_off(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), "preview_features", True)
    h, _ = sign_in(client, identity)
    consent(client, h)
    unlock(client, h)
    assert len(client.get("/v1/map?area=world", headers=h).json()["topics"]) == 4
    with connect() as conn:
        a = conn.execute("SELECT id FROM agreement WHERE state = 'live' LIMIT 1").fetchone()["id"]
    assert client.post(f"/v1/agreements/{a}/sign", headers=h).status_code == 409
    assert client.patch("/v1/settings", headers=h, json={"anonymous": False}).status_code == 422
    assert client.patch("/v1/settings", headers=h, json={"anonymous": False, "display_name": "  Ada   Rossi "}).status_code == 200
    assert client.post(f"/v1/agreements/{a}/sign", headers=h).json() == {"signed": True}
    assert client.get(f"/v1/agreements/{a}", headers=h).json()["petition"]["signed"]
    assert "Ada Rossi" in client.get(f"/a/{a}?lang=en").text
    client.patch("/v1/settings", headers=h, json={"anonymous": True})
    assert "Ada Rossi" not in client.get(f"/a/{a}?lang=en").text
    assert not client.get(f"/v1/agreements/{a}", headers=h).json()["petition"]["signed"]


def test_review_console_is_locked(client):
    assert client.get("/review").status_code == 401
    assert client.get("/review", auth=("reviewer", "wrong")).status_code == 401
    assert client.get("/review", auth=("reviewer", settings().review_token)).status_code == 200


def test_the_test_page_and_health_work_without_an_account(client):
    page = client.get("/")
    assert page.status_code == 200 and "Dev sign-in" in page.text
    # Every call in the page is relative, so it keeps working under a path like /demos/.
    assert 'fetch("/' not in page.text and "call(\"/" not in page.text
    health = client.get("/health").json()
    assert health["ok"] and health["ai"] == "templates" and health["sample"]


def test_dev_sign_in_goes_through_the_api(client, identity, monkeypatch):
    monkeypatch.setattr(api, "identity_client", lambda: contextlib.nullcontext(identity))
    token = client.post("/v1/dev/sign-in", json={"language": "en"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    consent(client, h)
    talk = client.post("/v1/talk", headers=h, json={})
    assert talk.status_code == 200 and talk.json()["lines"]


def test_dev_sign_in_is_gone_when_dev_identity_is_off(client, monkeypatch):
    monkeypatch.setattr(settings(), "dev_identity", False)
    assert client.post("/v1/dev/sign-in", json={}).status_code == 404


def test_too_many_talks_from_one_address_get_a_polite_no(client, identity, monkeypatch):
    h, _ = sign_in(client, identity)
    consent(client, h)
    monkeypatch.setattr(settings(), "rate_talk_per_ip_per_hour", 2)
    monkeypatch.setattr(api, "limiter", api.RateLimiter())
    assert client.post("/v1/talk", headers=h, json={}).status_code == 200
    assert client.post("/v1/talk", headers=h, json={}).status_code == 200
    third = client.post("/v1/talk", headers=h, json={})
    assert third.status_code == 429 and "Give us a minute" in third.json()["detail"]


def test_sign_ins_from_one_address_are_capped(client, identity, monkeypatch):
    monkeypatch.setattr(api, "identity_client", lambda: contextlib.nullcontext(identity))
    monkeypatch.setattr(settings(), "rate_signin_per_ip_per_hour", 1)
    monkeypatch.setattr(api, "limiter", api.RateLimiter())
    assert client.post("/v1/dev/sign-in", json={"language": "it"}).status_code == 200
    again = client.post("/v1/dev/sign-in", json={"language": "it"})
    assert again.status_code == 429 and "Aspetta un minuto" in again.json()["detail"]
