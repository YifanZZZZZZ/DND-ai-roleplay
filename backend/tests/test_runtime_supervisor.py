from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.character_agent import CharacterAgentResult, CharacterDecision
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.engine import create_engine
from backend.app.db.models import (
    AgentRun,
    Campaign,
    CampaignMembership,
    Character,
    CharacterProfile,
    GameSession,
    LlmInvocation,
    Message,
    MessageRecipient,
    SessionCharacterState,
    SessionRuntime,
)
from backend.app.domain.enums import (
    AgentRunStatus,
    CampaignLifecycleStatus,
    LlmInvocationStatus,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
)
from backend.app.runtime.supervisor import RuntimeSupervisor


class FakeCharacterAgent:
    def __init__(self, result: CharacterAgentResult) -> None:
        self.result = result
        self.contexts: list[str] = []

    async def respond(self, context: str) -> CharacterAgentResult:
        self.contexts.append(context)
        return self.result


class ScriptedCharacterAgent:
    def __init__(self) -> None:
        self.contexts: list[str] = []

    async def respond(self, context: str) -> CharacterAgentResult:
        self.contexts.append(context)
        if '"角色扮演指引": "布兰"' in context:
            return CharacterAgentResult(
                decision=CharacterDecision(
                    decision="RESPOND",
                    content="我举起手示意大家先停下。",
                    urgency="HIGH",
                    requires_dm_resolution=True,
                    resolution_request="布兰能否从脚步声中判断对方距离？",
                ),
                input_tokens=9,
                output_tokens=7,
            )
        return CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="我安静地观察走廊。"),
            input_tokens=8,
            output_tokens=6,
        )


class FailingCharacterAgent:
    async def respond(self, context: str) -> CharacterAgentResult:
        del context
        raise RuntimeError("模拟供应商超时")


@pytest.fixture
async def runtime_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = Settings(data_dir=tmp_path / "data")
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


async def _seed_run(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str, str]:
    async with factory() as session:
        character = Character(name="赛蕾妮", roleplay_prompt="谨慎而友善。", max_hp=30)
        character.profile = CharacterProfile(content="信任自己的小队伙伴。")
        campaign = Campaign(name="测试战役", lifecycle_status=CampaignLifecycleStatus.ACTIVE)
        campaign.memberships = [CampaignMembership(character=character)]
        game_session = GameSession(title="第一节", campaign=campaign, next_sequence_no=2)
        game_session.runtime = SessionRuntime(
            status=RuntimeStatus.AGENTS_EVALUATING,
            generation=1,
        )
        game_session.character_states = [
            SessionCharacterState(character=character, current_hp=15, max_hp_snapshot=30)
        ]
        message = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="昏暗的走廊尽头传来脚步声。",
            client_request_id="6b1a16ee-9c0f-4b42-b91a-0bd419eeedaa",
        )
        message.recipients = [MessageRecipient(character=character)]
        session.add_all([campaign, game_session, message])
        await session.flush()
        run = AgentRun(
            campaign_id=campaign.id,
            session_id=game_session.id,
            trigger_message_id=message.id,
            generation=1,
            status=AgentRunStatus.PENDING,
            eligible_count=1,
        )
        session.add(run)
        await session.flush()
        game_session.runtime.active_agent_run_id = run.id
        await session.commit()
        return run.id, game_session.id, character.id


async def _seed_two_character_run(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[str, str, str]:
    async with factory() as session:
        selene = Character(name="赛蕾妮", roleplay_prompt="赛蕾妮", max_hp=30)
        selene.profile = CharacterProfile(content="")
        bran = Character(name="布兰", roleplay_prompt="布兰", max_hp=20)
        bran.profile = CharacterProfile(content="")
        campaign = Campaign(name="双角色测试", lifecycle_status=CampaignLifecycleStatus.ACTIVE)
        campaign.memberships = [
            CampaignMembership(character=selene),
            CampaignMembership(character=bran),
        ]
        game_session = GameSession(title="第一节", campaign=campaign, next_sequence_no=2)
        game_session.runtime = SessionRuntime(status=RuntimeStatus.AGENTS_EVALUATING, generation=1)
        game_session.character_states = [
            SessionCharacterState(character=selene, current_hp=30, max_hp_snapshot=30),
            SessionCharacterState(character=bran, current_hp=20, max_hp_snapshot=20),
        ]
        message = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="远处传来脚步声。",
            client_request_id="6b1a16ee-9c0f-4b42-b91a-0bd419eeedabc",
        )
        message.recipients = [MessageRecipient(character=selene), MessageRecipient(character=bran)]
        session.add_all([campaign, game_session, message])
        await session.flush()
        run = AgentRun(
            campaign_id=campaign.id,
            session_id=game_session.id,
            trigger_message_id=message.id,
            generation=1,
            status=AgentRunStatus.PENDING,
            eligible_count=2,
            random_seed=1,
        )
        session.add(run)
        await session.flush()
        game_session.runtime.active_agent_run_id = run.id
        await session.commit()
        return run.id, game_session.id, bran.id


async def test_supervisor_publishes_one_message_and_waits_for_dm(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, character_id = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(
                decision="RESPOND",
                content="我贴近墙边，试着辨认那脚步声来自何处。",
                requires_dm_resolution=True,
                resolution_request="赛蕾妮是否能辨认脚步声的来源？",
            ),
            input_tokens=12,
            output_tokens=8,
        )
    )
    settings = Settings(
        data_dir=tmp_path / "runtime-data",
        deepseek_api_key="unused-for-fake-agent",
    )
    supervisor = RuntimeSupervisor(runtime_factory, lambda _: agent, settings)

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.WAITING_FOR_DM
        assert game_session.runtime.waiting_request == "赛蕾妮是否能辨认脚步声的来源？"
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert len(messages) == 2
        assert messages[-1].sender_character_id == character_id
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.COMPLETED
        assert invocation.input_tokens == 12
    assert len(agent.contexts) == 1
    assert "重伤" in agent.contexts[0]
    assert "15" not in agent.contexts[0]


async def test_stale_generation_cannot_publish_old_agent_result(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="我准备前进。"),
            input_tokens=None,
            output_tokens=None,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )
    claimed = await supervisor._claim(run_id)
    assert claimed is not None
    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        game_session.runtime.generation += 1
        game_session.runtime.active_agent_run_id = None
        await session.commit()

    await supervisor._commit_results(claimed, [agent.result], 0.0)

    async with runtime_factory() as session:
        messages = list(
            await session.scalars(select(Message).where(Message.session_id == session_id))
        )
        assert len(messages) == 1
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.CANCELLED


async def test_parallel_candidates_publish_only_the_coordinator_choice(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, bran_id = await _seed_two_character_run(runtime_factory)
    agent = ScriptedCharacterAgent()
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert len(messages) == 2
        assert messages[-1].sender_character_id == bran_id
        invocations = list(
            await session.scalars(select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id))
        )
        assert len(invocations) == 2
        assert {item.status for item in invocations} == {LlmInvocationStatus.COMPLETED}
    assert len(agent.contexts) == 2


async def test_twelfth_published_ai_message_returns_runtime_to_idle(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        game_session.runtime.consecutive_ai_messages = 11
        await session.commit()
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="我们暂且停在这里。"),
            input_tokens=4,
            output_tokens=4,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.IDLE
        assert game_session.runtime.consecutive_ai_messages == 12
        runs = list(
            await session.scalars(select(AgentRun).where(AgentRun.session_id == session_id))
        )
        assert len(runs) == 1


async def test_validator_is_disabled_by_default(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(
                decision="RESPOND",
                content="我进行调查检定。\n\n结果是 18。",
                requires_dm_resolution=True,
                resolution_request="请 DM 裁定调查结果。",
            ),
            input_tokens=5,
            output_tokens=5,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.WAITING_FOR_DM
        assert game_session.runtime.last_error_code is None
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert messages[-1].content == "我进行调查检定。\n\n结果是 18。"


async def test_enabled_validator_persists_detailed_failure(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="我的检定结果是 18。"),
            input_tokens=5,
            output_tokens=5,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(
            data_dir=tmp_path / "runtime-data",
            deepseek_api_key="unused",
            enable_message_validator=True,
        ),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.ERROR
        assert game_session.runtime.last_error_code == "MESSAGE_VALIDATION_FAILED"
        assert "未通过校验" in (game_session.runtime.last_error_message or "")
        assert "机械数值" in (game_session.runtime.last_error_message or "")


async def test_agent_failure_persists_invocation_and_runtime_details(
    runtime_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: FailingCharacterAgent(),
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused"),
    )

    with caplog.at_level("ERROR"):
        await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.ERROR
        assert game_session.runtime.last_error_code == "ALL_CHARACTER_AGENTS_FAILED"
        assert "模拟供应商超时" in (game_session.runtime.last_error_message or "")
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.FAILED
        assert invocation.error_code == "CHARACTER_AGENT_FAILED"
        assert invocation.error_message == "RuntimeError: 模拟供应商超时"
    assert "Character Agent call failed" in caplog.text
