from backend.app.agents.dm_prompt import (
    DmContextInput,
    build_context,
    compose_system_prompt,
    render_npc,
)


def test_recent_messages_carry_speaker_and_audience() -> None:
    """The AI DM used to see a wall of "CHARACTER: ..." with no names."""
    context = build_context(
        DmContextInput(
            recent_messages=[
                ("DM", "公开", "石门后面传来水声。"),
                ("卡莱拉", "私密→赛蕾妮", "别出声。"),
            ]
        )
    )
    assert "[公开] DM：石门后面传来水声。" in context
    assert "[私密→赛蕾妮] 卡莱拉：别出声。" in context


def test_dm_draft_block_only_appears_on_the_polish_path() -> None:
    auto = build_context(DmContextInput(trigger_speaker="卡莱拉", trigger_content="我推门。"))
    assert "<DM 的草稿>" not in auto

    polish = build_context(
        DmContextInput(
            trigger_speaker="卡莱拉",
            trigger_content="我推门。",
            dm_draft="守卫拦住他们，态度不好",
        )
    )
    assert "<DM 的草稿>\n守卫拦住他们，态度不好\n</DM 的草稿>" in polish


def test_system_prompt_switches_task_by_path() -> None:
    auto = compose_system_prompt()
    polish = compose_system_prompt(has_dm_draft=True, assist_mode="EXPAND")
    assert "真人 DM 还没有给出草稿" in auto
    assert "真人 DM 已经写了一段粗稿" in polish
    assert "辅助模式 EXPAND" in polish
    # The module-fidelity rules are shared by both paths.
    for prompt in (auto, polish):
        assert "模组内容 > 场景笔记 > 最近对话" in prompt
        assert "不得新增模组里没有的具名 NPC" in prompt


def test_style_instructions_with_braces_do_not_break_formatting() -> None:
    prompt = compose_system_prompt(style_instructions="多用短句 {like this} 不要长段")
    assert "{like this}" in prompt


def test_render_npc_omits_blank_fields() -> None:
    rendered = render_npc(
        {"name": "卢卡斯·格罗斯文诺", "role": "无聊鼬鼠酒馆老板", "flaw": "", "wants": "请人献花"}
    )
    assert rendered.startswith("# 卢卡斯·格罗斯文诺")
    assert "- 身份：无聊鼬鼠酒馆老板" in rendered
    assert "- 想要：请人献花" in rendered
    assert "缺陷" not in rendered


def test_empty_context_is_empty() -> None:
    assert build_context(DmContextInput()) == ""
