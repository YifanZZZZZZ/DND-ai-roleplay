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
