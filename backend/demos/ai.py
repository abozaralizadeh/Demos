"""Which model the World uses, and the daily budget it can't go past.

Azure OpenAI is used when its three settings are there, then Claude when
ANTHROPIC_API_KEY is, and otherwise none: the World talks with its templates.
Every call counts against DAILY_REQUEST_CAP and DAILY_TOKEN_BUDGET first, in
Postgres, so a restart doesn't reset the day.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel

from .config import settings
from .db import connect
from .writer import Declined, Reader, Writer

log = logging.getLogger("demos.ai")
T = TypeVar("T", bound=BaseModel)


class BudgetSpent(Exception):
    pass


class Budget:
    """Today's AI calls and tokens, shared by every process through the database."""

    def __init__(self, open_db=connect):
        self.open_db = open_db
        self.spent = False

    def check(self) -> None:
        cfg = settings()
        with self.open_db() as conn:
            row = conn.execute("SELECT requests, tokens FROM ai_usage WHERE day = CURRENT_DATE").fetchone()
        if row and (
            row["requests"] >= cfg.daily_request_cap
            or (cfg.daily_token_budget and row["tokens"] >= cfg.daily_token_budget)
        ):
            self.spent = True
            raise BudgetSpent()

    def spend(self, tokens: int) -> None:
        with self.open_db() as conn:
            conn.execute(
                "INSERT INTO ai_usage (day, requests, tokens) VALUES (CURRENT_DATE, 1, %s)"
                " ON CONFLICT (day) DO UPDATE SET requests = ai_usage.requests + 1,"
                " tokens = ai_usage.tokens + EXCLUDED.tokens",
                (tokens,),
            )
            conn.commit()


@dataclass(frozen=True)
class Target:
    endpoint: str
    api_key: str
    deployment: str


def azure_targets() -> list[Target]:
    cfg = settings()
    found = [
        Target(cfg.azure_endpoint, cfg.azure_api_key, cfg.azure_deployment),
        Target(cfg.azure_fallback_endpoint, cfg.azure_fallback_api_key, cfg.azure_fallback_deployment),
    ]
    return [t for t in found if t.endpoint and t.api_key and t.deployment]


class AzureAsk:
    """Azure OpenAI through the v1 chat completions API, with the fallback deployment second."""

    def __init__(self, targets: list[Target], budget: Budget, http: httpx.Client | None = None):
        self.targets = targets
        self.budget = budget
        self.http = http or httpx.Client(timeout=settings().ai_timeout)

    def __call__(self, system: str, prompt: str, out: type[T], max_tokens: int, fast: bool = False) -> T:
        shape = json.dumps(out.model_json_schema())
        system = f"{system}\n\nReply with one JSON object only, matching this JSON schema:\n{shape}"
        failed: Exception | None = None
        for target in self.targets:
            self.budget.check()
            tokens = 0
            try:
                r = self.http.post(
                    f"{target.endpoint.rstrip('/')}/openai/v1/chat/completions",
                    headers={"api-key": target.api_key},
                    json={
                        "model": target.deployment,
                        # Room for reasoning models, which spend tokens before they answer.
                        "max_completion_tokens": max_tokens * 2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                r.raise_for_status()
                data = r.json()
                tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
                message = data["choices"][0]["message"]
                if message.get("refusal"):
                    raise Declined()
                return out.model_validate_json(message.get("content") or "")
            except Declined:
                raise
            except Exception as e:
                log.warning("azure %s failed: %s", target.deployment, type(e).__name__)
                failed = e
            finally:
                self.budget.spend(tokens)
        raise failed or RuntimeError("no Azure deployment")


class ClaudeAsk:
    def __init__(self, budget: Budget, client=None):
        import anthropic

        self.budget = budget
        self.client = client or anthropic.Anthropic(timeout=settings().ai_timeout, max_retries=1)

    def __call__(self, system: str, prompt: str, out: type[T], max_tokens: int, fast: bool = False) -> T:
        self.budget.check()
        tokens = 0
        try:
            extra = {} if fast else {"output_config": {"effort": "low"}}
            response = self.client.messages.parse(
                model=settings().extract_model if fast else settings().world_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=out,
                **extra,
            )
            tokens = response.usage.input_tokens + response.usage.output_tokens
            if response.stop_reason == "refusal":
                raise Declined()
            return response.parsed_output
        finally:
            self.budget.spend(tokens)


def pick() -> tuple[Writer | None, Reader | None, Budget | None]:
    """The writer, reader and budget for one talk turn, or Nones when there's no model."""
    budget = Budget()
    targets = azure_targets()
    if targets:
        ask = AzureAsk(targets, budget)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        ask = ClaudeAsk(budget)
    else:
        return None, None, None
    return Writer(ask), Reader(ask), budget


def provider() -> str:
    if azure_targets():
        return "azure"
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "templates"
