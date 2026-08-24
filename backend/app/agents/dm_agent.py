from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.core.config import Settings


class DmDecision(BaseModel):
    content: str = Field(min_length=1, max_length=800)
    audience: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"
    recipient_character_ids: list[str] = Field(
        default_factory=lambda: list[str](), max_length=6
    )
    # What the model added on its own initiative. The DM is allowed to let the
    # agent voice NPCs and invent scenery, which only works if checking what it
    # invented is cheap — so it has to declare it rather than bury it in prose.
    improvised_notes: list[str] = Field(
        default_factory=lambda: list[str](), max_length=8
    )


@dataclass(frozen=True, slots=True)
class DmAgentResult:
    output: DmDecision
    input_tokens: int | None = None
    output_tokens: int | None = None


class DmAgent(Protocol):
    async def draft(self, system_prompt: str, context: str) -> DmAgentResult: ...


class DeepSeekDmAgent:
    def __init__(self, settings: Settings) -> None:
        if not settings.dm_agent_is_configured:
            raise RuntimeError("AI DM 尚未配置。")
        key = settings.deepseek_api_key
        assert key is not None
        client = AsyncOpenAI(
            api_key=key.get_secret_value(), base_url=settings.deepseek_base_url
        )
        self._model = OpenAIChatModel(
            settings.dm_model_name, provider=OpenAIProvider(openai_client=client)
        )
        self._model_settings = {
            "temperature": 0.65,
            "max_tokens": 900,
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    async def draft(self, system_prompt: str, context: str) -> DmAgentResult:
        agent: Agent[None, DmDecision] = Agent(
            self._model,
            output_type=DmDecision,
            instructions=system_prompt,
            model_settings=self._model_settings,
            retries=1,
        )
        result = await agent.run(context)
        usage = result.usage
        return DmAgentResult(
            output=result.output,
            input_tokens=usage.input_tokens or None,
            output_tokens=usage.output_tokens or None,
        )
