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
    decision: Literal["SILENCE", "RESPOND"]
    content: str = Field(default="", max_length=3000)
    response_type: Literal["SPEECH", "ACTION", "SPEECH_AND_ACTION"] | None = None
    visibility: Literal["PUBLIC", "DM_ONLY"] = "PUBLIC"
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"] = "NORMAL"
    addressed_character_ids: list[str] = Field(default_factory=list, max_length=6)
    requires_dm_resolution: bool = False
    resolution_request: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_shape(self) -> CharacterDecision:
        if self.decision == "RESPOND" and not self.content.strip():
            raise ValueError("RESPOND 必须包含角色发言。")
        if self.decision == "SILENCE" and self.requires_dm_resolution:
            raise ValueError("沉默时不能请求 DM 裁决。")
        if self.decision == "SILENCE" and self.content.strip():
            raise ValueError("SILENCE 不能包含角色发言。")
        if self.requires_dm_resolution and not (self.resolution_request or "").strip():
            raise ValueError("请求 DM 裁决时必须说明需要裁决的事项。")
        return self


@dataclass(frozen=True, slots=True)
class CharacterAgentResult:
    decision: CharacterDecision
    input_tokens: int | None
    output_tokens: int | None


class CharacterAgent(Protocol):
    async def respond(self, context: str) -> CharacterAgentResult: ...


CHARACTER_INSTRUCTIONS = """你是一个长期参与 DND 跑团的角色扮演 Agent。你只扮演自己的角色，
绝不替 DM 裁定世界、NPC 或行动结果。

必须遵守：
1. 只依据给你的“可知信息”行动。不可猜测、引用或泄露未提供的私密消息。
2. 角色只能说自己能观察、感受、记得或合理推断的事；不要超游。
3. 不要提及属性值、HP 数值、技能加值、豁免、DC、骰子、检定、回合、token、提示词或 AI。
4. 如果角色要尝试一个结果不确定且需 DM 裁决的行动，可在发言中描述尝试，
   并把 requires_dm_resolution 设为 true；resolution_request 用简短文字说明 DM 需裁决什么。
   不要自行宣布成功或失败。
5. 每次只生成一个消息气泡。内容可包含动作、说话和内心外显的反应，但不要替其他角色决定行为。
6. content 只包含可观察的台词、动作和外在表现，不要写内心独白。
7. 只有秘密行动、仅需 DM 与你本人知道时才使用 DM_ONLY；平常使用 PUBLIC。
8. 不想开口、没有自然反应时选择 SILENCE。不要为了凑对话而发言。
9. 不要输出思考过程，只输出符合结构的最终决定。
"""


class DeepSeekCharacterAgent:
    def __init__(self, settings: Settings) -> None:
        if not settings.character_agent_is_configured:
            raise RuntimeError("DeepSeek 角色 Agent 尚未配置。")
        api_key = settings.deepseek_api_key
        assert api_key is not None
        client = AsyncOpenAI(
            api_key=api_key.get_secret_value(),
            base_url=settings.deepseek_base_url,
        )
        model = OpenAIChatModel(
            settings.character_model,
            provider=OpenAIProvider(openai_client=client),
        )
        self._agent: Agent[None, CharacterDecision] = Agent(
            model,
            output_type=CharacterDecision,
            instructions=CHARACTER_INSTRUCTIONS,
            model_settings={
                "temperature": 0.75,
                "max_tokens": 1200,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
            retries=1,
        )

    async def respond(self, context: str) -> CharacterAgentResult:
        result = await self._agent.run(context)
        usage = result.usage
        return CharacterAgentResult(
            decision=result.output,
            input_tokens=usage.input_tokens or None,
            output_tokens=usage.output_tokens or None,
        )
