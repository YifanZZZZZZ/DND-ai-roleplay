from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageValidation:
    approved: bool
    reason: str | None = None


class MessageValidator:
    """Deterministic safety gate for every character message before persistence."""

    _mechanical_patterns = (
        re.compile(r"\d"),
        re.compile(r"\b(?:d[24681020]|dc|ac|hp|str|dex|con|int|wis|cha)\b", re.I),
        re.compile(r"(?:技能|属性|能力值|豁免|检定|加值|骰子|投骰|难度等级|伤害骰)"),
    )
    _result_claim_patterns = (
        re.compile(r"(?:我|他|她|它|我们|目标).{0,8}(?:成功|失败|命中|击中|躲开|被击倒)"),
        re.compile(r"(?:造成|受到)\s*\d+\s*(?:点)?(?:伤害|生命)"),
    )

    def validate(self, content: str) -> MessageValidation:
        text = content.strip()
        if not text:
            return MessageValidation(False, "角色消息不能为空。")
        if "\n\n" in text:
            return MessageValidation(False, "一次角色响应只能生成一个消息气泡。")
        for pattern in (*self._mechanical_patterns, *self._result_claim_patterns):
            if pattern.search(text):
                return MessageValidation(False, "消息包含机械数值或未经 DM 裁定的结果。")
        return MessageValidation(True)
