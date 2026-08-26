from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.core.config import Settings


class CharacterDecision(BaseModel):
    """Field order is load-bearing.

    Structured output is generated top to bottom, so what sits above ``content``
    is decided before the line exists.
    ``appraisal`` (how the character reads the situation) and ``intent`` (what
    they therefore want to do) separate thinking from speaking, so the phrasing
    cannot quietly drive the behaviour; ``requires_dm_resolution`` forces the
    model to decide whether this reaches outside the character's own control
    before the line exists. All of it is in-band: no extra request, no extra
    latency. ``appraisal`` and ``intent`` are never persisted or shown.
    """

    decision: Literal["SILENCE", "RESPOND"]
    appraisal: str = Field(default="", max_length=200)
    intent: str = Field(default="", max_length=200)
    action_source: Literal["NONE", "SPELL"] = "NONE"
    source_name: str | None = Field(default=None, max_length=120)
    # Decided before the line is written, not after. Sitting at the end of the
    # schema it was an afterthought the model filled in once the reply already
    # read like a complete turn, so questions to NPCs sailed through unflagged.
    requires_dm_resolution: bool = False
    resolution_request: str | None = Field(default=None, max_length=300)
    content: str = Field(default="", max_length=240)
    visibility: Literal["PUBLIC", "DM_ONLY"] = "PUBLIC"
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"] = "NORMAL"
    addressed_character_ids: list[str] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_shape(self) -> CharacterDecision:
        if self.decision == "RESPOND" and not self.content.strip():
            raise ValueError("RESPOND 必须包含角色发言。")
        if self.decision == "SILENCE" and self.requires_dm_resolution:
            raise ValueError("沉默时不能请求 DM 裁决。")
        if self.decision == "SILENCE" and self.content.strip():
            raise ValueError("SILENCE 不能包含角色发言。")
        if self.decision == "SILENCE" and self.action_source != "NONE":
            raise ValueError("沉默时不能使用法术。")
        if self.action_source == "SPELL" and not (self.source_name or "").strip():
            raise ValueError("使用法术时必须声明准确的法术名称。")
        if self.action_source == "NONE" and self.source_name is not None:
            raise ValueError("不使用法术时不能填写法术名称。")
        if self.requires_dm_resolution and not (self.resolution_request or "").strip():
            raise ValueError("请求 DM 裁决时必须说明需要裁决的事项。")
        return self


@dataclass(frozen=True, slots=True)
class CharacterAgentResult:
    decision: CharacterDecision
    input_tokens: int | None
    output_tokens: int | None


class CharacterAgent(Protocol):
    async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult: ...


class DeepSeekCharacterAgent:
    """One provider client, one Agent per call.

    The instructions are the character's own persona, so they cannot live in a
    module-level constant shared by everyone. Building the Agent per call is
    cheap; building the HTTP client is not, so only the client is reused.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.character_agent_is_configured:
            raise RuntimeError("DeepSeek 角色 Agent 尚未配置。")
        api_key = settings.deepseek_api_key
        assert api_key is not None
        client = AsyncOpenAI(
            api_key=api_key.get_secret_value(),
            base_url=settings.deepseek_base_url,
        )
        self._model = OpenAIChatModel(
            settings.character_model,
            provider=OpenAIProvider(openai_client=client),
        )
        self._model_settings = {
            "temperature": 0.75,
            # Raised from 400 to cover appraisal/intent without squeezing content.
            "max_tokens": 600,
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult:
        agent: Agent[None, CharacterDecision] = Agent(
            self._model,
            output_type=CharacterDecision,
            instructions=system_prompt,
            model_settings=self._model_settings,
            retries=1,
        )
        result = await agent.run(context)
        usage = result.usage
        return CharacterAgentResult(
            decision=result.output,
            input_tokens=usage.input_tokens or None,
            output_tokens=usage.output_tokens or None,
        )
