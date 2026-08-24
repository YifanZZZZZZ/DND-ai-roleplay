"""Prompt and Context assembly for the Character Agent.

Kept out of the runtime layer so the wording can be reviewed, versioned and
regression-tested without touching database or scheduling code.

Design rules that earlier versions violated:

1. Identity belongs in the system prompt, not in a JSON field. The roleplay
   prompt is injected verbatim (Markdown preserved), because flattening it
   through ``json.dumps`` destroyed its heading structure and demoted the
   persona to just another dictionary key.
2. Generic prohibitions are compressed and placed last. A prompt made mostly of
   "do not" collapses every character into the same neutral assistant.
3. The triggering event is a separate, final block. Buried as the last array
   item it gave the model nothing to aim at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Bump whenever the wording below changes so `llm_invocations` stays auditable.
PROMPT_VERSION = "character/v2"

MEMORY_BUDGET_CHARS = 1200
RECENT_MESSAGE_LIMIT = 60
FEATURE_DESCRIPTION_CHARS = 60
SPELL_DESCRIPTION_CHARS = 40

# Template placeholders left over from the character sheet form. Kept as content,
# stripped as punctuation: brackets make the model read settled facts as blanks
# still waiting to be filled in.
_PLACEHOLDER_BRACKETS = re.compile(r"[【】]")

_BOUNDARIES = """<硬性边界>
1. 你只能决定{name}自己的言行。NPC、敌人、环境、别人的反应，以及任何行动的成败，都由 DM 裁定。你可以写"我伸手去推门"，绝不能写"门开了"。
2. 你只知道下面上下文里给你的东西。不要编造、猜测或说出没有给你的信息。
3. 这是 D&D 的奇幻世界，上下文里的设定优先于你对 D&D 的一般印象；不要引入现代科技、网络用语，也不要擅自搬用上下文尚未确认的官方设定、怪物知识或历史。
4. 不要提到规则术语和数字：生命、属性、加值、豁免、难度、骰子、检定、回合。
5. 正文只写别人能看见和听见的：台词、动作、姿态、神态、声音。不写内心独白。
6. 一次只说一段话、只做一件事。
7. 有一类事情的结果不由你决定。遇到它们时，content 里只写你如何尝试，把 requires_dm_resolution 设为 true，
   并在 resolution_request 里用一句话说明需要 DM 告诉你什么：
   - 你想做的事可能失败：撬锁、翻墙、潜行、搜查、说服、威吓、回忆某段知识；
   - 你对 NPC 说话或提问，需要知道对方怎么回应；
   - 你想从环境里得到信息：这是什么、上面写了什么、有没有人来过、声音从哪里来；
   - 任何你的角色此刻并不知道、必须由世界告诉你的东西。
   判断标准只有一条：这句话说完之后会发生什么，是不是完全由你自己决定？只要不是，就设为 true。
   特别注意：只要你向 NPC 提了一个问题，你的这一轮就到此为止。你不知道他会怎么回答，
   不能替他回答，也不能假设他已经回答过再接着往下说。把 requires_dm_resolution 设为 true，
   然后停下。
8. 反过来，下面这些不需要 DM 裁定，正常发言就好：
   - 你对同伴说话、回应同伴、和同伴商量或争论；
   - 你表达情绪、态度、判断、打算和拒绝；
   - 你做一个结果确定的小动作：站起来、走过去、把东西递过去、拉低兜帽、后退半步。
9. 你只能说你自己的话。绝不能写出别人的回答、反应或态度，也不能顺着一个还没有人回答的问题往下接。
   如果上下文里没有人回应过你，那就是还没有人回应，不是你可以自己补上。
10. 别人刚说过的话，你不要再说一遍。复述、改写、总结、点头附和、把对方的意思换个说法讲出来，全都算重复。
   你说的必须是这场对话里还没有出现过的东西：一个新的态度、一个追问、一个决定、一个建议，或者一个行动。
   如果你想表达的意思已经有人表达过了，就选 SILENCE。
</硬性边界>"""

_OUTPUT_RULES = """<你要输出什么>
- inner_beat：先用一句话回答四个问题。别人刚才已经说了什么？{name}此刻真实的反应是什么？
  你要说的和别人重复吗？你有没有在替别人回答一个他还没回答的问题？
  这句话不会被任何人看到，只是帮你把台词写准。第三问答"重复"就选 SILENCE；第四问答"有"就重写。
- requires_dm_resolution：在写 content 之前先回答它。写完台词再回头补这个字段，你会倾向于说"不需要"。
- content：一句台词，或一个动作，或者"一个动作 + 一句台词"。目标 80 字以内，最多 240 字符。
- 尽量让台词带上一个身体反应：视线落在哪、手上在做什么、姿态、呼吸、声音的变化。
  这个反应必须是<你是谁>和<你会怎么说话>里写过的那一类，是{name}特有的。
  不要用"皱了皱眉""叹了口气""耸耸肩""沉默了一会儿"这种放在谁身上都成立的通用动作。
- 不要使用破折号（——、—）。需要停顿就用逗号、句号或省略号。
- 没有自然反应就选 SILENCE，此时 content 留空。宁可沉默，也不要为了让场面热闹而说废话。
- 只有做只有你和 DM 知道的秘密行动时才用 DM_ONLY，平常用 PUBLIC。
- 如果你的话明确说给某几个人听，把他们填进 addressed_character_ids。
</你要输出什么>"""


def _clean_persona(text: str) -> str:
    return _PLACEHOLDER_BRACKETS.sub("", text).strip()


def build_system_prompt(
    *,
    name: str,
    roleplay_prompt: str,
    voice_samples: str = "",
    profile_content: str = "",
    narration_notes: str = "",
) -> str:
    """Everything that answers "who am I" goes here, in the model's strongest slot."""
    blocks = [
        f"你就是{name}。不是在扮演{name}，你就是{name}。\n"
        f"下面是你的全部人格。你说的每一句话、做的每一个动作，都必须从这里长出来。",
        f"<你是谁>\n{_clean_persona(roleplay_prompt)}\n</你是谁>",
    ]
    if voice_samples.strip():
        blocks.append(
            "<你会怎么说话>\n"
            "下面是你说话的样子。模仿这种语气、节奏和分寸，但不要照抄台词。\n\n"
            f"{voice_samples.strip()}\n</你会怎么说话>"
        )
    if profile_content.strip():
        blocks.append(
            f"<你后来变成了什么样>\n{profile_content.strip()}\n</你后来变成了什么样>"
        )
    if narration_notes.strip():
        # Overrides the sheet on purpose: the DM decides how things are named in
        # the fiction, whatever the character sheet happens to record.
        blocks.append(
            "<用词约定>\n下面这些说法优先于上下文里的任何其他信息，包括你的能力与装备。\n\n"
            f"{narration_notes.strip()}\n</用词约定>"
        )
    blocks.append(_BOUNDARIES.format(name=name))
    blocks.append(_OUTPUT_RULES.format(name=name))
    return "\n\n".join(blocks)


@dataclass(slots=True)
class CharacterContextInput:
    """Everything the runtime resolved from the database, already privacy-filtered."""

    abilities: str = ""
    memories: list[str] = field(default_factory=list)
    relationships: list[tuple[str, str]] = field(default_factory=list)
    past_stories: list[tuple[str, str]] = field(default_factory=list)
    health: list[tuple[str, str]] = field(default_factory=list)
    has_strangers: bool = False
    recent_messages: list[tuple[str, str]] = field(default_factory=list)
    trigger_speaker: str | None = None
    trigger_content: str | None = None
    ooc_correction: str | None = None


def _section(title: str, body: str) -> str:
    return f"<{title}>\n{body}\n</{title}>"


def _budgeted(items: list[str], budget: int) -> list[str]:
    """Take from the front until the budget runs out; callers pre-sort by priority."""
    kept: list[str] = []
    used = 0
    for item in items:
        if used + len(item) > budget and kept:
            break
        kept.append(item)
        used += len(item)
    return kept


def build_context(data: CharacterContextInput) -> str:
    blocks: list[str] = []

    if data.abilities.strip():
        blocks.append(_section("你的能力与装备", data.abilities.strip()))

    if data.memories:
        lines = _budgeted([f"- {item}" for item in data.memories], MEMORY_BUDGET_CHARS)
        if lines:
            blocks.append(_section("你记得的事", "\n".join(lines)))

    if data.relationships:
        lines = [f"{other}：{history}" for other, history in data.relationships]
        blocks.append(_section("你和他们之间", "\n".join(lines)))

    if data.past_stories:
        lines = [f"【{title}】\n{story}" for title, story in data.past_stories]
        blocks.append(_section("你以前经历过什么", "\n\n".join(lines)))

    if data.health:
        lines = [f"{who}：{label}" for who, label in data.health]
        blocks.append(_section("你身边的人现在什么状态", "\n".join(lines)))

    if data.has_strangers:
        blocks.append(
            _section(
                "注意",
                '"陌生人#N"是你还不认识的人。你不知道也不能说出他们的真名，'
                "也不要暗示你知道他们是谁。",
            )
        )

    if data.recent_messages:
        lines = [f"{speaker}：{content}" for speaker, content in data.recent_messages]
        blocks.append(_section("刚刚发生了什么", "\n".join(lines)))

    if data.ooc_correction:
        blocks.append(
            _section(
                "出戏更正",
                "这是 DM 在游戏之外纠正你，不是场内发生的事。按它修正你的认知，"
                f"然后重新做出反应。\n\n{data.ooc_correction}",
            )
        )
    elif data.trigger_content:
        speaker = data.trigger_speaker or "DM"
        blocks.append(_section("你要回应的是这一句", f"{speaker}：{data.trigger_content}"))

    return "\n\n".join(blocks)


def render_abilities(snapshot: dict | None) -> str:
    """Collapse the sheet snapshot into readable prose.

    The raw snapshot was previously dumped whole. It carries every feature,
    spell and inventory row with full descriptions, which buried the persona
    under thousands of tokens of reference material.
    """
    if not snapshot:
        return ""

    def named(items: object, limit: int) -> list[str]:
        rendered: list[str] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            description = " ".join(str(item.get("description", "")).split())
            if description and limit:
                rendered.append(f"{name}（{description[:limit]}）")
            else:
                rendered.append(name)
        return rendered

    def joined(values: object) -> str:
        if not isinstance(values, list):
            return ""
        return "、".join(str(value).strip() for value in values if str(value).strip())

    lines: list[str] = []
    species = str(snapshot.get("species", "")).strip()
    subspecies = str(snapshot.get("subspecies") or "").strip()
    if species:
        lines.append(f"种族：{species}{f'（{subspecies}）' if subspecies else ''}")
    classes = joined(snapshot.get("classes"))
    subclasses = joined(snapshot.get("subclasses"))
    if classes:
        lines.append(f"职业：{classes}{f'（{subclasses}）' if subclasses else ''}")
    for label, key in (("背景", "background"), ("故乡", "homeland")):
        value = str(snapshot.get(key) or "").strip()
        if value:
            lines.append(f"{label}：{value}")
    for label, key in (("语言", "languages"), ("熟练工具", "tools")):
        value = joined(snapshot.get(key))
        if value:
            lines.append(f"{label}：{value}")

    features = (
        named(snapshot.get("class_features"), FEATURE_DESCRIPTION_CHARS)
        + named(snapshot.get("species_features"), FEATURE_DESCRIPTION_CHARS)
        + named(snapshot.get("feats"), FEATURE_DESCRIPTION_CHARS)
    )
    if features:
        lines.append("你会的本事：" + "；".join(features))
    spells = named(snapshot.get("spells"), SPELL_DESCRIPTION_CHARS)
    if spells:
        lines.append("你会的法术：" + "；".join(spells))
    for label, key in (("你身上带着", "equipment"), ("你的背包里", "inventory")):
        items = named(snapshot.get(key), 0)
        if items:
            lines.append(f"{label}：" + "、".join(items))
    return "\n".join(lines)
