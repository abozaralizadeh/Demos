import json

import httpx
import pytest

from demos import ai
from demos.config import settings
from demos.db import connect
from demos.engine import Engine
from demos.writer import Declined, ReadViews, Reader, Writer

MAIN = ai.Target("https://main.example", "k1", "gpt-6-luna")
SPARE = ai.Target("https://spare.example", "k2", "gpt-5-mini")


@pytest.fixture
def usage(seeded):
    """Today's AI usage starts empty and is cleared again afterwards."""
    with connect() as conn:
        conn.execute("DELETE FROM ai_usage")
        conn.commit()
    yield
    with connect() as conn:
        conn.execute("DELETE FROM ai_usage")
        conn.commit()


def today():
    with connect() as conn:
        return conn.execute("SELECT requests, tokens FROM ai_usage WHERE day = CURRENT_DATE").fetchone()


def fake_azure(answer, fail_hosts=(), calls=None):
    def handle(request: httpx.Request):
        if calls is not None:
            calls.append((request.url.host, json.loads(request.content)["model"], request.headers["api-key"]))
        if request.url.host in fail_hosts:
            return httpx.Response(500)
        return httpx.Response(200, json={
            "choices": [{"message": answer}],
            "usage": {"total_tokens": 120},
        })
    return httpx.Client(transport=httpx.MockTransport(handle))


def views_answer():
    return {"content": json.dumps({"views": [{"statement_id": "s1", "value": "agree", "quote": "rent"}]})}


def test_azure_answers_are_parsed_and_counted(usage):
    calls = []
    ask = ai.AzureAsk([MAIN], ai.Budget(), fake_azure(views_answer(), calls=calls))
    out = ask("system", "prompt", ReadViews, max_tokens=100)
    assert out.views[0].statement_id == "s1"
    assert calls == [("main.example", "gpt-6-luna", "k1")]
    assert today() == {"requests": 1, "tokens": 120}


def test_the_fallback_deployment_is_used_only_when_the_main_one_fails(usage):
    calls = []
    ask = ai.AzureAsk([MAIN, SPARE], ai.Budget(), fake_azure(views_answer(), {"main.example"}, calls))
    assert ask("system", "prompt", ReadViews, max_tokens=100).views
    assert [c[1] for c in calls] == ["gpt-6-luna", "gpt-5-mini"]
    assert today()["requests"] == 2


def test_a_refusal_is_a_decline(usage):
    ask = ai.AzureAsk([MAIN, SPARE], ai.Budget(), fake_azure({"content": None, "refusal": "no"}))
    with pytest.raises(Declined):
        ask("system", "prompt", ReadViews, max_tokens=100)


def test_nothing_is_sent_once_the_day_is_spent(usage, monkeypatch):
    monkeypatch.setattr(settings(), "daily_token_budget", 100)
    calls = []
    budget = ai.Budget()
    ask = ai.AzureAsk([MAIN], budget, fake_azure(views_answer(), calls=calls))
    ask("system", "prompt", ReadViews, max_tokens=100)
    with pytest.raises(ai.BudgetSpent):
        ask("system", "prompt", ReadViews, max_tokens=100)
    assert len(calls) == 1 and budget.spent


def test_the_request_cap_stops_calls_too(usage, monkeypatch):
    monkeypatch.setattr(settings(), "daily_request_cap", 1)
    ask = ai.AzureAsk([MAIN], ai.Budget(), fake_azure(views_answer()))
    ask("system", "prompt", ReadViews, max_tokens=100)
    with pytest.raises(ai.BudgetSpent):
        ask("system", "prompt", ReadViews, max_tokens=100)


def test_azure_is_picked_only_when_it_is_fully_set(monkeypatch):
    cfg = settings()
    assert ai.provider() == "templates" and ai.pick() == (None, None, None)
    monkeypatch.setattr(cfg, "azure_endpoint", "https://main.example")
    monkeypatch.setattr(cfg, "azure_api_key", "k")
    assert ai.provider() == "templates"
    monkeypatch.setattr(cfg, "azure_deployment", "gpt-6-luna")
    writer, reader, budget = ai.pick()
    assert ai.provider() == "azure" and isinstance(writer, Writer) and isinstance(reader, Reader) and budget


def test_when_the_day_is_spent_the_world_still_answers_and_says_so(conn, person, usage, monkeypatch):
    monkeypatch.setattr(settings(), "daily_request_cap", 0)
    budget = ai.Budget()
    ask = ai.AzureAsk([MAIN], budget, fake_azure(views_answer()))
    e = Engine(conn, writer=Writer(ask), reader=Reader(ask))
    e.budget = budget
    talk = e.start(person)
    reply = e.say(person, talk.conversation_id, "Rent in Milan is far too high for people like me")
    assert reply.lines and reply.notice and "plainer until tomorrow" in reply.notice
