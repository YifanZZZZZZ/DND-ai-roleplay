from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.core.config import Settings


class SummaryDecision(BaseModel):
    summary: str = Field(min_length=1, max_length=12000)
    memories: list[str] = Field(default_factory=list, max_length=8)


@dataclass(frozen=True, slots=True)
class SummaryAgentResult:
    output: SummaryDecision
    input_tokens: int | None
    output_tokens: int | None


class DeepSeekSummaryAgent:
    def __init__(self, settings: Settings) -> None:
        if not settings.summary_agent_is_configured:
            raise RuntimeError("摘要 Agent 尚未配置。")
        key = settings.deepseek_api_key
        assert key is not None
        client = AsyncOpenAI(
            api_key=key.get_secret_value(),
            base_url=settings.deepseek_base_url,
        )
        model = OpenAIChatModel(
            settings.summary_model,
            provider=OpenAIProvider(openai_client=client),
        )
        self._agent: Agent[None, SummaryDecision] = Agent(
            model,
            output_type=SummaryDecision,
            instructions=(
                "你负责整理一个 DND 角色实际可知的 Session 记录。只能使用输入内容，"
                "不得补充未知事实、规则结果或数值。摘要应简洁，"
                "memories 只保留值得跨战役记住的事实。"
            ),
            model_settings={
                "temperature": 0.2,
                "max_tokens": 1800,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
            retries=1,
        )

    async def summarize(self, context: str) -> SummaryAgentResult:
        result = await self._agent.run(context)
        usage = result.usage
        return SummaryAgentResult(
            output=result.output,
            input_tokens=usage.input_tokens or None,
            output_tokens=usage.output_tokens or None,
        )
