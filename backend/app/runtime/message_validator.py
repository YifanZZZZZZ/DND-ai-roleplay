from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageValidation:
    approved: bool
    reason: str | None = None


class MessageValidator:
    """Deterministic safety gate for every character message before persistence.

    Earlier versions rejected any digit at all, so ordinary lines like
    "我数到三" or "第 2 次了" were treated as rule leakage. Numbers are now only
    suspicious next to a rules term; bare counting is left alone.
    """

    _mechanical_patterns = (
        re.compile(r"\d+\s*点?\s*(?:伤害|生命|治疗|法力)"),
        # \b is useless here: Python treats CJK as word characters, so "难度DC15"
        # and "个d20" have no boundary before the latin run. Use a latin lookbehind.
        re.compile(r"(?<![a-zA-Z])(?:DC|AC|HP|MP)\s*[:：]?\s*\d+", re.I),
        re.compile(r"(?<![a-zA-Z])(?:str|dex|con|int|wis|cha)\s*[:：]?\s*[+-]?\d+", re.I),
        re.compile(r"(?<![a-zA-Z])d\s?(?:4|6|8|10|12|20|100)(?!\d)", re.I),
        re.compile(r"[+-]\s*\d+\s*(?:加值|修正)"),
        re.compile(r"(?:豁免|检定|加值|骰子|投骰|难度等级|伤害骰|先攻|命中骰)"),
    )
    _result_claim_patterns = (
        re.compile(
            r"(?:^|[。！？])(?!(?:[^。！？])*(?:尝试|试图))"
            r"[^。！？]{1,24}(?:成功|失败|命中|击中|躲开|被击倒)"
        ),
        re.compile(r"(?:造成|受到)\s*\d+\s*(?:点)?(?:伤害|生命)"),
    )

    _dash_pattern = re.compile(r"[—–]|--")
    _explicit_cast_pattern = re.compile(
        r"(?:施展|施放|释放|发动|吟唱)(?:名为)?[《“\"]?([\u4e00-\u9fff]{1,12}(?:术|咒|法术))"
    )

    def validate_spell_choice(
        self,
        action_source: str,
        source_name: str | None,
        allowed_spell_names: tuple[str, ...],
        content: str = "",
    ) -> MessageValidation:
        explicit_cast = self._explicit_cast_pattern.search(content)
        if action_source != "SPELL" and explicit_cast is not None:
            return MessageValidation(False, "正文明确描述了施法，但没有声明 SPELL 和准确法术名。")
        if action_source != "SPELL":
            return MessageValidation(True)
        selected = (source_name or "").strip()
        if selected not in allowed_spell_names:
            available = "、".join(allowed_spell_names) or "无"
            return MessageValidation(
                False,
                f"角色声明了未掌握的法术“{selected or '未填写'}”；当前法术白名单：{available}。",
            )
        if explicit_cast is not None and explicit_cast.group(1) != selected:
            return MessageValidation(
                False,
                f"正文施展的是“{explicit_cast.group(1)}”，但结构化声明是“{selected}”。",
            )
        return MessageValidation(True)

    def validate(self, content: str) -> MessageValidation:
        text = content.strip()
        if not text:
            return MessageValidation(False, "角色消息不能为空。")
        if "\n\n" in text:
            return MessageValidation(False, "一次角色响应只能生成一个消息气泡。")
        if self._dash_pattern.search(text):
            return MessageValidation(False, "消息使用了破折号，请改用逗号、句号或省略号。")
        for pattern in self._mechanical_patterns:
            if pattern.search(text):
                return MessageValidation(False, "消息包含机械数值或规则术语。")
        for pattern in self._result_claim_patterns:
            if pattern.search(text):
                return MessageValidation(False, "消息宣告了未经 DM 裁定的行动结果。")
        return MessageValidation(True)
