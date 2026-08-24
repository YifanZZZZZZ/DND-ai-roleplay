"""One-off extraction of named NPCs from the raw module text."""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.core.config import Settings


class NpcCard(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=400)
    personality: str = Field(default="", max_length=800)
    ideal: str = Field(default="", max_length=400)
    bond: str = Field(default="", max_length=400)
    flaw: str = Field(default="", max_length=400)
    knows: str = Field(default="", max_length=1200)
    wants: str = Field(default="", max_length=600)
    voice: str = Field(default="", max_length=600)


class NpcExtraction(BaseModel):
    npcs: list[NpcCard] = Field(default_factory=lambda: list[NpcCard](), max_length=40)


@dataclass(frozen=True, slots=True)
class NpcExtractionResult:
    output: NpcExtraction


NPC_INSTRUCTIONS = """你从一份 DND 模组原文里抽取有名字的 NPC，做成卡片供 AI DM 参考。

规则：
1. 只抽取模组里出现了姓名的 NPC。无名的路人、群体、怪物种类不要抽取。
2. 每个字段只能填模组原文明确写了的内容。原文没写的字段留空字符串，绝对不要推测或补写。
3. role 填身份、种族、阵营、年龄、职业等能说清他是谁的信息。
4. personality / ideal / bond / flaw 对应模组里的个性特点、理想、牵绊、缺陷；
   若模组用的是别的写法，按同样的语义归类。
5. knows 填这个 NPC 知道、并且可能告诉冒险者的信息。
6. wants 填他想要什么、会向冒险者提出什么请求。
7. voice 填模组描述的说话方式与外在表现；没有描述就留空。
8. 已经死亡或失踪、但在剧情中会被反复提到的人物也要抽取，在 role 里注明。
9. 保持原文的人名写法，不要翻译或改写。
10. 只输出结构化结果。
"""


class DeepSeekNpcAgent:
    def __init__(self, settings: Settings) -> None:
        if not settings.dm_agent_is_configured:
            raise RuntimeError("NPC 提取 Agent 尚未配置。")
        key = settings.deepseek_api_key
        assert key is not None
        client = AsyncOpenAI(
            api_key=key.get_secret_value(), base_url=settings.deepseek_base_url
        )
        model = OpenAIChatModel(
            settings.dm_model_name, provider=OpenAIProvider(openai_client=client)
        )
        self._agent: Agent[None, NpcExtraction] = Agent(
            model,
            output_type=NpcExtraction,
            instructions=NPC_INSTRUCTIONS,
            model_settings={
                "temperature": 0.1,
                "max_tokens": 6000,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
            retries=1,
        )

    async def extract(self, module_text: str) -> NpcExtractionResult:
        result = await self._agent.run(module_text)
        return NpcExtractionResult(output=result.output)
