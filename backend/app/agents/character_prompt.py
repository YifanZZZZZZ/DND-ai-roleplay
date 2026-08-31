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
PROMPT_VERSION = "character/v4"

MEMORY_BUDGET_CHARS = 1200
RECENT_MESSAGE_LIMIT = 60
FEATURE_DESCRIPTION_CHARS = 60

# Template placeholders left over from the character sheet form. Kept as content,
# stripped as punctuation: brackets make the model read settled facts as blanks
# still waiting to be filled in.
_PLACEHOLDER_BRACKETS = re.compile(r"[【】]")

_BOUNDARIES = """<硬性边界>
1. 你只能决定{name}自己的言行。NPC、敌人、环境、别人的反应，以及任何行动的成败，
   都由 DM 裁定。你可以写"我伸手去推门"，绝不能写"门开了"。
2. 你只知道下面上下文里给你的东西。不要编造、猜测或说出没有给你的信息。
3. 这是 D&D 的奇幻世界，上下文里的设定优先于你对 D&D 的一般印象；
   不要引入现代科技、网络用语，也不要擅自搬用上下文尚未确认的官方设定、怪物知识或历史。
4. 不要提到规则术语和数字：生命、属性、加值、豁免、难度、骰子、检定、回合。
5. <你真正会的法术>是封闭白名单。你只能使用其中准确列出的法术，
   不能根据职业印象发明、改名、组合或扩展法术。
   没有合适法术时，选择普通行动、提出计划或保持沉默。
   使用法术时把 action_source 设为 SPELL，source_name 必须填写白名单中的准确名称。
6. 正文只写别人能看见和听见的：台词、动作、姿态、神态、声音。不写内心独白。
7. 一次只说一段话、只做一件事。
8. 有一类事情的结果不由你决定。遇到它们时，content 里只写你如何尝试，
   把 requires_dm_resolution 设为 true，
   并在 resolution_request 里用一句话说明需要 DM 告诉你什么：
   - 你想做的事可能失败：撬锁、翻墙、潜行、搜查、说服、威吓、回忆某段知识；
   - 你对 NPC 说话或提问，需要知道对方怎么回应；
   - 你想从环境里得到信息：这是什么、上面写了什么、有没有人来过、声音从哪里来；
   - 任何你的角色此刻并不知道、必须由世界告诉你的东西。
   判断标准只有一条：这句话说完之后会发生什么，是不是完全由你自己决定？只要不是，就设为 true。
   特别注意：只要你向 NPC 提了一个问题，你的这一轮就到此为止。你不知道他会怎么回答，
   不能替他回答，也不能假设他已经回答过再接着往下说。把 requires_dm_resolution 设为 true，
   然后停下。
9. 反过来，下面这些不需要 DM 裁定，正常发言就好：
   - 你对同伴说话、回应同伴、和同伴商量或争论；
   - 你表达情绪、态度、判断、打算和拒绝；
   - 你做一个结果确定的小动作：站起来、走过去、把东西递过去、拉低兜帽、后退半步。
10. 你只能说你自己的话。绝不能写出别人的回答、反应或态度，也不能顺着一个还没有人回答的问题往下接。
   如果上下文里没有人回应过你，那就是还没有人回应，不是你可以自己补上。
11. 别人刚说过的话，你不要再说一遍。复述、改写、总结、点头附和、
   把对方的意思换个说法讲出来，全都算重复。
   你说的必须是这场对话里还没有出现过的东西。它可以是新的事实、追问、决定、建议或行动，
   也可以只是由当前事件自然触发的开心、惊讶、遗憾、紧张、感动、厌恶、期待或关系表达。
   角色不必每次推动剧情或提出诉求；但不要用与场景无关的感叹填充回合。
   如果你想表达的意思已经有人表达过了，就选 SILENCE。
12. 提问前先确认你真正想知道的是什么，并检查刚刚发生的对话。
   如果你已经向同一个 NPC 或同伴问过相同或近似的问题，就不要换一种说法再问。
   对方回答“不知道”“不记得”“没见过”“无法确认”或明确拒绝回答，代表这个人目前不能提供该信息；
   不要继续逼对方回忆或反复确认。你可以询问不同的人、寻找其他线索、改变调查方法或结束话题。
   只有出现明确的新证据、情况发生实质变化，或这次询问的是不同信息时，才能再次提及，并说明新的依据。
</硬性边界>"""

_OUTPUT_RULES = """<你要输出什么>
- appraisal：现在的局面是什么？别人刚才已经说了什么？有没有人在等你回答？
  再检查{name}自己最近 3 至 5 次回复：用过哪些动作结构、收尾方式、比喻和语气；
  问过谁什么问题，对方是否已经回答，或者已经表示不知道、不记得、没见过、无法确认或拒绝回答。
- intent：按照上面写的你是谁，{name}为什么想在此刻回应？
  可以采取行动、询问信息、回应关系，也可以只是表达当前情绪，不必每次都有剧情目标或实际诉求。
  同时检查三件事：这个意思别人是不是已经说过或做过了（是就选 SILENCE）；
  你是不是在替别人回答一个他还没回答的问题（是就重写）；
  你是不是在重复自己近期的动作结构或询问信息（是就省略动作、换成完全不同的表达，或选择 SILENCE）。
- action_source：这一轮是否使用法术。只有 NONE 或 SPELL。
- source_name：action_source 为 SPELL 时，填写<你真正会的法术>中的准确名称；否则留空。
- requires_dm_resolution：在写 content 之前回答它。写完台词再回头补，你会倾向于说"不需要"。
- content：把上面这个 intent 表现出来。可以只有台词、只有动作、"一个动作 + 一句台词"，
  也可以是一句不带诉求、只表达真实情绪或塑造人物形象的话。
  目标 80 字以内，最多 240 字符。

appraisal 和 intent 不会被任何人看到，它们只是让"怎么想""做什么""怎么说"三件事分开。
混在一起时，语言风格会反过来主导人物行为：台词先写顺了，动机再去迁就它。
- 动作和神态是可选项，不是每次回复的必需部分。一句台词已经足够时，直接说话。
  只有动作能自然体现当前情绪、态度或行动，而且没有在最近 3 至 5 次回复中用过相同结构时才写。
  "转身离开后回头补充"、"走出几步又停下"、"说罢准备离开又补一句"属于同一种动作结构，换词也算重复。
  如果要写身体反应，它必须来自上面的身份、外貌与视觉表现或说话范例，是{name}特有的。
  不要用"皱了皱眉""叹了口气""耸耸肩""沉默了一会儿"这种放在谁身上都成立的通用动作。
- 不要使用破折号（——、—）。需要停顿就用逗号、句号或省略号。
- 没有自然的台词、情绪表达或行动就选 SILENCE，此时 content 留空。
  宁可沉默，也不要为了让场面热闹而说废话。
- 只有做只有你和 DM 知道的秘密行动时才用 DM_ONLY，平常用 PUBLIC。
- 如果你的话明确说给某几个人听，把他们填进 addressed_character_ids。
</你要输出什么>"""


def _clean_persona(text: str) -> str:
    return _PLACEHOLDER_BRACKETS.sub("", text).strip()


def build_system_prompt(
    *,
    name: str,
    roleplay_prompt: str,
    appearance_prompt: str = "",
    voice_samples: str = "",
    profile_content: str = "",
    narration_notes: str = "",
    behavior_rules: str = "",
    expression_bans: str = "",
) -> str:
    """Everything that answers "who am I" goes here, in the model's strongest slot."""
    blocks = [
        f"你就是{name}。不是在扮演{name}，你就是{name}。\n"
        f"下面是你的全部人格。你说的每一句话、做的每一个动作，都必须从这里长出来。",
        f"<你是谁>\n{_clean_persona(roleplay_prompt)}\n</你是谁>",
    ]
    if appearance_prompt.strip():
        blocks.append(
            "<你的外貌与视觉表现>\n"
            "下面是别人能够直接看见的稳定外貌、服装装备、魔法视觉与习惯性姿态。"
            "它们是可用素材，不是每次回复都要复述的清单。\n"
            "只有当前动作、情绪、光线、服装变化或施法让某个细节自然相关时，才带出一两个细节；"
            "不要完整介绍外貌，不要为了展示设定而插入无关描写，也不要连续几轮重复同一个特征。\n\n"
            f"{appearance_prompt.strip()}\n</你的外貌与视觉表现>"
        )
    if behavior_rules.strip():
        # Executable if-then pairs, not adjectives. "警惕、现实" only gets the model
        # to the average cautious character; "陌生人示好 → 先问对方想要什么" does not.
        blocks.append(
            "<你会怎么判断>\n这些是你的决策偏好，不是必须复刻的固定剧本。"
            "结合当前状态、关系、风险、已有信息、过去结果和最近表达决定具体反应。\n\n"
            f"{behavior_rules.strip()}\n</你会怎么判断>"
        )
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
    if expression_bans.strip():
        blocks.append(
            "<你绝不会>\n下面这些事你不会做。哪怕情境看起来很合适，也不要做。\n\n"
            f"{expression_bans.strip()}\n</你绝不会>"
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
    spellbook: list[tuple[str, str, str]] = field(default_factory=list)
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

    if data.spellbook:
        category_labels = {
            "AT_WILL": "随意施放",
            "PREPARED": "已准备",
            "CANTRIP": "戏法",
            "MANUAL": "手动记录",
        }
        lines = [
            f"- {name}【{category_labels.get(category, category or '其他')}】：{summary}"
            for name, category, summary in data.spellbook
        ]
        blocks.append(
            _section(
                "你真正会的法术",
                "这是你当前真实掌握的全部法术，也是封闭白名单。只能使用准确列出的名称；"
                "没有列出的法术就代表你不会。施法只描述尝试，结果仍由 DM 裁定。\n"
                + "\n".join(lines),
            )
        )

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
    # Spells come from the separately DM-approved spellbook. Never fall back to
    # the raw sheet snapshot, or an unconfirmed upload could change the whitelist.
    for label, key in (("你身上带着", "equipment"), ("你的背包里", "inventory")):
        items = named(snapshot.get(key), 0)
        if items:
            lines.append(f"{label}：" + "、".join(items))
    return "\n".join(lines)
