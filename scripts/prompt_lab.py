"""Run one character through a fixed scenario set under two prompt variants.

The point is to make prompt changes checkable without opening a campaign:
edit the character's files under docs/, re-run, read the diff.

    .venv/bin/python scripts/prompt_lab.py 维瑞娅

The scenario set doubles as a regression suite. After any prompt or persona
change, re-run and compare against the previous output file: a change meant
for one character often moves another.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from backend.app.agents.character_agent import (  # noqa: E402
    CharacterDecision,
    DeepSeekCharacterAgent,
)
from backend.app.agents.character_prompt import (  # noqa: E402
    CharacterContextInput,
    build_context,
    build_system_prompt,
)
from backend.app.core.config import Settings  # noqa: E402

DOCS = REPO / "docs"
CALIB = DOCS / "calibration"


@dataclass(slots=True)
class CharacterFiles:
    name: str
    roleplay_prompt: str
    voice_samples: str
    behavior_rules: str
    expression_bans: str

    @classmethod
    def load(cls, name: str) -> CharacterFiles:
        def read(path: Path) -> str:
            return path.read_text(encoding="utf-8").strip() if path.exists() else ""

        persona = read(DOCS / f"{name}_roleplay_prompt.md")
        if not persona:
            raise SystemExit(f"找不到 docs/{name}_roleplay_prompt.md")
        return cls(
            name=name,
            roleplay_prompt=persona,
            voice_samples=read(DOCS / "voice_samples" / f"{name}.md"),
            behavior_rules=read(CALIB / f"{name}_behavior_rules.md"),
            expression_bans=read(CALIB / f"{name}_expression_bans.md"),
        )


VARIANTS = {
    # Everything the character had before this round of calibration.
    "base": lambda f: build_system_prompt(
        name=f.name, roleplay_prompt=f.roleplay_prompt, voice_samples=f.voice_samples
    ),
    # Same, plus the two new per-character blocks.
    "tuned": lambda f: build_system_prompt(
        name=f.name,
        roleplay_prompt=f.roleplay_prompt,
        voice_samples=f.voice_samples,
        behavior_rules=f.behavior_rules,
        expression_bans=f.expression_bans,
    ),
}


def scenario_context(scenario: dict, character: str, party: list[str]) -> str:
    speaker, line = scenario["trigger"]
    return build_context(
        CharacterContextInput(
            health=[("你自己", "健康")]
            + [(name, "健康") for name in party if name != character],
            recent_messages=[tuple(item) for item in scenario.get("recent", [])],
            trigger_speaker=speaker,
            trigger_content=line,
        )
    )


def render(decision: CharacterDecision) -> str:
    if decision.decision == "SILENCE":
        body = "_（沉默）_"
    else:
        body = decision.content
    lines = [body]
    meta = []
    if decision.requires_dm_resolution:
        meta.append(f"⏸ 等待 DM：{decision.resolution_request or ''}")
    if decision.appraisal:
        meta.append(f"局面：{decision.appraisal}")
    if decision.intent:
        meta.append(f"意图：{decision.intent}")
    if meta:
        lines.append("")
        lines += [f"<sub>{item}</sub>" for item in meta]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("character")
    parser.add_argument("--samples", type=int, default=2, help="每个变体每个场景采样几次")
    parser.add_argument(
        "--party",
        default="卡莱拉,赛蕾妮,卡斯珀",
        help="同场的其他角色，只用于健康状态与姓名识别",
    )
    args = parser.parse_args()

    files = CharacterFiles.load(args.character)
    if not files.behavior_rules and not files.expression_bans:
        raise SystemExit(
            f"{args.character} 还没有 behavior_rules / expression_bans，两个变体会完全一样。"
        )

    scenarios = json.loads((CALIB / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    party = [name.strip() for name in args.party.split(",") if name.strip()]

    settings = Settings(_env_file=REPO / ".env")  # 从任何目录运行都能读到
    if not settings.character_agent_is_configured:
        raise SystemExit("角色 Agent 未配置，检查 .env 里的 AI_TRPG_DEEPSEEK_API_KEY。")
    agent = DeepSeekCharacterAgent(settings)

    prompts = {key: build(files) for key, build in VARIANTS.items()}
    out: list[str] = [
        f"# {args.character} · prompt A/B",
        "",
        f"模型 `{settings.character_model}` ｜ 每格 {args.samples} 次采样 ｜ "
        f"base {len(prompts['base'])} 字符，tuned {len(prompts['tuned'])} 字符",
        "",
        "base = 人设 + 说话范例。tuned = 再加上 behavior_rules 与 expression_bans。",
        "上下文两边完全相同。",
        "",
    ]

    for scenario in scenarios:
        context = scenario_context(scenario, args.character, party)
        print(f"[{scenario['id']}] {scenario['name']} …", flush=True)
        results: dict[str, list[str]] = {}
        for key, system_prompt in prompts.items():
            got = await asyncio.gather(
                *(agent.respond(system_prompt, context) for _ in range(args.samples)),
                return_exceptions=True,
            )
            results[key] = [
                f"⚠️ {type(item).__name__}: {item}"
                if isinstance(item, BaseException)
                else render(item.decision)
                for item in got
            ]

        speaker, line = scenario["trigger"]
        out += [
            f"## {scenario['id']} {scenario['name']}",
            "",
            f"**{speaker}**：{line}",
            "",
            f"> 期望：{scenario['expect']}",
            "",
        ]
        for index in range(args.samples):
            out += [
                f"### 采样 {index + 1}",
                "",
                "| base（旧） | tuned（新） |",
                "| --- | --- |",
                "| "
                + results["base"][index].replace("\n", "<br>")
                + " | "
                + results["tuned"][index].replace("\n", "<br>")
                + " |",
                "",
            ]

    stamp = datetime.now().strftime("%m%d-%H%M")
    path = CALIB / f"{args.character}_ab_{stamp}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"\n写入 {path.relative_to(REPO)}")


if __name__ == "__main__":
    asyncio.run(main())
