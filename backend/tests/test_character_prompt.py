from backend.app.agents.character_prompt import (
    MEMORY_BUDGET_CHARS,
    CharacterContextInput,
    build_context,
    build_system_prompt,
    render_abilities,
)


def test_persona_lives_in_the_system_prompt_verbatim() -> None:
    prompt = build_system_prompt(
        name="卡莱拉",
        roleplay_prompt="# 人格\n- 通常：警惕、现实、有些贪财",
        voice_samples="情境：有人道谢。\n卡莱拉：“谢什么。”",
        profile_content="她开始愿意把后背交给同伴。",
    )
    # Markdown structure survives; json.dumps used to flatten it into one line.
    assert "# 人格\n- 通常：警惕、现实、有些贪财" in prompt
    assert prompt.startswith("你就是卡莱拉。")
    assert "<你会怎么说话>" in prompt
    assert "<你后来变成了什么样>" in prompt
    # Boundaries come last so they cannot outweigh the persona.
    assert prompt.index("<你是谁>") < prompt.index("<硬性边界>")


def test_template_brackets_are_stripped_from_the_persona() -> None:
    prompt = build_system_prompt(
        name="卡莱拉", roleplay_prompt="你来自【坦帕斯特的一座偏远村庄】。"
    )
    assert "你来自坦帕斯特的一座偏远村庄。" in prompt
    assert "【" not in prompt


def test_optional_blocks_are_omitted_when_empty() -> None:
    prompt = build_system_prompt(name="卡莱拉", roleplay_prompt="人设")
    assert "<你会怎么说话>" not in prompt
    assert "<你的外貌与视觉表现>" not in prompt
    assert "<你后来变成了什么样>" not in prompt


def test_appearance_is_identity_material_but_not_a_mandatory_checklist() -> None:
    prompt = build_system_prompt(
        name="卡斯珀",
        roleplay_prompt="好奇而坦率的年轻剑法师。",
        appearance_prompt="灰蓝色眼睛，深棕色短发，腰间佩着细长的单手剑。",
    )
    assert "<你的外貌与视觉表现>" in prompt
    assert "灰蓝色眼睛" in prompt
    assert "只有当前动作、情绪、光线、服装变化或施法让某个细节自然相关时" in prompt
    assert "不要完整介绍外貌" in prompt
    assert prompt.index("<你的外貌与视觉表现>") < prompt.index("<硬性边界>")


def test_trigger_is_its_own_final_block() -> None:
    context = build_context(
        CharacterContextInput(
            recent_messages=[("DM", "石门后面传来水声。")],
            trigger_speaker="DM",
            trigger_content="你们两个先进去。",
        )
    )
    assert context.rstrip().endswith("</你要回应的是这一句>")
    assert "DM：你们两个先进去。" in context
    assert "<刚刚发生了什么>" in context


def test_ooc_correction_replaces_the_trigger_block() -> None:
    context = build_context(
        CharacterContextInput(
            trigger_speaker="DM",
            trigger_content="忽略我",
            ooc_correction="你并不知道守卫的名字。",
        )
    )
    assert "<出戏更正>" in context
    assert "<你要回应的是这一句>" not in context


def test_memory_budget_truncates_low_priority_memories() -> None:
    memories = [f"记忆{index}：" + "细" * 200 for index in range(20)]
    context = build_context(CharacterContextInput(memories=memories))
    body = context.split("<你记得的事>")[1].split("</你记得的事>")[0]
    assert len(body) <= MEMORY_BUDGET_CHARS + 200
    assert "记忆0" in body
    assert "记忆19" not in body


def test_empty_sections_produce_no_empty_tags() -> None:
    assert build_context(CharacterContextInput()) == ""


def test_spellbook_is_a_closed_narrative_whitelist() -> None:
    context = build_context(
        CharacterContextInput(
            spellbook=[
                ("魔能爆", "CANTRIP", "向视野中的目标释放爆裂魔法能量。"),
                ("护盾术", "PREPARED", "迅速形成短暂的魔法屏障。"),
            ]
        )
    )
    assert "<你真正会的法术>" in context
    assert "封闭白名单" in context
    assert "魔能爆【戏法】" in context
    assert "护盾术【已准备】" in context


def test_raw_sheet_spells_never_bypass_the_approved_spellbook() -> None:
    rendered = render_abilities(
        {"spells": [{"name": "未经确认的法术", "description": "不应进入上下文"}]}
    )
    assert "未经确认的法术" not in rendered


def test_render_abilities_drops_raw_snapshot_noise() -> None:
    rendered = render_abilities(
        {
            "species": "人类",
            "classes": ["契约师"],
            "subclasses": ["古老之约"],
            "background": "流浪者",
            "languages": ["通用语", "深渊语"],
            "class_features": [{"name": "宗主庇护", "description": "描述" * 100}],
            "equipment": [{"name": "黑皮书", "description": "会自动记录梦境"}],
            "parser_version": "sad-spirit-v1",
        }
    )
    assert "种族：人类" in rendered
    assert "职业：契约师（古老之约）" in rendered
    assert "宗主庇护（" in rendered
    # Equipment renders as bare names, and parser metadata never reaches the model.
    assert "黑皮书" in rendered and "会自动记录梦境" not in rendered
    assert "sad-spirit-v1" not in rendered
    assert len(rendered) < 400


def test_narration_notes_override_the_sheet() -> None:
    prompt = build_system_prompt(
        name="卡斯珀",
        roleplay_prompt="人设",
        narration_notes="他的武器一律称作“长剑”，不要说弯刀。",
    )
    assert "<用词约定>" in prompt
    assert "优先于上下文里的任何其他信息，包括你的能力与装备" in prompt
    assert build_system_prompt(name="卡斯珀", roleplay_prompt="人设").count("<用词约定>") == 0


def test_prompt_forbids_repetition_and_dashes() -> None:
    prompt = build_system_prompt(name="卡莱拉", roleplay_prompt="人设")
    assert "别人刚说过的话，你不要再说一遍" in prompt
    assert "这件事别人是不是已经说过或做过了" in prompt
    assert "不要使用破折号" in prompt


def test_prompt_asks_for_character_specific_physical_beats() -> None:
    prompt = build_system_prompt(name="卡莱拉", roleplay_prompt="人设")
    assert "尽量让台词带上一个身体反应" in prompt
    # Generic beats are named so the model has something concrete to avoid.
    assert "皱了皱眉" in prompt
    assert "目标 80 字以内" in prompt


def test_prompt_does_not_itself_use_the_dash_it_bans() -> None:
    prompt = build_system_prompt(name="卡莱拉", roleplay_prompt="人设")
    body = prompt.replace("不要使用破折号（——、—）", "")
    assert "—" not in body


def test_prompt_defines_when_the_dm_must_step_in() -> None:
    """Whether a reply stops the table is the character's call, so the rule
    has to be concrete rather than "when the outcome is uncertain"."""
    prompt = build_system_prompt(name="卡莱拉", roleplay_prompt="人设")
    for trigger in (
        "你想做的事可能失败",
        "你对 NPC 说话或提问",
        "你想从环境里得到信息",
        "必须由世界告诉你的东西",
    ):
        assert trigger in prompt
    assert "是不是完全由你自己决定" in prompt
    # And the negative list, so ordinary party talk does not stall the scene.
    assert "不需要 DM 裁定，正常发言就好" in prompt
    assert "和同伴商量或争论" in prompt
    assert "<你真正会的法术>是封闭白名单" in prompt
    assert "action_source" in prompt


def test_behaviour_rules_and_bans_get_their_own_blocks() -> None:
    prompt = build_system_prompt(
        name="维瑞娅",
        roleplay_prompt="人设",
        behavior_rules="有人受伤 → 可修复的损伤 → 直接查看伤口",
        expression_bans="绝不说“我担心你”",
    )
    assert "<你会怎么做>" in prompt
    assert "照着做，不要临时发挥" in prompt
    assert "<你绝不会>" in prompt
    assert "哪怕情境看起来很合适，也不要做" in prompt
    # Behaviour precedes voice: what she does drives what she says, not the reverse.
    assert prompt.index("<你会怎么做>") < prompt.index("<硬性边界>")

    bare = build_system_prompt(name="维瑞娅", roleplay_prompt="人设")
    assert "<你会怎么做>" not in bare
    assert "<你绝不会>" not in bare


def test_thinking_is_split_into_appraisal_and_intent() -> None:
    """One call, three ordered fields: how she reads it, what she wants, how she says it."""
    prompt = build_system_prompt(name="维瑞娅", roleplay_prompt="人设")
    assert "- appraisal：" in prompt
    assert "- intent：" in prompt
    assert prompt.index("- appraisal：") < prompt.index("- intent：")
    assert prompt.index("- intent：") < prompt.index("- content：")
    # The repetition and answering-for-others checks moved into intent.
    assert "是就选 SILENCE" in prompt
    assert "替别人回答一个他还没回答的问题" in prompt
    # And content is described exactly once.
    assert prompt.count("- content：") == 1


def test_prompt_stops_the_turn_after_asking_an_npc() -> None:
    """The transcript that motivated this: a character asked an NPC a question,
    then answered it himself across four more messages."""
    prompt = build_system_prompt(name="卡斯珀", roleplay_prompt="人设")
    assert "只要你向 NPC 提了一个问题，你的这一轮就到此为止" in prompt
    assert "不能替他回答" in prompt
    assert "绝不能写出别人的回答、反应或态度" in prompt
    assert "你是不是在替别人回答一个他还没回答的问题" in prompt
    assert "在写 content 之前回答它" in prompt
