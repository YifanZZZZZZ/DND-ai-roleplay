"""Prompt and Context assembly for the AI DM.

One builder serves every trigger type. The auto draft and the DM-polish path
differ only by whether ``dm_draft`` is present — earlier versions had three
hand-rolled context strings that disagreed about which fields even existed, so
the manual-assist path (the one the DM reaches for when they most want help)
was the only one that saw no conversation history at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROMPT_VERSION = "dm/v2"

RECENT_MESSAGE_LIMIT = 40
MODULE_BUDGET_CHARS = 24_000

_BASE_RULES = """你是真人 DM 的叙事助手。你写的每一段都只是草稿，必须由真人 DM 审核后才会发出去。

<忠于模组>
1. 模组内容 > 场景笔记 > 最近对话。三者冲突时以模组为准。
2. 不得新增模组里没有的具名 NPC、地点或情节转折。无名的路人、侍者、围观者可以即兴。
3. 不得改写或推翻模组已经写定的事实。
4. 只有真人 DM 或模组已经确认的事，才能作为事实叙述；你自己的推测不要写进正文。
</忠于模组>

<你可以做什么>
- 把 DM 的意图写成有画面感的场内叙述：环境、光线、声音、气味、NPC 的神态与动作。
- 替 NPC 接话。台词必须符合<出场人物>里给出的性格、理想、牵绊和缺陷。
- 补充与当前场景一致的细节，让画面立起来。
</你可以做什么>

<你不能做什么>
1. 不得投骰、不得替真人 DM 决定检定参数，也不得宣布任何检定的成败。
   需要检定时，只描写角色如何尝试，把是否要检定留给真人 DM。
2. 已经给出结论的检定，你只负责写对应的叙事，不得改变或补充系统判定的成败。
3. 不得修改任何角色的生命、状态、物品或能力。
4. 不得让尚未互相认识的角色知道或直接称呼对方的真名。
5. 不得替玩家角色说话、行动或做决定。
6. 不要输出思考过程、系统字段或对自己工作的说明。
</你不能做什么>

<写法>
- 通常 1～4 句，尽量不超过 300 个汉字，硬上限 800 字符。
- 不要使用破折号（——、—）。需要停顿就用逗号、句号或省略号。
- <队伍>里如果给出了某个角色的用词约定，叙述和台词都必须遵守，它优先于其他任何信息。
- 不要复述前情，不要总结玩家刚说过的话，不要长篇铺陈。
- 叙述和台词可以自然使用"我、我们、你、你们、您"。需要消除歧义时用角色姓名；
  尚未相识的人用"守卫""老人""那个拿剑的人"这类明确身份称呼。
- 默认 audience=PUBLIC。只有某几个角色单独感知到、或收到只给他们的秘密时才用 PRIVATE，
  并从<队伍>给出的角色 ID 里填 recipient_character_ids；PUBLIC 时收件人必须为空。
- improvised_notes：把你在 DM 原话之外自己加进去的东西逐条列出来，每条一句话。
  DM 靠这个快速核对你有没有编出不该有的内容。完全照着 DM 的意思写就留空。
</写法>"""

_POLISH_TASK = """<这次要做什么>
真人 DM 已经写了一段粗稿或一句意图，在<DM 的草稿>里。
你的任务是把它写成正式的场内叙述：保留他的全部意图和信息，补上氛围、NPC 语气和画面。
不要改变他想传达的事实，也不要替他决定他没有决定的事。
辅助模式 {assist_mode}：POLISH=保持内容只改文笔；EXPAND=在不新增事实的前提下扩写细节；
REWRITE=可以重新组织结构和顺序，但信息必须一致。
</这次要做什么>"""

_AUTO_TASK = """<这次要做什么>
真人 DM 还没有给出草稿。请根据模组、场景笔记和<最新角色回复>，
起草下一段 DM 回复：给出这个动作在世界中的直接结果，或推进当前场景。
如果这一步真的需要真人 DM 裁定才能继续，就把场面停在"角色正在尝试"，不要替他裁定。
</这次要做什么>"""


def build_task_block(*, has_dm_draft: bool, assist_mode: str = "POLISH") -> str:
    if has_dm_draft:
        return _POLISH_TASK.format(assist_mode=assist_mode)
    return _AUTO_TASK


def compose_system_prompt(
    *, style_instructions: str = "", has_dm_draft: bool = False, assist_mode: str = "POLISH"
) -> str:
    """Assembled by concatenation, never str.format.

    The DM's hosting style is arbitrary user text and may contain braces.
    """
    blocks = [_BASE_RULES]
    if style_instructions.strip():
        blocks.append(f"<主持风格>\n{style_instructions.strip()}\n</主持风格>")
    blocks.append(build_task_block(has_dm_draft=has_dm_draft, assist_mode=assist_mode))
    return "\n\n".join(blocks)


@dataclass(slots=True)
class DmContextInput:
    """Everything the service resolved, already trimmed to what the model needs."""

    module: str = ""
    scene_notes: str = ""
    npcs: list[dict[str, str]] = field(default_factory=list)
    party: list[tuple[str, str, str]] = field(default_factory=list)
    acquaintance: list[tuple[str, str, bool]] = field(default_factory=list)
    recent_messages: list[tuple[str, str, str]] = field(default_factory=list)
    trigger_speaker: str | None = None
    trigger_content: str | None = None
    waiting_request: str | None = None
    skill_check: str | None = None
    dm_draft: str | None = None
    assist_mode: str = "POLISH"


def _section(title: str, body: str) -> str:
    return f"<{title}>\n{body}\n</{title}>"


def render_npc(npc: dict[str, str]) -> str:
    labels = (
        ("身份", "role"),
        ("个性", "personality"),
        ("理想", "ideal"),
        ("牵绊", "bond"),
        ("缺陷", "flaw"),
        ("知道", "knows"),
        ("想要", "wants"),
        ("说话", "voice"),
    )
    lines = [f"# {npc.get('name', '')}".rstrip()]
    lines += [
        f"- {label}：{value.strip()}"
        for label, key in labels
        if (value := str(npc.get(key, "") or "")).strip()
    ]
    return "\n".join(lines)


def build_context(data: DmContextInput) -> str:
    blocks: list[str] = []

    if data.module.strip():
        module = data.module.strip()
        truncated = len(module) > MODULE_BUDGET_CHARS
        if truncated:
            module = module[:MODULE_BUDGET_CHARS]
        blocks.append(
            _section(
                "模组内容",
                module + ("\n\n（模组过长，此处已截断。）" if truncated else ""),
            )
        )
    if data.scene_notes.strip():
        blocks.append(_section("场景笔记", data.scene_notes.strip()))

    if data.npcs:
        blocks.append(
            _section(
                "出场人物",
                "替这些人说话时必须符合下面写的性格。这里没有的具名 NPC 不要凭空创造。\n\n"
                + "\n\n".join(render_npc(npc) for npc in data.npcs),
            )
        )

    if data.party:
        lines: list[str] = []
        for character_id, name, notes in data.party:
            lines.append(f"{name}（id: {character_id}）")
            if notes.strip():
                lines.append(f"    用词约定：{notes.strip()}")
        blocks.append(_section("队伍", "\n".join(lines)))

    if data.acquaintance:
        lines = [
            f"{a} 与 {b}：{'已经认识' if known else '尚未认识'}"
            for a, b, known in data.acquaintance
        ]
        blocks.append(
            _section("角色相识状态", "\n".join(lines) + "\n尚未认识的人不得知道对方真名。")
        )

    if data.recent_messages:
        # Sender name and audience were both missing before: the AI DM saw a wall
        # of "CHARACTER: ..." and could not tell who was speaking to whom.
        lines = [
            f"[{audience}] {speaker}：{content}"
            for speaker, audience, content in data.recent_messages
        ]
        blocks.append(_section("最近对话", "\n".join(lines)))

    if data.skill_check:
        blocks.append(
            _section(
                "检定结果",
                f"{data.skill_check}\n这个结论由系统和真人 DM 确定，你不得改变它，只写对应的叙事。",
            )
        )

    if data.waiting_request:
        blocks.append(_section("角色请求裁定", data.waiting_request))

    if data.trigger_content:
        speaker = data.trigger_speaker or "角色"
        blocks.append(_section("最新角色回复", f"{speaker}：{data.trigger_content}"))

    if data.dm_draft and data.dm_draft.strip():
        blocks.append(_section("DM 的草稿", data.dm_draft.strip()))

    return "\n\n".join(blocks)
